"""Router tests for PIO misinformation timeline storage."""
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


INCIDENT_ID = "TEST_PIO_MISINFO"
LEGACY_TIMELINE_COLLECTION = "pio_misinformation_timeline"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.PIO_MISINFORMATION_ITEMS].delete_many({})
    db[LEGACY_TIMELINE_COLLECTION].delete_many({})


def test_misinformation_timeline_embeds_on_item_not_legacy_collection() -> None:
    _clear()
    app = create_app()

    with TestClient(app) as client:
        item_response = client.post(
            f"/api/incidents/{INCIDENT_ID}/public-information/records/pio_misinformation_items",
            json={
                "claim_rumor": "False shelter rumor",
                "severity": "Moderate",
                "status": "Monitoring",
                "response_decision": "Correct",
            },
        )
        assert item_response.status_code == 201
        item = item_response.json()
        assert item["timeline"] == []

        add_response = client.post(
            f"/api/incidents/{INCIDENT_ID}/public-information/misinformation/{item['id']}/timeline",
            json={"event_text": "Posted corrective message", "user": "pio"},
        )
        assert add_response.status_code == 201
        event = add_response.json()
        assert event["id"] == 1
        assert event["event_text"] == "Posted corrective message"
        assert event["created_by"] == "pio"

        list_response = client.get(
            f"/api/incidents/{INCIDENT_ID}/public-information/misinformation/{item['id']}/timeline"
        )
        assert list_response.status_code == 200
        assert list_response.json() == [event]

    db = get_incident_db(INCIDENT_ID)
    saved = db[IncidentCollections.PIO_MISINFORMATION_ITEMS].find_one({"id": item["id"]})
    assert saved is not None
    assert saved["timeline"] == [event]
    assert saved["last_update"] == event["event_time"]
    assert db[LEGACY_TIMELINE_COLLECTION].count_documents({}) == 0

    _clear()
