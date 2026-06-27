from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from utils import incident_context
from utils.api_client import api_client, DEFAULT_BASE_URL

from modules.logistics.resource_status.repository import ResourceStatusRepository
from modules.logistics.resource_status.service import ResourceStatusService


@pytest.fixture()
def resource_status_app_client():
    """Points api_client at the real sarapp_db app in-process — resource
    status reads/writes go through MongoDB via the API, not local SQLite."""
    from sarapp_db.api.app import create_app
    from sarapp_db.mongo.collection_names import IncidentCollections
    from sarapp_db.mongo.database_manager import get_incident_db

    for incident_id in ("resource-status-test", "resource-sync"):
        db = get_incident_db(incident_id)
        db[IncidentCollections.LOGISTICS_RESOURCE_STATUS_ITEMS].delete_many({})

    app = create_app()
    api_client.configure_test_transport(app)
    try:
        yield api_client
    finally:
        api_client.configure(DEFAULT_BASE_URL)


def _setup_incident(tmp_path: Path, monkeypatch, incident_id: str = "resource-status-test") -> Path:
    # incident_storage (which incident_context delegates to for path
    # resolution) reads its root from CHECKIN_DATA_DIR, not from any
    # attribute on incident_context itself — there's no "_DATA_DIR" on this
    # module, so setting one was a no-op and every run reused the same real
    # on-disk incident storage, leaking state across runs.
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path / "data"))
    incident_context.set_active_incident(incident_id)
    return incident_context.get_active_incident_db_path()


def test_create_and_update_resource_logs_audit(tmp_path: Path, monkeypatch, resource_status_app_client) -> None:
    db_path = _setup_incident(tmp_path, monkeypatch)
    service = ResourceStatusService(ResourceStatusRepository())

    created = service.create_resource(
        {
            "resource_id": "ENG-12",
            "resource_name": "Engine 12",
            "resource_type": "Vehicle",
            "status": "Pending",
            "eta_utc": "2026-03-22T12:30:00+00:00",
            "destination_facility_id": "fac-1",
            "notes": "Incoming support",
        },
        actor_name="pytest",
    )
    updated = service.update_resource(
        created.id,
        {
            "status": "Enroute",
            "eta_utc": "2026-03-22T13:00:00+00:00",
            "assigned_to": "Staging",
            "checkin_facility_id": "fac-2",
        },
        actor_name="pytest",
    )

    assert created.resource_id == "ENG-12"
    assert created.destination_facility_id == "fac-1"
    assert updated.status == "Enroute"
    assert updated.checkin_facility_id == "fac-2"
    audit_entries = service.list_audit_entries(created.id)
    fields = {entry["field_name"] for entry in audit_entries}
    assert {"status", "eta_utc", "assigned_to", "checkin_facility_id"}.issubset(fields)
    assert db_path.exists()


@pytest.mark.skip(
    reason="ResourceStatusRepository.source_rows() is an intentional stub "
    "('Incident source sync deferred — checkin/vehicle/aircraft not yet "
    "migrated', repository.py) — equipment/vehicle/aircraft checkin hasn't "
    "moved to MongoDB yet, so there's no live source to sync from. Re-enable "
    "once that migration lands."
)
def test_sync_from_incident_sources_seeds_board_without_duplicates(tmp_path: Path, monkeypatch, resource_status_app_client) -> None:
    _setup_incident(tmp_path, monkeypatch, incident_id="resource-sync")
    repo = ResourceStatusRepository()
    service = ResourceStatusService(repo)

    with incident_context.get_active_incident_db_path().open("a", encoding="utf-8"):
        pass
    import sqlite3

    conn = sqlite3.connect(incident_context.get_active_incident_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            status TEXT,
            location TEXT,
            notes TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO equipment (id, name, type, status, location, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (7, "Cache Trailer", "Trailer", "available", "Base", "Ready"),
    )
    conn.commit()
    conn.close()

    created_first = service.sync_from_incident_sources()
    created_second = service.sync_from_incident_sources()
    items = service.list_resources()

    assert created_first == 1
    assert created_second == 0
    assert len(items) == 1
    assert items[0].resource_name == "Cache Trailer"
    assert items[0].status == "Available"
