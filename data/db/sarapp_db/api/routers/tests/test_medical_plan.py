"""ICS-206 merged medical plan storage."""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from bridge.medical_bridge import MedicalBridge
from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from utils import incident_context
from utils.state import AppState


INCIDENT_ID = "TEST_MEDICAL_PLAN"
OLD_COLLECTIONS = (
    "ics_206_ambulance_services",
    "ics_206_hospitals",
    "ics_206_air_ambulance",
    "ics_206_medical_comms",
    "ics_206_procedures",
    "ics_206_signatures",
)


def _clear(db):
    db["medical_plan"].delete_many({})
    db["ics_206_aid_stations"].delete_many({})
    for name in OLD_COLLECTIONS:
        db[name].delete_many({})


def test_ics206_sections_are_stored_in_medical_plan():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    incident_context.set_active_incident(INCIDENT_ID)
    AppState._active_incident_number = INCIDENT_ID
    AppState.set_active_op_period(1)

    bridge = MedicalBridge()
    bridge.ensure_ics206_tables()
    ambulance_id = bridge.add_record(
        "ambulance_services",
        {
            "name": "County EMS",
            "type": "Ground ALS",
            "service_level": 2,
            "phone": "555-0101",
            "location": "Station 1",
            "notes": "Primary transport",
        },
    )
    bridge.add_record(
        "hospitals",
        {
            "name": "General Hospital",
            "address": "1 Main St",
            "phone": "555-0202",
            "helipad": 1,
            "burn_center": 0,
            "level": "II",
        },
    )
    bridge.save_procedures("Call medical unit before transport.")
    bridge.save_signatures({"prepared_by": "Med Lead", "position": "MEDL", "approved_by": "IC", "date": "2026-07-11"})

    plan_doc = db["medical_plan"].find_one({"incident_id": INCIDENT_ID, "op_period": 1})
    assert plan_doc is not None
    assert plan_doc["plan_id"] == f"{INCIDENT_ID}-MEDICAL-PLAN-1"
    assert plan_doc["ambulance_services"][0]["id"] == ambulance_id
    assert plan_doc["ambulance_services"][0]["name"] == "County EMS"
    assert plan_doc["hospitals"][0]["name"] == "General Hospital"
    assert plan_doc["procedures"]["content"] == "Call medical unit before transport."
    assert plan_doc["signatures"]["prepared_by"] == "Med Lead"
    for name in OLD_COLLECTIONS:
        assert db[name].count_documents({}) == 0

    app = create_app()
    with TestClient(app) as client:
        ambulances = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/ambulance-services", params={"op": 1})
        procedures = client.get(f"/api/incidents/{INCIDENT_ID}/medical/ics206/procedures", params={"op": 1})
    assert ambulances.status_code == 200
    assert ambulances.json()[0]["name"] == "County EMS"
    assert procedures.status_code == 200
    assert procedures.json()["content"] == "Call medical unit before transport."

    _clear(db)
