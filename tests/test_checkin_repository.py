import importlib
import os
import sqlite3
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))


def setup_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    import utils.mission_context as mc
    import utils.db as db
    importlib.reload(mc)
    importlib.reload(db)

    # Create lightweight package hierarchy to avoid heavy imports
    modules_pkg = types.ModuleType("modules")
    modules_pkg.__path__ = []
    logistics_pkg = types.ModuleType("modules.logistics")
    logistics_pkg.__path__ = []
    checkin_pkg = types.ModuleType("modules.logistics.checkin")
    checkin_pkg.__path__ = [str(ROOT / "modules/logistics/checkin")]
    sys.modules["modules"] = modules_pkg
    sys.modules["modules.logistics"] = logistics_pkg
    sys.modules["modules.logistics.checkin"] = checkin_pkg

    spec = importlib.util.spec_from_file_location(
        "modules.logistics.checkin.repository",
        ROOT / "modules/logistics/checkin/repository.py",
    )
    repo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = repo
    spec.loader.exec_module(repo)

    mc.set_active_mission("test_mission")
    return repo, mc


def test_tables_created_and_copy(tmp_path, monkeypatch):
    repo, mc = setup_repo(tmp_path, monkeypatch)

    payload = {
        "id": "P1",
        "first_name": "Alice",
        "last_name": "Smith",
    }
    repo.create_or_update_personnel_master(payload)
    repo.copy_personnel_to_mission(payload)

    master_db = tmp_path / "master.db"
    mission_db = tmp_path / "missions" / "test_mission.db"

    assert master_db.exists()
    assert mission_db.exists()

    with sqlite3.connect(master_db) as conn:
        assert conn.execute("SELECT count(*) FROM personnel_master").fetchone()[0] == 1
    with sqlite3.connect(mission_db) as conn:
        row = conn.execute("SELECT status FROM personnel_mission WHERE id = 'P1'").fetchone()
        assert row[0] == "Checked-In"
