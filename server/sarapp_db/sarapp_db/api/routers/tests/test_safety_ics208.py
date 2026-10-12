"""Router-level tests for ICS-208 incident documents."""
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


INCIDENT_ID = "TEST_SAFETY_ICS208"


def _clear() -> None:
    get_incident_db(INCIDENT_ID)[IncidentCollections.ICS_208_INSTANCES].delete_many({})


def test_upsert_ics208_stamps_created_and_updated_times() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.put(
            f"/api/incidents/{INCIDENT_ID}/safety/ics208",
            json={
                "op_period": 3,
                "safety_message": "Initial draft.",
            },
        )
        assert created.status_code == 200
        created_body = created.json()
        assert created_body["created_at"]
        assert created_body["updated_at"]
        assert created_body["created_at"] == created_body["updated_at"]

        updated = client.put(
            f"/api/incidents/{INCIDENT_ID}/safety/ics208",
            json={
                "op_period": 3,
                "safety_message": "Revised draft.",
            },
        )
        assert updated.status_code == 200
        updated_body = updated.json()
        assert updated_body["created_at"] == created_body["created_at"]
        assert updated_body["updated_at"] >= created_body["updated_at"]
        assert updated_body["safety_message"] == "Revised draft."
    _clear()
