import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository


class _TeamsRepository(BaseRepository):
    collection_name = "teams"


def test_snapshot_and_live_broadcast_on_write():
    incident_id = "TESTCACHE1"
    db = get_incident_db(incident_id)
    db["teams"].delete_many({})

    app = create_app()
    with TestClient(app) as client:
        # Empty snapshot before any writes
        res = client.get(f"/api/incidents/{incident_id}/snapshot", params={"collections": "teams"})
        assert res.status_code == 200
        assert res.json()["collections"]["teams"] == []

        with client.websocket_connect(f"/api/incidents/{incident_id}/ws") as ws:
            repo = _TeamsRepository(db)
            doc = repo.insert_one({"name": "Team 1"})

            event = ws.receive_json()
            assert event["collection"] == "teams"
            assert event["op"] == "created"
            assert event["id"] == doc["_id"]
            assert event["doc"]["name"] == "Team 1"

            repo.update_one(doc["_id"], {"name": "Team 1 Renamed"})
            event2 = ws.receive_json()
            assert event2["op"] == "updated"
            assert event2["doc"]["name"] == "Team 1 Renamed"

            repo.soft_delete(doc["_id"])
            event3 = ws.receive_json()
            assert event3["op"] == "deleted"

        res2 = client.get(f"/api/incidents/{incident_id}/snapshot", params={"collections": "teams"})
        assert res2.json()["collections"]["teams"] == []  # soft-deleted, excluded from snapshot

    db["teams"].delete_many({})
