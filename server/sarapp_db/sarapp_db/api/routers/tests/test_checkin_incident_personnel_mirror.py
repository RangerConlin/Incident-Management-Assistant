"""Saving a check-in must mirror personnel fields into the per-incident
`incident_personnel` collection through IncidentPersonnelRepository (the
write used to bypass BaseRepository with a raw pymongo upsert)."""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

INCIDENT_ID = "TEST_CHECKIN_INCIDENT_PERSONNEL_MIRROR"
PERSON_RECORD = 501


def _clear():
    get_incident_db(INCIDENT_ID)[IncidentCollections.RESOURCE_STATUS].delete_many({})
    get_incident_db(INCIDENT_ID)[IncidentCollections.INCIDENT_PERSONNEL].delete_many({})
    get_master_db()[MasterCollections.PERSONNEL].delete_many({"person_record": PERSON_RECORD})


def _seed_master_person():
    get_master_db()[MasterCollections.PERSONNEL].insert_one({
        "_id": "test-person-501",
        "person_record": PERSON_RECORD,
        "name": "Jordan Smith",
        "rank": "FF",
        "callsign": "Rescue-1",
        "primary_role": "Medic",
        "phone": "555-0100",
        "email": "jordan@example.com",
        "organization": "County SAR",
        "person_id": "P-501",
        "is_medic": True,
        "deleted": False,
    })


def test_save_checkin_upserts_incident_personnel_record():
    _clear()
    _seed_master_person()

    app = create_app()
    with TestClient(app) as client:
        res = client.put(
            f"/api/incidents/{INCIDENT_ID}/checkin/{PERSON_RECORD}",
            json={"status": "Checked In", "incident_callsign": "Rescue-1A"},
        )
    assert res.status_code == 200, res.text

    mirrored = get_incident_db(INCIDENT_ID)[IncidentCollections.INCIDENT_PERSONNEL].find_one(
        {"person_record": PERSON_RECORD}
    )
    assert mirrored is not None
    assert mirrored["name"] == "Jordan Smith"
    assert mirrored["callsign"] == "Rescue-1A"
    assert mirrored["is_medic"] is True
    assert mirrored["incident_id"] == INCIDENT_ID

    _clear()


def test_save_checkin_updates_existing_incident_personnel_record_in_place():
    _clear()
    _seed_master_person()

    app = create_app()
    with TestClient(app) as client:
        client.put(
            f"/api/incidents/{INCIDENT_ID}/checkin/{PERSON_RECORD}",
            json={"status": "Checked In"},
        )
        res = client.put(
            f"/api/incidents/{INCIDENT_ID}/checkin/{PERSON_RECORD}",
            json={"status": "Checked In", "incident_callsign": "Rescue-9"},
        )
    assert res.status_code == 200, res.text

    col = get_incident_db(INCIDENT_ID)[IncidentCollections.INCIDENT_PERSONNEL]
    docs = list(col.find({"person_record": PERSON_RECORD}))
    assert len(docs) == 1
    assert docs[0]["callsign"] == "Rescue-9"

    _clear()
