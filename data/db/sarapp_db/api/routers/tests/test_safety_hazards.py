"""Router-level tests for the canonical Hazard Register (Safety Risk Manager)
endpoints in data/db/sarapp_db/api/routers/safety.py.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db


INCIDENT_ID = "TEST_SAFETY_HAZARDS"


def _clear():
    get_incident_db(INCIDENT_ID)[IncidentCollections.HAZARDS].delete_many({})


def test_create_hazard_computes_spe_server_side():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Steep terrain",
                "op_period_ids": [1],
                "spe_initial": {"severity": 5, "probability": 5, "exposure": 4},
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["spe_initial"]["score"] == 100
        assert body["spe_initial"]["band"] == "Very High"
        assert body["spe_initial"]["action"] == "Discontinue / Stop"
        assert body["spe_residual"] is None
    _clear()


def test_invalid_spe_input_rejected():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Bad input",
                "op_period_ids": [1],
                "spe_initial": {"severity": 9, "probability": 1, "exposure": 1},
            },
        )
        assert res.status_code == 422
    _clear()


def test_get_update_delete_hazard():
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={"title": "Original", "op_period_ids": [1]},
        ).json()

        fetched = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}"
        )
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Original"

        patched = client.patch(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}",
            json={"title": "Renamed"},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Renamed"

        deleted = client.delete(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}"
        )
        assert deleted.status_code == 204

        missing = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}"
        )
        assert missing.status_code == 404
    _clear()
