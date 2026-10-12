"""Guard against list_comms_contacts filtering the per-incident teams
collection by an "incident_id" field that team documents never carry
(each incident already gets its own database via get_incident_db). See
the identical bug fixed in ic_overview.py's team/task readers.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_COMMS_CONTACTS"


def _clear(db):
    db["teams"].delete_many({})
    db["incident_personnel"].delete_many({})


def test_comms_contacts_returns_team_with_no_incident_id_field():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one({
        "int_id": 7,
        "team_id": "TEST_COMMS_CONTACTS-TEAM-7",
        "name": "Team 7",
        "callsign": "Rescue 7",
        "deleted": False,
    })

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/comms-log/contacts")
    assert res.status_code == 200
    contacts = res.json()
    team_contacts = [c for c in contacts if c["type"] == "team"]
    assert len(team_contacts) == 1
    assert team_contacts[0]["id"] == 7
    assert team_contacts[0]["primary"] == "Team 7"

    _clear(db)
