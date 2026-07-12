"""Router tests for legacy /resources endpoints backed by resource_status."""
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


INCIDENT_ID = "TEST_INCIDENT_RESOURCES"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.RESOURCE_STATUS].delete_many({})


def test_resources_delete_transitions_resource_status() -> None:
    _clear()
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.RESOURCE_STATUS].insert_one(
        {
            "_id": "rs-vehicle-7",
            "entity_type": "vehicle",
            "record_id": 7,
            "resource_id": "V-7",
            "resource_name": "Vehicle 7",
            "resource_type": "Vehicle",
            "status": "Checked In",
            "checked_in_time": "2026-07-12T10:00:00+00:00",
            "assigned_to": "Staging",
            "assignment_reference": "Division A",
            "status_log": [],
            "deleted": False,
        }
    )
    app = create_app()
    with TestClient(app) as client:
        before = client.get(f"/api/incidents/{INCIDENT_ID}/resources", params={"resource_type": "vehicle"})
        assert before.status_code == 200
        assert [row["record_id"] for row in before.json()] == [7]

        response = client.delete(f"/api/incidents/{INCIDENT_ID}/resources/vehicle/7")
        assert response.status_code == 204

        after = client.get(f"/api/incidents/{INCIDENT_ID}/resources", params={"resource_type": "vehicle"})
        assert after.status_code == 200
        assert after.json() == []

        repeated = client.delete(f"/api/incidents/{INCIDENT_ID}/resources/vehicle/7")
        assert repeated.status_code == 404

    current = db[IncidentCollections.RESOURCE_STATUS].find_one({"_id": "rs-vehicle-7"})
    assert current is not None
    assert current["status"] == "Demobilized"
    assert current["assigned_to"] is None
    assert current["assignment_reference"] is None
    assert "checked_in_time" not in current
    assert current["checked_out_time"]
    assert current["status_log"][-1]["changed_by"] == "Check-Out"

    _clear()


def test_resources_list_excludes_closed_statuses() -> None:
    _clear()
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.RESOURCE_STATUS].insert_many(
        [
            {
                "_id": "active",
                "entity_type": "equipment",
                "record_id": 1,
                "resource_name": "Radio Cache",
                "status": "Available",
                "deleted": False,
            },
            {
                "_id": "closed",
                "entity_type": "equipment",
                "record_id": 2,
                "resource_name": "Old Cache",
                "status": "Demobilized",
                "deleted": False,
            },
        ]
    )

    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/incidents/{INCIDENT_ID}/resources", params={"resource_type": "equipment"})

    assert response.status_code == 200
    assert [row["record_id"] for row in response.json()] == [1]

    _clear()
