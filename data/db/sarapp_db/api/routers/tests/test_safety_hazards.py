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


def test_create_incident_only_hazard_computes_default_and_residual_spe_server_side() -> None:
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
                "default_spe": {"severity": 5, "probability": 5, "exposure": 4},
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["hazard_type_id"] is None
        assert body["default_spe"]["score"] == 100
        assert body["default_spe"]["band"] == "Very High"
        assert body["default_spe"]["action"] == "Discontinue / Stop"
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


def test_hazard_zone_ids_can_store_multiple_zones_and_filter_by_zone() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Mapped hazard",
                "category": "Environmental",
                "default_spe": {"severity": 2, "probability": 3, "exposure": 4},
                "hazard_zone_ids": [101, 102, 101],
            },
        )
        assert created.status_code == 201
        assert created.json()["hazard_zone_ids"] == [101, 102]

        patched = client.patch(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{created.json()['id']}",
            json={"hazard_zone_ids": [102, 103]},
        )
        assert patched.status_code == 200
        assert patched.json()["hazard_zone_ids"] == [102, 103]

        by_zone = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            params={"hazard_zone_id": 103},
        )
        assert by_zone.status_code == 200
        assert [row["id"] for row in by_zone.json()] == [created.json()["id"]]

        no_match = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            params={"hazard_zone_id": 101},
        )
        assert no_match.status_code == 200
        assert no_match.json() == []
    _clear()


def test_hazard_links_can_store_multiple_backend_relationships_and_filter_by_work_assignment() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            json={
                "title": "Linked hazard",
                "category": "Operational",
                "default_spe": {"severity": 2, "probability": 2, "exposure": 2},
                "op_period_ids": [1, 2, 2],
                "work_assignment_ids": [42, 42],
                "team_ids": [7],
                "task_ids": [9],
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["op_period_ids"] == [1, 2]
        assert body["work_assignment_ids"] == [42]
        assert body["team_ids"] == [7]
        assert body["task_ids"] == [9]

        patched = client.patch(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards/{body['id']}",
            json={"work_assignment_ids": [42, 43]},
        )
        assert patched.status_code == 200
        assert patched.json()["work_assignment_ids"] == [42, 43]

        by_assignment = client.get(
            f"/api/incidents/{INCIDENT_ID}/safety/hazards",
            params={"work_assignment_id": 43},
        )
        assert by_assignment.status_code == 200
        assert [row["id"] for row in by_assignment.json()] == [body["id"]]
    _clear()
