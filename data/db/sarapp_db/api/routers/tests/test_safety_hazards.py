"""Router-level tests for the canonical incident hazard register endpoints."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db


INCIDENT_ID = "TEST_SAFETY_HAZARDS"


def _clear() -> None:
    get_incident_db(INCIDENT_ID)[IncidentCollections.HAZARDS].delete_many({})
    get_master_db()[MasterCollections.HAZARD_TYPES].delete_many({})


def _seed_hazard_type() -> None:
    get_master_db()[MasterCollections.HAZARD_TYPES].insert_one(
        {
            "id": 10,
            "name": "Heat Exposure",
            "category": "Environmental",
            "description": "Exposure to high heat conditions.",
            "aliases": ["Heat Stress"],
            "controls": ["Hydrate", "Work/rest cycle"],
            "ppe": ["Sun hat", "Cooling towel"],
            "standard_safety_language": "Watch crews for signs of heat illness.",
            "default_spe": {
                "severity": 4,
                "probability": 3,
                "exposure": 4,
                "score": 48,
                "band": "Substantial",
                "action": "Correction Required",
            },
            "active": True,
        }
    )


def test_create_incident_only_hazard_computes_spe_server_side() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Steep terrain",
                "category": "Terrain",
                "description": "Loose footing on a hillside.",
                "controls": ["Slow movement"],
                "ppe": ["Helmet"],
                "safety_language": "Use deliberate foot placement.",
                "default_spe": {"severity": 4, "probability": 3, "exposure": 3},
                "spe_initial": {"severity": 5, "probability": 5, "exposure": 4},
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["hazard_type_id"] is None
        assert body["default_spe"]["score"] == 36
        assert body["default_spe"]["band"] == "Possible"
        assert body["spe_initial"]["score"] == 100
        assert body["spe_initial"]["band"] == "Very High"
        assert body["spe_initial"]["action"] == "Discontinue / Stop"
        assert body["spe_residual"] is None
        assert body["op_period_ids"] == []
        assert body["task_ids"] == []
        assert body["team_ids"] == []
        assert body["work_assignment_ids"] == []
        assert body["hazard_zone_ids"] == []
    _clear()


def test_create_hazard_from_library_copies_matching_fields() -> None:
    _clear()
    _seed_hazard_type()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "library_hazard_type_id": 10,
                "spe_initial": {"severity": 3, "probability": 2, "exposure": 2},
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["hazard_type_id"] == 10
        assert body["title"] == "Heat Exposure"
        assert body["category"] == "Environmental"
        assert body["description"] == "Exposure to high heat conditions."
        assert body["controls"] == ["Hydrate", "Work/rest cycle"]
        assert body["ppe"] == ["Sun hat", "Cooling towel"]
        assert body["safety_language"] == "Watch crews for signs of heat illness."
        assert body["default_spe"]["score"] == 48
        assert body["default_spe"]["band"] == "Substantial"
    _clear()


def test_invalid_spe_input_rejected() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Bad input",
                "category": "Other",
                "default_spe": {"severity": 9, "probability": 1, "exposure": 1},
            },
        )
        assert res.status_code == 422
    _clear()


def test_get_update_delete_hazard() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Original",
                "category": "Operational",
                "default_spe": {"severity": 1, "probability": 1, "exposure": 1},
            },
        ).json()

        fetched = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}"
        )
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Original"

        patched = client.patch(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}",
            json={
                "title": "Renamed",
                "controls": ["Buddy check"],
                "spe_residual": {"severity": 1, "probability": 2, "exposure": 2},
            },
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Renamed"
        assert patched.json()["controls"] == ["Buddy check"]
        assert patched.json()["spe_residual"]["score"] == 4

        deleted = client.delete(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}"
        )
        assert deleted.status_code == 204

        missing = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created['id']}"
        )
        assert missing.status_code == 404
    _clear()
