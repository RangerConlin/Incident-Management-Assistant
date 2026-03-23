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


def test_team_status_sets_to_assigned_on_add(incident_data_dir: Path) -> None:
    incident_number = "INC-OPS-002"
    db_path = create_incident_database(incident_number)
    AppState.set_active_incident(incident_number)

    team = team_repository.save_team(Team(name="Bravo", team_type="GT"))
    assert team.team_id is not None

    task_id = task_repository.create_task(title="Search Sector Bravo")
    assert task_id > 0

    tt_id = task_repository.add_task_team(task_id, team.team_id, None, True)
    assert tt_id > 0

    # Verify team.status is updated to "Assigned" and timestamp is present
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, status_updated FROM teams WHERE id=?",
            (team.team_id,),
        ).fetchone()

    assert row is not None
    assert (row[0] or "").strip().lower() == "assigned"
    assert isinstance(row[1], str) and len((row[1] or "").strip()) > 0
