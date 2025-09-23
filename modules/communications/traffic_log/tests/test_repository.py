from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils import incident_context
from utils.state import AppState

from modules.communications.models.master_repo import MasterRepository
from modules.communications.traffic_log.models import CommsLogEntry, CommsLogQuery
from modules.communications.traffic_log.repository import CommsLogRepository
from modules.communications.traffic_log.services import CommsLogService


@pytest.fixture()
def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    incident_context.set_active_incident("test-incident")
    AppState.set_active_incident("test-incident")
    AppState.set_active_user_id("comm_op")
    master_db = tmp_path / "master.db"
    with sqlite3.connect(master_db) as conn:
        conn.execute(
            """
            CREATE TABLE comms_resources (
                id INTEGER PRIMARY KEY,
                alpha_tag TEXT,
                function TEXT,
                freq_rx REAL,
                freq_tx REAL,
                mode TEXT,
                notes TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO comms_resources (id, alpha_tag, function, freq_rx, freq_tx, mode, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "VHF-1", "Tactical", 155.55, 155.55, "FM", "Primary tactical"),
        )
        conn.commit()

    # Reload modules that cache database paths
    import modules.communications.models.db as comms_db
    import modules.communications.models.master_repo as master_repo_module
    import modules.communications.traffic_log.models as log_models
    import modules.communications.traffic_log.repository as repo_module
    import modules.communications.traffic_log.services as services_module

    comms_db.MASTER_DB_PATH = master_db
    importlib.reload(comms_db)
    comms_db.MASTER_DB_PATH = master_db
    importlib.reload(master_repo_module)
    importlib.reload(log_models)
    importlib.reload(repo_module)
    importlib.reload(services_module)

    global MasterRepository, CommsLogEntry, CommsLogQuery, CommsLogRepository, CommsLogService
    from modules.communications.models.master_repo import MasterRepository as MasterRepository
    from modules.communications.traffic_log.models import CommsLogEntry as CommsLogEntry
    from modules.communications.traffic_log.models import CommsLogQuery as CommsLogQuery
    from modules.communications.traffic_log.repository import CommsLogRepository as CommsLogRepository
    from modules.communications.traffic_log.services import CommsLogService as CommsLogService

    return tmp_path


def test_repository_creates_entry_and_audit(setup_env):
    repo = CommsLogRepository(incident_id="test-incident")
    entry = CommsLogEntry(
        message="Rescue team checking in",
        priority="Routine",
        resource_id=1,
        from_unit="Team 1",
        to_unit="Base",
    )
    created = repo.add_entry(entry)
    assert created.id is not None
    master = MasterRepository()
    channel = master.get_channel(1)
    assert created.resource_label == channel["display_name"]
    assert created.frequency.startswith("155")

    updated = repo.update_entry(created.id, {"message": "Updated message", "follow_up_required": True})
    assert updated.message == "Updated message"
    assert updated.follow_up_required is True

    audits = repo.list_audit_entries(created.id)
    assert len(audits) >= 2
    assert audits[0].action in {"update", "create"}

    results = repo.list_entries(CommsLogQuery(priorities=["Routine"]))
    assert results and results[0].message == "Updated message"


def test_service_exports_csv(tmp_path, setup_env):
    repo = CommsLogRepository(incident_id="test-incident")
    service = CommsLogService(repository=repo)
    service.create_entry(
        {
            "message": "Perimeter established",
            "priority": "Priority",
            "resource_id": 1,
            "from_unit": "Base",
            "to_unit": "Ops",
            "follow_up_required": False,
        }
    )
    export_path = tmp_path / "log.csv"
    service.export_to_csv(export_path, CommsLogQuery())
    assert export_path.exists()
    text = export_path.read_text(encoding="utf-8")
    assert "Perimeter established" in text
