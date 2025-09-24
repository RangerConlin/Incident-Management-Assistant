from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import utils.db as utils_db
from PySide6.QtWidgets import QApplication, QMessageBox as QtMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from modules.command.ics203.controller import ICS203Controller
from modules.command.ics203.models import (
    ICS203Repository,
    MasterPersonnelRepository,
    ensure_incident_schema,
    render_template,
)
from modules.command.ics203.panels import ics203_panel
from modules.command.ics203.panels.ics203_panel import ICS203Panel
from utils.state import AppState


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    base = tmp_path / "data"
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(base))
    monkeypatch.setattr(utils_db, "_DATA_DIR", base)
    return base


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    previous = AppState.get_active_incident()
    AppState.set_active_incident(None)
    try:
        yield
    finally:
        AppState.set_active_incident(previous)


def test_ensure_incident_schema_creates_tables(data_dir: Path) -> None:
    ensure_incident_schema("test-incident")
    db_path = data_dir / "incidents" / "test-incident.db"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {
        "ics203_units",
        "ics203_positions",
        "ics203_assignments",
    }.issubset(tables)


def test_repository_apply_template_sets_hierarchy(data_dir: Path) -> None:
    repo = ICS203Repository("alpha")
    items = render_template("Operations → Branch I → Alpha/Bravo", "alpha")
    repo.apply_batch(items)
    units = repo.list_units()
    by_name = {u.name: u for u in units}
    branch = by_name["Branch I"]
    operations = by_name["Operations"]
    assert branch.parent_unit_id == operations.id
    division_alpha = by_name["Division Alpha"]
    assert division_alpha.parent_unit_id == branch.id


def test_air_operations_template_creates_groups(data_dir: Path) -> None:
    repo = ICS203Repository("air")
    repo.apply_batch(render_template("Operations → Air Operations Branch", "air"))
    units = {unit.name: unit for unit in repo.list_units()}
    assert "Air Tactical Group" in units
    assert "Air Support Group" in units
    air_branch = units["Air Operations Branch"]
    assert units["Air Tactical Group"].parent_unit_id == air_branch.id
    assert units["Air Support Group"].parent_unit_id == air_branch.id
    titles = {position.title for position in repo.list_all_positions()}
    assert "Helibase Manager" in titles


def test_controller_export_snapshot(data_dir: Path) -> None:
    controller = ICS203Controller("exp")
    ops_id = controller.add_unit({"unit_type": "Section", "name": "Operations", "sort_order": 1})
    pos_id = controller.add_position({"title": "Division Supervisor", "unit_id": ops_id, "sort_order": 0})
    controller.add_assignment(pos_id, {"display_name": "Alex Rivera", "callsign": "DIV-A"})
    export_path = controller.export_snapshot()
    assert export_path.exists()
    content = export_path.read_text(encoding="utf-8")
    assert "Division Supervisor" in content
    assert "Alex Rivera" in content


def test_master_personnel_search_uses_master_db(data_dir: Path) -> None:
    master_path = data_dir / "master.db"
    master_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(master_path) as conn:
        conn.execute(
            """
            CREATE TABLE personnel (
                id TEXT PRIMARY KEY,
                name TEXT,
                callsign TEXT,
                phone TEXT,
                home_unit TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO personnel (id, name, callsign, phone, home_unit) VALUES (?,?,?,?,?)",
            ("101", "Alex Rivera", "DIV-A", "555-0101", "County SAR"),
        )
        conn.commit()
    repo = MasterPersonnelRepository()
    results = repo.search_people("Rivera")
    assert results
    assert results[0]["name"] == "Alex Rivera"
    assert results[0]["agency"] == "County SAR"


def test_command_staff_template_sets_command_positions(data_dir: Path) -> None:
    repo = ICS203Repository("command")
    repo.apply_batch(render_template("Command Staff", "command"))
    units = {unit.name: unit for unit in repo.list_units()}
    assert "Command" in units
    command_unit_id = units["Command"].id
    positions = repo.list_all_positions()
    titles = {position.title for position in positions}
    assert {"Incident Commander", "Public Information Officer"}.issubset(titles)
    agency_rep = next(p for p in positions if p.title == "Agency Representative")
    assert agency_rep.unit_id == command_unit_id


def test_panel_buttons_disabled_until_load(qt_app: QApplication, data_dir: Path) -> None:
    panel = ICS203Panel()
    try:
        assert not panel.btn_templates.isEnabled()
        assert not panel.btn_seed.isEnabled()
        panel.load("incident-123")
        assert panel.btn_templates.isEnabled()
        assert panel.btn_seed.isEnabled()
    finally:
        panel.deleteLater()


def test_panel_warns_when_no_incident(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    panel = ICS203Panel()
    captured: dict[str, tuple[str, str]] = {}

    def fake_warning(parent, title, message):
        captured["warning"] = (title, message)
        return QtMessageBox.Ok

    monkeypatch.setattr(ics203_panel.QMessageBox, "warning", fake_warning)
    try:
        panel._apply_template()
    finally:
        panel.deleteLater()

    assert captured.get("warning") == (
        "Incident Required",
        "Load an incident before managing the ICS-203 organization.",
    )


def test_panel_auto_loads_active_incident(
    qt_app: QApplication, data_dir: Path
) -> None:
    AppState.set_active_incident("auto-1")
    panel = ICS203Panel()
    try:
        assert panel.incident_id == "auto-1"
        assert panel.btn_seed.isEnabled()
    finally:
        panel.deleteLater()


def test_panel_refreshes_on_incident_change(
    qt_app: QApplication, data_dir: Path
) -> None:
    AppState.set_active_incident("inc-001")
    panel = ICS203Panel()
    try:
        assert panel.incident_id == "inc-001"
        AppState.set_active_incident("inc-002")
        qt_app.processEvents()
        assert panel.incident_id == "inc-002"
    finally:
        panel.deleteLater()
