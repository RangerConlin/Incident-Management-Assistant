from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import incident_context

from modules.logistics.resource_status.repository import ResourceStatusRepository
from modules.logistics.resource_status.service import ResourceStatusService


def _setup_incident(tmp_path: Path, incident_id: str = "resource-status-test") -> Path:
    data_dir = tmp_path / "data"
    incident_context._DATA_DIR = data_dir  # type: ignore[attr-defined]
    incident_context.set_active_incident(incident_id)
    return data_dir / "incidents" / f"{incident_id}.db"


def test_create_and_update_resource_logs_audit(tmp_path: Path) -> None:
    db_path = _setup_incident(tmp_path)
    service = ResourceStatusService(ResourceStatusRepository())

    created = service.create_resource(
        {
            "resource_id": "ENG-12",
            "resource_name": "Engine 12",
            "resource_type": "Vehicle",
            "status": "Pending",
            "eta_utc": "2026-03-22T12:30:00+00:00",
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
        },
        actor_name="pytest",
    )

    assert created.resource_id == "ENG-12"
    assert updated.status == "Enroute"
    audit_entries = service.list_audit_entries(created.id)
    fields = {entry["field_name"] for entry in audit_entries}
    assert {"status", "eta_utc", "assigned_to"}.issubset(fields)
    assert db_path.exists()


def test_sync_from_incident_sources_seeds_board_without_duplicates(tmp_path: Path) -> None:
    _setup_incident(tmp_path, incident_id="resource-sync")
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
