import importlib
import os
import sqlite3
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))


def setup_api(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    import utils.mission_context as mc
    import utils.db as db
    importlib.reload(mc)
    importlib.reload(db)

    modules_pkg = types.ModuleType("modules")
    modules_pkg.__path__ = []
    logistics_pkg = types.ModuleType("modules.logistics")
    logistics_pkg.__path__ = []
    checkin_pkg = types.ModuleType("modules.logistics.checkin")
    checkin_pkg.__path__ = [str(ROOT / "modules/logistics/checkin")]
    sys.modules["modules"] = modules_pkg
    sys.modules["modules.logistics"] = logistics_pkg
    sys.modules["modules.logistics.checkin"] = checkin_pkg

    spec_repo = importlib.util.spec_from_file_location(
        "modules.logistics.checkin.repository",
        ROOT / "modules/logistics/checkin/repository.py",
    )
    repo = importlib.util.module_from_spec(spec_repo)
    sys.modules[spec_repo.name] = repo
    spec_repo.loader.exec_module(repo)

    spec_api = importlib.util.spec_from_file_location(
        "modules.logistics.checkin.api",
        ROOT / "modules/logistics/checkin/api.py",
    )
    api = importlib.util.module_from_spec(spec_api)
    sys.modules[spec_api.name] = api
    spec_api.loader.exec_module(api)

    mc.set_active_mission("m1")
    return api, repo, mc


def test_check_in_flow(tmp_path, monkeypatch):
    api, repo, mc = setup_api(tmp_path, monkeypatch)
    master_payload = {"id": "P2", "first_name": "Bob", "last_name": "Jones"}
    repo.create_or_update_personnel_master(master_payload)

    # Existing record should copy to mission
    result = api.check_in_entity("personnel", {"mode": "id", "value": "P2"})
    assert result["success"] and result["was_copied"]

    mission_db = tmp_path / "missions" / "m1.db"
    with sqlite3.connect(mission_db) as conn:
        assert conn.execute("SELECT count(*) FROM personnel_mission WHERE id='P2'").fetchone()[0] == 1

    # Non existing should request creation
    result = api.check_in_entity("personnel", {"mode": "id", "value": "P3"})
    assert result.get("requiresCreate")

    # Create new record and ensure it exists in both DBs
    payload = {"id": "P3", "first_name": "Eve", "last_name": "Doe"}
    res2 = api.create_master_plus_mission("personnel", payload)
    assert res2["success"] and res2["was_created"]
    with sqlite3.connect(mission_db) as conn:
        assert conn.execute("SELECT count(*) FROM personnel_mission WHERE id='P3'").fetchone()[0] == 1
    master_db = tmp_path / "master.db"
    with sqlite3.connect(master_db) as conn:
        assert conn.execute("SELECT count(*) FROM personnel_master WHERE id='P3'").fetchone()[0] == 1
