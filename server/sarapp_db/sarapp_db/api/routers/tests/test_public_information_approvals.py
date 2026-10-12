"""Router tests for embedded PIO message approvals."""
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


INCIDENT_ID = "TEST_PIO_APPROVALS"
LEGACY_APPROVALS_COLLECTION = "pio_approvals"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.PIO_MESSAGES].delete_many({})
    db[IncidentCollections.PIO_MESSAGE_REVISIONS].delete_many({})
    db[LEGACY_APPROVALS_COLLECTION].delete_many({})


def test_message_status_embeds_approval_history_on_message() -> None:
    _clear()
    app = create_app()

    with TestClient(app) as client:
        create_response = client.post(
            f"/api/incidents/{INCIDENT_ID}/public-information/messages",
            json={
                "title": "Public update",
                "type": "Press Release",
                "audience": "Public",
                "priority": "Normal",
                "status": "Draft",
                "body": "Update body",
            },
        )
        assert create_response.status_code == 201
        message = create_response.json()
        assert message["approvals"] == []

        status_response = client.post(
            f"/api/incidents/{INCIDENT_ID}/public-information/messages/{message['id']}/status",
            json={"status": "Approved", "user": "lead", "comment": "Looks good"},
        )
        assert status_response.status_code == 200
        updated = status_response.json()
        assert updated["approved_by"] == "lead"
        assert len(updated["approvals"]) == 1
        approval = updated["approvals"][0]
        assert approval["action"] == "Approved"
        assert approval["comment"] == "Looks good"
        assert approval["reviewer_name"] == "lead"

        list_response = client.get(
            f"/api/incidents/{INCIDENT_ID}/public-information/messages/{message['id']}/approvals"
        )
        assert list_response.status_code == 200
        assert list_response.json() == [approval]

    db = get_incident_db(INCIDENT_ID)
    saved = db[IncidentCollections.PIO_MESSAGES].find_one({"id": message["id"]})
    assert saved is not None
    assert saved["approvals"] == [approval]
    assert db[LEGACY_APPROVALS_COLLECTION].count_documents({}) == 0

    _clear()
