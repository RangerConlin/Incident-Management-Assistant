"""Router tests for canonical Intel clue storage."""
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


INCIDENT_ID = "TEST_INTEL_CLUES_CANONICAL"
LEGACY_CLUES_COLLECTION = "intel_clues"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.INTEL_ITEMS].delete_many({})
    db[IncidentCollections.INTEL_LOG].delete_many({})
    db[LEGACY_CLUES_COLLECTION].delete_many({})


def test_clues_are_canonical_intel_items_not_legacy_clue_docs() -> None:
    _clear()
    app = create_app()

    with TestClient(app) as client:
        create_response = client.post(
            f"/api/incidents/{INCIDENT_ID}/intel/items",
            json={
                "item_type": "Clue",
                "title": "Boot print",
                "status": "Active",
                "priority": "Medium",
                "confidence": "Unconfirmed",
                "trend": "Unknown",
                "location_text": "Trail junction",
                "linked_team_ids": [7],
                "notes": "Found near creek",
                "created_by": "radio",
            },
        )
        assert create_response.status_code == 201
        clue = create_response.json()
        assert clue["item_type"] == "Clue"
        assert clue["linked_team_ids"] == [7]

        obs_response = client.post(
            f"/api/incidents/{INCIDENT_ID}/intel/items/{clue['id']}/observations",
            json={
                "observed_at": "2026-07-12T12:00:00+00:00",
                "observer": "radio",
                "source_team": "Team 7",
                "source_team_id": 7,
                "status": "Active",
                "severity": "Unknown",
                "confidence": "Unconfirmed",
                "summary": "Boot print",
                "detailed_notes": "Found near creek",
                "location_text": "Trail junction",
                "actor": "radio",
            },
        )
        assert obs_response.status_code == 201
        assert obs_response.json()["observations"][0]["summary"] == "Boot print"

        legacy_response = client.get(f"/api/incidents/{INCIDENT_ID}/intel/clues")
        assert legacy_response.status_code == 404

    db = get_incident_db(INCIDENT_ID)
    saved = db[IncidentCollections.INTEL_ITEMS].find_one({"_id": clue["id"]})
    assert saved is not None
    assert saved["item_type"] == "Clue"
    assert saved["observations"][0]["source_team_id"] == 7
    assert db[LEGACY_CLUES_COLLECTION].count_documents({}) == 0

    _clear()
