"""Guard that work_assignments.py writes through WorkAssignmentsRepository
(BaseRepository) instead of a raw pymongo collection. Exercises create/update
round trip and confirms embedded sub-resource writes ($push/$pull on
resources/hazards) still broadcast over the incident WebSocket.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections


INCIDENT_ID = "TEST_WORK_ASSIGNMENTS_BROADCAST"
COL = IncidentCollections.WORK_ASSIGNMENTS
BASE = f"/api/incidents/{INCIDENT_ID}/planning/work-assignments"


def _clear(db):
    db[COL].delete_many({})


def test_create_update_and_embedded_writes_broadcast():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/incidents/{INCIDENT_ID}/ws") as ws:
            res = client.post(BASE, json={"assignment_name": "Strike Team 1"})
            assert res.status_code == 201, res.text
            wa = res.json()
            assert wa["assignment_name"] == "Strike Team 1"

            event = ws.receive_json()
            assert event["collection"] == COL
            assert event["op"] == "created"
            assert event["doc"]["assignment_name"] == "Strike Team 1"

            res = client.patch(f"{BASE}/{wa['id']}", json={"assignment_name": "Strike Team 1 Renamed"})
            assert res.status_code == 200, res.text
            assert res.json()["assignment_name"] == "Strike Team 1 Renamed"

            event2 = ws.receive_json()
            assert event2["op"] == "updated"
            assert event2["doc"]["assignment_name"] == "Strike Team 1 Renamed"

            # $push on the embedded `resources` array.
            res = client.post(f"{BASE}/{wa['id']}/resources", json={"resource_type_text": "Engine"})
            assert res.status_code == 201, res.text
            resource = res.json()
            assert resource["resource_type_text"] == "Engine"

            event3 = ws.receive_json()
            assert event3["op"] == "updated"
            assert len(event3["doc"]["resources"]) == 1

            # $pull on the same embedded array.
            res = client.delete(f"{BASE}/{wa['id']}/resources/{resource['id']}")
            assert res.status_code == 204, res.text

            event4 = ws.receive_json()
            assert event4["op"] == "updated"
            assert event4["doc"]["resources"] == []

            # $push on the embedded `hazards` array.
            res = client.post(f"{BASE}/{wa['id']}/hazards", json={"hazard_type_text": "Heat"})
            assert res.status_code == 201, res.text
            hazard = res.json()

            event5 = ws.receive_json()
            assert event5["op"] == "updated"
            assert len(event5["doc"]["hazards"]) == 1

        res = client.get(f"{BASE}/{wa['id']}")
        assert res.status_code == 200
        doc = res.json()
        assert doc["assignment_name"] == "Strike Team 1 Renamed"
        assert len(doc["hazards"]) == 1

    # Writes went through BaseRepository: the document has created_at/
    # updated_at and a plain string _id, stamped by insert_one/update_one
    # rather than hand-built in the router.
    stored = db[COL].find_one({"incident_id": INCIDENT_ID})
    assert isinstance(stored["_id"], str)
    assert stored.get("created_at")
    assert stored.get("updated_at")

    _clear(db)
