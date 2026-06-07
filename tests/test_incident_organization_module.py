from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import utils.db as utils_db

from modules.command.incident_organization.controller import IncidentOrganizationController
from modules.command.incident_organization.repository import IncidentOrganizationRepository
from utils.state import AppState


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    base = tmp_path / "data"
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(base))
    monkeypatch.setattr(utils_db, "_DATA_DIR", base)
    return base


@pytest.fixture(scope="session")
def qt_app():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    QApplication = qt_widgets.QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def reset_app_state():
    previous = AppState.get_active_incident()
    AppState.set_active_incident(None)
    try:
        yield
    finally:
        AppState.set_active_incident(previous)


def test_repository_creates_incident_organization_tables(data_dir: Path) -> None:
    repo = IncidentOrganizationRepository("org-schema")

    with sqlite3.connect(data_dir / "incidents" / "org-schema.db") as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert "organization_positions" in tables
    assert "position_assignments" in tables
    assert "position_assignment_history" in tables
    assert "position_requirements" in tables
    assert "organization_templates" in tables
    assert "generated_form_snapshots" in tables


def test_assignment_history_is_preserved(data_dir: Path) -> None:
    controller = IncidentOrganizationController("org-history")
    position_id = controller.add_position(
        {
            "title": "Operations Section Chief",
            "classification": "section",
            "is_critical": True,
        }
    )
    assignment_id, warnings = controller.assign_person(
        position_id,
        {
            "personnel_id": "101",
            "display_name": "Alex Rivera",
            "assignment_type": "primary",
            "assigned_by": "Planner",
        },
    )

    assert assignment_id > 0
    assert warnings == []
    controller.remove_assignment(assignment_id, changed_by="Planner", notes="Shift ended")

    assert controller.list_assignments(position_id) == []
    all_assignments = controller.list_assignments(position_id, active_only=False)
    assert all_assignments[0].end_time is not None
    history = controller.list_assignment_history(position_id)
    assert [entry.action for entry in history] == ["assigned", "removed"]
    assert history[-1].notes == "Shift ended"


def test_staffing_and_span_warnings_are_calculated(data_dir: Path) -> None:
    controller = IncidentOrganizationController("org-warnings")
    command_id = controller.add_position(
        {
            "title": "Incident Commander",
            "classification": "command",
            "is_critical": True,
        }
    )
    for index in range(8):
        controller.add_position(
            {
                "title": f"Branch Director {index}",
                "classification": "branch",
                "parent_position_id": command_id,
            }
        )

    summary = controller.staffing_summary()[command_id]

    assert summary.staffing_status == "vacant"
    assert {warning.code for warning in summary.warnings} == {
        "critical_vacancy",
        "span_of_control",
    }


def test_qualification_warning_does_not_block_assignment(data_dir: Path) -> None:
    controller = IncidentOrganizationController("org-quals")
    position_id = controller.add_position(
        {
            "title": "Planning Section Chief",
            "classification": "section",
            "required_qualifications": ["PSC3"],
        }
    )

    assignment_id, warnings = controller.assign_person(
        position_id,
        {
            "display_name": "Taylor Morgan",
            "assignment_type": "trainee",
        },
    )

    assert assignment_id > 0
    assert [warning.code for warning in warnings] == ["qualification_review"]
    assert controller.list_assignments(position_id)[0].display_name == "Taylor Morgan"


def test_ics203_and_ics207_payloads_are_generated_from_structure(data_dir: Path) -> None:
    controller = IncidentOrganizationController("org-forms")
    parent_id = controller.add_position(
        {"title": "Logistics Section Chief", "classification": "section"}
    )
    child_id = controller.add_position(
        {
            "title": "Communications Unit Leader",
            "classification": "unit",
            "parent_position_id": parent_id,
        }
    )
    controller.assign_person(child_id, {"display_name": "Sam Lee"})

    ics203 = controller.build_ics203_payload()
    ics207 = controller.build_ics207_payload()

    assert ics203["form_type"] == "ICS_203"
    assert any(
        item["title"] == "Communications Unit Leader"
        for item in ics203["positions"]
    )
    assert ics207["form_type"] == "ICS_207"
    assert {"parent_position_id": parent_id, "position_id": child_id} in ics207["edges"]
    snapshot_id = controller.save_generated_snapshot("ICS_203", ics203)
    assert snapshot_id > 0


def test_panel_loads_with_windows_entrypoint(qt_app, data_dir: Path) -> None:
    AppState.set_active_incident("org-ui")
    from modules.command.incident_organization import IncidentOrganizationPanel
    from modules.command.windows import get_staff_org_panel

    panel = get_staff_org_panel("org-ui")
    try:
        assert isinstance(panel, IncidentOrganizationPanel)
        assert panel.incident_id == "org-ui"
        assert panel.btn_ics203.text() == "Prepare ICS 203"
        assert panel.btn_ics207.text() == "Prepare ICS 207"
    finally:
        panel.deleteLater()
