"""Router tests for canonical ICS-214 entry storage."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient
from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

INCIDENT_ID = "TEST_ICS214_CANONICAL"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.ICS_214_ENTRIES].delete_many({})
    db[IncidentCollections.ICS_214_LOG_DEFINITIONS].delete_many({})
    db["ics_214_logs"].delete_many({})


def test_mobile_team_log_writes_one_flat_associated_entry() -> None:
    _clear()
    with TestClient(create_app()) as client:
        response = client.post(
            f"/api/incidents/{INCIDENT_ID}/mobile/teams/12/log",
            json={"text": "Team departed base", "actor_user_id": "ops",
                  "timestamp_utc": "2026-07-12T12:00:00+00:00"},
        )
        assert response.status_code == 201
        entry = response.json()
        assert entry["team_ids"] == [12]
        assert client.get(f"/api/incidents/{INCIDENT_ID}/ics214/streams").status_code == 404

    db = get_incident_db(INCIDENT_ID)
    stored = db[IncidentCollections.ICS_214_ENTRIES].find_one({"entry_id": entry["id"]})
    assert stored is not None and "entries" not in stored
    assert db["ics_214_logs"].count_documents({}) == 0
    _clear()


def test_team_expansion_and_operational_period_filter_are_derived() -> None:
    _clear()
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.TEAMS].insert_one({
        "_id": "team-4", "int_id": 4, "name": "Alpha",
        "member_person_records": [101, 102],
    })
    db[IncidentCollections.OPERATIONAL_PERIODS].insert_one({
        "_id": "op-1", "int_id": 1, "number": 1,
        "start_time": "2026-07-12T08:00:00+00:00",
        "end_time": "2026-07-12T20:00:00+00:00",
        "deleted": False,
    })
    with TestClient(create_app()) as client:
        inside = client.post(
            f"/api/incidents/{INCIDENT_ID}/ics214/entries",
            json={"text": "Inside OP", "occurred_at": "2026-07-12T12:00:00+00:00",
                  "team_ids": [4], "expand_team_members": True},
        )
        assert inside.status_code == 201
        assert inside.json()["person_ids"] == [101, 102]
        outside = client.post(
            f"/api/incidents/{INCIDENT_ID}/ics214/entries",
            json={"text": "Outside OP", "occurred_at": "2026-07-13T12:00:00+00:00",
                  "team_ids": [4]},
        )
        assert outside.status_code == 201
        rows = client.get(
            f"/api/incidents/{INCIDENT_ID}/ics214/entries",
            params={"operational_period_id": 1, "team_id": 4},
        ).json()
        assert [row["text"] for row in rows] == ["Inside OP"]
    db[IncidentCollections.TEAMS].delete_many({"_id": "team-4"})
    db[IncidentCollections.OPERATIONAL_PERIODS].delete_many({"_id": "op-1"})
    _clear()
