from __future__ import annotations

import importlib.util
import shutil
import sqlite3
import sys
import types
from pathlib import Path

import pytest

from utils import incident_context
from utils.incident_db import create_incident_database
from utils.state import AppState


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_package(name: str, path: Path) -> None:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader is not None
    spec.loader.exec_module(module)
    return module


_ensure_package("modules.operations", REPO_ROOT / "modules" / "operations")
_ensure_package("modules.operations.teams", REPO_ROOT / "modules" / "operations" / "teams")
_ensure_package("modules.operations.teams.data", REPO_ROOT / "modules" / "operations" / "teams" / "data")
_ensure_package("modules.operations.taskings", REPO_ROOT / "modules" / "operations" / "taskings")

team_model_module = _load_module(
    "modules.operations.teams.data.team",
    REPO_ROOT / "modules" / "operations" / "teams" / "data" / "team.py",
)
team_repository = _load_module(
    "modules.operations.teams.data.repository",
    REPO_ROOT / "modules" / "operations" / "teams" / "data" / "repository.py",
)
task_repository = _load_module(
    "modules.operations.taskings.repository",
    REPO_ROOT / "modules" / "operations" / "taskings" / "repository.py",
)
Team = team_model_module.Team


@pytest.fixture()
def incident_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    base = tmp_path / "data"
    incidents_dir = base / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)

    repo_template = REPO_ROOT / "data" / "incidents" / "template.db"
    shutil.copy2(repo_template, incidents_dir / "template.db")

    monkeypatch.setenv("CHECKIN_DATA_DIR", str(base))
    monkeypatch.setattr(incident_context, "_DATA_DIR", base)

    previous_incident = AppState.get_active_incident()
    AppState.set_active_incident(None)
    try:
        yield base
    finally:
        AppState.set_active_incident(previous_incident)


def test_add_team_snapshots_roster_when_team_columns_present(incident_data_dir: Path) -> None:
    incident_number = "INC-OPS-003"
    db_path = create_incident_database(incident_number)
    AppState.set_active_incident(incident_number)

    # Ensure schema has team_id columns on personnel/vehicles for this test
    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute("ALTER TABLE personnel ADD COLUMN team_id INTEGER")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE vehicles ADD COLUMN team_id INTEGER")
        except Exception:
            pass
        conn.commit()

    team = team_repository.save_team(Team(name="Charlie", team_type="GT"))
    assert team.team_id is not None

    # Seed one person and one vehicle on the team
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO personnel (id, name, role, phone, team_id) VALUES (?,?,?,?,?)",
            (101, "Pat Smith", "TL", "555-1001", int(team.team_id)),
        )
        # vehicles.id is TEXT in template; use a string id
        conn.execute(
            "INSERT INTO vehicles (id, status_id, make, model, team_id) VALUES (?,?,?,?,?)",
            ("V-101", "Available", "Ford", "F150", int(team.team_id)),
        )
        conn.commit()

    task_id = task_repository.create_task(title="Search Sector Charlie")
    assert task_id > 0

    tt_id = task_repository.add_task_team(task_id, team.team_id, None, True)
    assert tt_id > 0

    # Verify snapshot rows exist
    with sqlite3.connect(db_path) as conn:
        c1 = conn.execute(
            "SELECT COUNT(*) FROM task_personnel WHERE task_id=? AND personnel_id=?",
            (int(task_id), 101),
        ).fetchone()[0]
        c2 = conn.execute(
            "SELECT COUNT(*) FROM task_vehicles WHERE task_id=? AND vehicle_id=?",
            (int(task_id), "V-101"),
        ).fetchone()[0]
    assert c1 == 1
    assert c2 == 1

    # The list helpers should also return these entries (either via team linkage or snapshot)
    people = task_repository.list_task_personnel(task_id)
    vehicles = task_repository.list_task_vehicles(task_id)
    assert any(p.get("id") == 101 for p in people)
    assert any(v.get("id") == "V-101" for v in vehicles)
