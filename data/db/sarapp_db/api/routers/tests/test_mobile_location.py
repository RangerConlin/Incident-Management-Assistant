"""Team-location tracking (GIS module Phase 1 — see tracking_plan.md in
ICS-Mobile-App for the full design).

Covers: leader ping always overwrites, non-leader ping is ignored while the
leader is the current source, non-leader ping is accepted once the leader
isn't the source, an unchecked-in person's ping is silently ignored, stop
only clears when the stopper is the current source, the desktop-facing
team-locations GET, and the server-side auto-clear on demobilization.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db


INCIDENT_ID = "TEST_MOBILE_LOCATION"
LEADER_ID = 100
MEMBER_ID = 101
OUTSIDER_ID = 102  # registered + checked in, but not on the team's roster
TOKEN_LEADER = "tok-mobile-loc-leader"
TOKEN_MEMBER = "tok-mobile-loc-member"
TOKEN_OUTSIDER = "tok-mobile-loc-outsider"
TOKEN_UNCHECKED = "tok-mobile-loc-unchecked"
UNCHECKED_ID = 103  # registered token, no resource_status doc


def _teams_col():
    return get_incident_db(INCIDENT_ID)["teams"]


def _resource_status_col():
    return get_incident_db(INCIDENT_ID)["resource_status"]


def _tokens_col():
    return get_master_db()[MasterCollections.PUSH_TOKENS]


def _clear():
    _teams_col().delete_many({})
    _resource_status_col().delete_many({})
    _tokens_col().delete_many({"token": {"$in": [
        TOKEN_LEADER, TOKEN_MEMBER, TOKEN_OUTSIDER, TOKEN_UNCHECKED,
    ]}})


def _seed():
    _teams_col().insert_one({
        "int_id": 1,
        "name": "Team 1",
        "team_leader": LEADER_ID,
        "members_json": f"[{LEADER_ID}, {MEMBER_ID}]",
        "current_location_lat": None,
        "current_location_lon": None,
        "current_location_updated_at": None,
        "current_location_person_record": None,
    })
    for person_record in (LEADER_ID, MEMBER_ID, OUTSIDER_ID):
        _resource_status_col().insert_one({
            "entity_type": "personnel",
            "record_id": person_record,
            "status": "Available",
            "deleted": False,
        })
    _tokens_col().insert_one({"token": TOKEN_LEADER, "person_record": LEADER_ID, "incident_id": INCIDENT_ID})
    _tokens_col().insert_one({"token": TOKEN_MEMBER, "person_record": MEMBER_ID, "incident_id": INCIDENT_ID})
    _tokens_col().insert_one({"token": TOKEN_OUTSIDER, "person_record": OUTSIDER_ID, "incident_id": INCIDENT_ID})
    _tokens_col().insert_one({"token": TOKEN_UNCHECKED, "person_record": UNCHECKED_ID, "incident_id": INCIDENT_ID})


def test_leader_ping_overwrites():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/mobile/location", json={"token": TOKEN_LEADER, "lat": 1.0, "lon": 2.0})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "recorded": True}
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] == 1.0
    assert team["current_location_lon"] == 2.0
    assert team["current_location_person_record"] == LEADER_ID
    _clear()


def test_non_leader_ping_ignored_while_leader_is_source():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        client.post("/api/mobile/location", json={"token": TOKEN_LEADER, "lat": 1.0, "lon": 2.0})
        res = client.post("/api/mobile/location", json={"token": TOKEN_MEMBER, "lat": 9.0, "lon": 9.0})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "recorded": False}
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] == 1.0
    assert team["current_location_person_record"] == LEADER_ID
    _clear()


def test_non_leader_ping_accepted_once_leader_not_source():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/mobile/location", json={"token": TOKEN_MEMBER, "lat": 3.0, "lon": 4.0})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "recorded": True}
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] == 3.0
    assert team["current_location_person_record"] == MEMBER_ID
    _clear()


def test_unchecked_in_person_ping_silently_ignored():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/mobile/location", json={"token": TOKEN_UNCHECKED, "lat": 5.0, "lon": 6.0})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "recorded": False}
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] is None
    _clear()


def test_person_not_on_any_team_roster_ping_silently_ignored():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/mobile/location", json={"token": TOKEN_OUTSIDER, "lat": 7.0, "lon": 8.0})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "recorded": False}
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] is None
    _clear()


def test_stop_clears_only_when_stopper_is_current_source():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        client.post("/api/mobile/location", json={"token": TOKEN_MEMBER, "lat": 3.0, "lon": 4.0})

        # Leader isn't the current source (member is) — leader's stop is a no-op.
        res_noop = client.post("/api/mobile/location/stop", json={"token": TOKEN_LEADER})
        assert res_noop.json() == {"ok": True, "cleared": False}
        team = _teams_col().find_one({"int_id": 1})
        assert team["current_location_person_record"] == MEMBER_ID

        # Member is the current source — member's stop clears it.
        res_clear = client.post("/api/mobile/location/stop", json={"token": TOKEN_MEMBER})
        assert res_clear.json() == {"ok": True, "cleared": True}
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] is None
    assert team["current_location_person_record"] is None
    _clear()


def test_get_team_locations_returns_active_dot():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        client.post("/api/mobile/location", json={"token": TOKEN_LEADER, "lat": 1.0, "lon": 2.0})
        res = client.get(f"/api/incidents/{INCIDENT_ID}/team-locations")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["team_id"] == 1
    assert rows[0]["lat"] == 1.0
    assert rows[0]["lon"] == 2.0
    _clear()


def test_get_team_locations_omits_teams_with_no_location():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/team-locations")
    assert res.status_code == 200
    assert res.json() == []
    _clear()


def test_demobilization_auto_clears_tracking():
    _clear()
    _seed()
    app = create_app()
    with TestClient(app) as client:
        client.post("/api/mobile/location", json={"token": TOKEN_LEADER, "lat": 1.0, "lon": 2.0})
        res = client.patch(
            f"/api/incidents/{INCIDENT_ID}/checkin/{LEADER_ID}/status",
            json={"status": "Demobilized"},
        )
    assert res.status_code == 200
    team = _teams_col().find_one({"int_id": 1})
    assert team["current_location_lat"] is None
    assert team["current_location_person_record"] is None
    _clear()
