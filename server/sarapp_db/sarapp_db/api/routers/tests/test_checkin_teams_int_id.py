"""Guard the team-id/int_id consolidation: checkin.py's team endpoints must
resolve teams by int_id (the field operations.py's create_team actually
writes), not the retired team_id field. A live-created team (no team_id at
all) must be checkin-able, disband-able, and listed correctly. These tests
fail if checkin.py drifts back to querying by team_id.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_CHECKIN_TEAMS_INT_ID"


def _live_created_team_doc(**overrides) -> dict:
    """A team as `operations.py`'s create_team actually writes it — int_id
    only, no team_id field at all."""
    doc = {
        "int_id": 1,
        "name": "GT-4 Alpha",
        "status": "Available",
        "current_task_id": None,
        "disbanded": False,
    }
    doc.update(overrides)
    return doc


def _clear(db):
    db["teams"].delete_many({})


def test_get_distinct_teams_returns_int_id_as_team_id():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one(_live_created_team_doc(int_id=7, name="GT-7 Bravo"))

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/checkin/teams")
    assert res.status_code == 200
    teams = res.json()
    assert teams == [{"team_id": "7", "team_name": "GT-7 Bravo"}]

    _clear(db)


def test_team_checkin_resolves_by_int_id():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one(_live_created_team_doc(int_id=4, name="GT-4 Alpha", status="Available"))

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/checkin/teams/4/checkin",
            json={"checked_in_by": "P100"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["int_id"] == 4
    assert body["status"] == "Available"
    assert body["checked_in_by"] == "P100"

    _clear(db)


def test_team_checkin_404s_for_unknown_int_id():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/checkin/teams/999/checkin",
            json={"checked_in_by": "P100"},
        )
    assert res.status_code == 404

    _clear(db)


def test_team_disband_resolves_by_int_id():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one(_live_created_team_doc(int_id=9, name="GT-9 Charlie"))

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/checkin/teams/9/disband",
            json={"disbanded_by": "P200"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["int_id"] == 9
    assert body["disbanded"] is True
    assert body["disbanded_by"] == "P200"

    _clear(db)


def test_list_teams_by_checkin_state_includes_int_id():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    db["teams"].insert_one(_live_created_team_doc(int_id=2, name="GT-2 Delta", status="Enroute"))

    app = create_app()
    with TestClient(app) as client:
        res = client.get(
            f"/api/incidents/{INCIDENT_ID}/checkin/teams/checked-state",
            params={"checked_in": False, "include_disbanded": False},
        )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["int_id"] == 2
    assert rows[0]["name"] == "GT-2 Delta"

    _clear(db)
