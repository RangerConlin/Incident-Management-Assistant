"""Guard the team-id/int_id consolidation for the comms-log contact
suggestion builder: a live-created team (int_id only, no team_id field)
must produce a usable `id` in the suggestion list rather than None.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_COMMS_CONTACTS_INT_ID"


def _clear(db):
    db["teams"].delete_many({})
    db["incident_personnel"].delete_many({})


def test_comms_contacts_resolves_team_id_from_int_id():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one({
        "int_id": 5,
        "name": "GT-5 Echo",
        "callsign": "Echo-5",
        "status": "Available",
        "deleted": False,
    })

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/comms-log/contacts")
    assert res.status_code == 200
    suggestions = res.json()
    team_suggestions = [s for s in suggestions if s["type"] == "team"]
    assert len(team_suggestions) == 1
    assert team_suggestions[0]["id"] == 5
    assert team_suggestions[0]["primary"] == "GT-5 Echo"

    _clear(db)
