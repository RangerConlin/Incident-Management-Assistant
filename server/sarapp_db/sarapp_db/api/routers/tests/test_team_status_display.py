"""Regression coverage for PATCH .../operations/teams/{id}/status.

Guards two bugs found together while wiring the mobile status buttons:
1. `_team_status_from_tt` was referenced but never defined, so updating a
   team's status while it had an active task (any status_key present in
   TS_STATUS_COLS) crashed with a NameError -> 500.
2. The endpoint's display-text mapping was stale/incomplete, so aliases
   like "oos" persisted as "Oos" instead of "Out of Service".
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_TEAM_STATUS"


def _clear(db):
    db["teams"].delete_many({})
    db["tasks"].delete_many({})


def _seed_team_with_active_task(db):
    db["teams"].insert_one({
        "int_id": 1, "name": "Team 1", "team_type": "GT", "status": "Assigned",
        "current_task_id": 1,
    })
    db["tasks"].insert_one({
        "int_id": 1, "task_id": "T-001", "title": "Search Sector 4",
        "status": "Assigned", "task_teams": [
            {"id": 1, "team_id": 1, "team_name": "Team 1", "time_assigned": "2026-07-12T21:00:00+00:00"},
        ],
    })


def test_status_update_with_active_task_does_not_500():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _seed_team_with_active_task(db)

    app = create_app()
    with TestClient(app) as client:
        res = client.patch(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/1/status",
            json={"status_key": "enroute", "changed_by": "pytest"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "En Route"

    _clear(db)


def test_oos_status_persists_full_display_text():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one({
        "int_id": 2, "name": "Team 2", "team_type": "GT", "status": "Available",
        "current_task_id": None,
    })

    app = create_app()
    with TestClient(app) as client:
        res = client.patch(
            f"/api/incidents/{INCIDENT_ID}/operations/teams/2/status",
            json={"status_key": "oos", "changed_by": "pytest"},
        )
    assert res.status_code == 200
    assert res.json()["status"] == "Out of Service"

    _clear(db)
