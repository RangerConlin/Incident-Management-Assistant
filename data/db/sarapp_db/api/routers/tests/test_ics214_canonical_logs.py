"""Router tests for canonical ICS-214 activity log storage."""
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
LEGACY_UNIT_LOGS_COLLECTION = "unit_logs"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.ICS_214_LOGS].delete_many({})
    db[LEGACY_UNIT_LOGS_COLLECTION].delete_many({})


def test_mobile_team_log_writes_ics214_logs_not_unit_logs() -> None:
    _clear()
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            f"/api/incidents/{INCIDENT_ID}/mobile/teams/12/log",
            json={
                "text": "Team departed base",
                "actor_user_id": "ops",
                "timestamp_utc": "2026-07-12T12:00:00+00:00",
                "critical_flag": False,
                "tags": ["movement"],
            },
        )
        assert response.status_code == 201
        entry = response.json()
        assert entry["text"] == "Team departed base"
        assert entry["source"] == "mobile"

        stream_response = client.get(f"/api/incidents/{INCIDENT_ID}/ics214/streams")
        assert stream_response.status_code == 200
        streams = stream_response.json()
        assert [stream["name"] for stream in streams] == ["Team 12"]

    db = get_incident_db(INCIDENT_ID)
    stream = db[IncidentCollections.ICS_214_LOGS].find_one({"incident_id": INCIDENT_ID, "name": "Team 12"})
    assert stream is not None
    assert stream["entries"][0]["text"] == "Team departed base"
    assert db[LEGACY_UNIT_LOGS_COLLECTION].count_documents({}) == 0

    _clear()
