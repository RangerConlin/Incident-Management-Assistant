"""Seed demo data for the Logistics Resource Request module.

The script populates the master database with a few suppliers and writes an
incident specific database containing representative resource requests across
all statuses.  Running the script is idempotent and safe for local testing.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from modules.logistics.resource_requests.api.service import ResourceRequestService
from modules.logistics.resource_requests.models.enums import Priority, RequestStatus
from utils import incident_db

MASTER_SUPPLIERS = [
    ("S1", "Mountain Outfitters", "Kelly Ridge", "555-0100", "kelly@outfitters.test", "123 Summit Rd", "Backcountry gear"),
    ("S2", "Valley Medical", "Dr. Lee", "555-0101", "lee@valleymed.test", "88 Health Way", "Field hospital kits"),
    ("S3", "Rotor Lift", "Captain Diaz", "555-0102", "diaz@rotorlift.test", "Airstrip 3", "Helicopter support"),
    ("S4", "Rapid Wheels", "Taylor Chen", "555-0103", "taylor@rapidwheels.test", "48 Logistics Pkwy", "Vehicle rentals"),
    ("S5", "SignalComm", "Jordan Poe", "555-0104", "jordan@signalcomm.test", "9 Radio Rd", "Communications trailers"),
    ("S6", "Hydro Support", "Sam Brook", "555-0105", "sam@hydro.test", "456 Water St", "Portable water systems"),
]

TEAMS = [
    ("T1", "Ground Team Alpha"),
    ("T2", "Medical Strike Team"),
    ("T3", "Air Operations"),
]

VEHICLES = [
    ("V1", "Truck 12"),
    ("V2", "Ambulance 4"),
]

AIRCRAFT = [
    ("A1", "Helicopter 7"),
]

COMMS = [(f"C{i:02d}", f"Cache Radio {i}") for i in range(1, 13)]


def _ensure_master_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_name TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            notes TEXT
        )
        """
    )


def seed_master(master_path: Path) -> None:
    master_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(master_path)
    try:
        _ensure_master_tables(conn)
        conn.executemany(
            "INSERT OR IGNORE INTO suppliers(id, name, contact_name, phone, email, address, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            MASTER_SUPPLIERS,
        )
        conn.commit()
    finally:
        conn.close()


def seed_incident(incident_id: str) -> None:
    db_path = incident_db.create_incident_database(incident_id)
    service = ResourceRequestService(incident_id, db_path)

    base = datetime.utcnow() - timedelta(days=1)
    priorities = [Priority.IMMEDIATE, Priority.HIGH, Priority.ROUTINE]
    statuses = list(RequestStatus)

    for index, status in enumerate(statuses, start=1):
        header = {
            "title": f"Demo Request {index}",
            "requesting_section": "Logistics",
            "needed_by_utc": (base + timedelta(hours=index)).isoformat() + "Z",
            "priority": priorities[index % len(priorities)].value,
            "status": RequestStatus.DRAFT.value,
            "created_by_id": "demo",
            "justification": "Training scenario seed",
            "delivery_location": "Base Camp",
            "comms_requirements": "VHF, SAR Net",
        }
        items = [
            {
                "kind": "SUPPLY",
                "description": "MRE Cases",
                "quantity": 10 + index,
                "unit": "case",
            }
        ]
        request_id = service.create_request(header, items)
        if status != RequestStatus.DRAFT:
            service.change_status(request_id, status.value, actor_id="demo", note="Seed progression")

    # Additional relationships for demonstration
    for req in service.list_requests({"status": [RequestStatus.APPROVED.value]}):
        service.assign_fulfillment(
            req["id"],
            supplier_id="S1",
            team_id="T1",
            vehicle_id="V1",
            eta_utc=datetime.utcnow().isoformat() + "Z",
            note="Seed assignment",
        )

    # Demo links/comms resources stored as JSON
    first_id = service.list_requests({"status": [RequestStatus.DRAFT.value]})[0]["id"]
    service.update_request(first_id, {"links": json.dumps({"ops_order": "OPORD-1"})})


def main() -> None:
    master_path = Path("data") / "master.db"
    seed_master(master_path)
    incident_db.set_active_incident_id("TRAINING-001")
    seed_incident("TRAINING-001")


if __name__ == "__main__":
    main()
