from __future__ import annotations

import importlib.util
import shutil
import sqlite3
import sys
import types
from pathlib import Path

import pytest

from utils import incident_context, incident_storage
from utils.incident_db import create_incident_database
from utils.state import AppState


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TABLES = {
    "agency_contacts",
    "assignment_air",
    "assignment_ground",
    "attachments",
    "audit_logs",
    "debriefs",
    "equipment",
    "narrative_entries",
    "operationalperiods",
    "personnel",
    "planning_logs",
    "planning_notes",
    "task_personnel",
    "task_teams",
    "task_vehicles",
    "tasks",
    "teams",
    "vehicles",
}


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
_ensure_package("modules.operations.data", REPO_ROOT / "modules" / "operations" / "data")
_ensure_package("modules.operations.teams", REPO_ROOT / "modules" / "operations" / "teams")
_ensure_package("modules.operations.teams.data", REPO_ROOT / "modules" / "operations" / "teams" / "data")
_ensure_package("modules.operations.taskings", REPO_ROOT / "modules" / "operations" / "taskings")

_load_module(
    "modules.operations.data.repository",
    REPO_ROOT / "modules" / "operations" / "data" / "repository.py",
)
team_model_module = _load_module(
    "modules.operations.teams.data.team",
    REPO_ROOT / "modules" / "operations" / "teams" / "data" / "team.py",
)
team_repository = _load_module(
    "modules.operations.teams.data.repository",
    REPO_ROOT / "modules" / "operations" / "teams" / "data" / "repository.py",
)
_load_module(
    "modules.operations.taskings.models",
    REPO_ROOT / "modules" / "operations" / "taskings" / "models.py",
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

    previous_incident = AppState.get_active_incident()
    AppState.set_active_incident(None)
    try:
        yield base
    finally:
        AppState.set_active_incident(previous_incident)


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_create_incident_database_initializes_template_schema(incident_data_dir: Path) -> None:
    db_path = create_incident_database("INC/001")

    paths = incident_storage.resolve_incident_paths_by_identifier("INC/001") or incident_storage.resolve_incident_paths_by_identifier("INC-001")
    assert paths is not None
    assert db_path == paths.incident_db
    assert paths.spatial_db.exists()
    assert paths.manifest.exists()
    assert db_path.exists()
    assert db_path.stat().st_size > 0

    tables = _table_names(db_path)
    assert REQUIRED_TABLES.issubset(tables)
    assert "notifications" in tables


def test_fresh_incident_supports_team_task_and_assignment_creation(incident_data_dir: Path) -> None:
    incident_number = "INC-OPS-001"
    db_path = create_incident_database(incident_number)
    AppState.set_active_incident(incident_number)

    team = team_repository.save_team(Team(name="Alpha", team_type="GT"))
    assert team.team_id is not None

    task_id = task_repository.create_task(title="Search Sector Alpha")
    assert task_id > 0

    task_team_id = task_repository.add_task_team(task_id, team.team_id, "S-001", True)
    assert task_team_id > 0

    with sqlite3.connect(db_path) as conn:
        team_row = conn.execute(
            "SELECT id, name, team_type, current_task_id FROM teams WHERE id=?",
            (team.team_id,),
        ).fetchone()
        task_row = conn.execute(
            "SELECT id, task_id, title, status FROM tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        link_row = conn.execute(
            "SELECT task_id, teamid, sortie_id, is_primary FROM task_teams WHERE id=?",
            (task_team_id,),
        ).fetchone()

    assert team_row == (team.team_id, "Alpha", "GT", task_id)
    assert task_row[0] == task_id
    assert task_row[2] == "Search Sector Alpha"
    assert task_row[3] == "Draft"
    assert link_row == (task_id, team.team_id, "S-001", 1)
