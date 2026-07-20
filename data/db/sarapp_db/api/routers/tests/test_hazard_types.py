from __future__ import annotations

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


def _clear() -> None:
    get_master_db()[MasterCollections.HAZARD_TYPES].delete_many({})


def test_create_hazard_type_computes_default_spe() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/hazard-types",
            json={
                "name": "Heat Exposure",
                "category": "Environmental",
                "description": "Exposure to hot conditions.",
                "aliases": ["Heat Stress", "Overheating"],
                "controls": ["Hydrate", "Work/rest cycles"],
                "ppe": ["Cooling towel", "Sun hat"],
                "standard_safety_language": "Monitor crews for heat illness.",
                "default_spe": {"severity": 4, "probability": 3, "exposure": 4},
                "active": True,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == 1
        assert body["controls"] == ["Hydrate", "Work/rest cycles"]
        assert body["ppe"] == ["Cooling towel", "Sun hat"]
        assert body["default_spe"]["score"] == 48
        assert body["default_spe"]["band"] == "Substantial"
        assert body["default_spe"]["action"] == "Correction Required"
    _clear()


def test_invalid_default_spe_is_rejected() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/hazard-types",
            json={
                "name": "Water Hazard",
                "category": "Water",
                "description": "Swift water exposure.",
                "aliases": [],
                "controls": ["Wear PFD"],
                "ppe": ["PFD"],
                "standard_safety_language": "Stay out of moving water.",
                "default_spe": {"severity": 9, "probability": 1, "exposure": 1},
                "active": True,
            },
        )
        assert response.status_code == 422
    _clear()


def test_search_uses_new_fields() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            "/api/hazard-types",
            json={
                "name": "Vehicle Movement",
                "category": "Vehicle",
                "description": "Moving vehicles near crews.",
                "aliases": ["Traffic"],
                "controls": ["Spotter", "Cone the area"],
                "ppe": ["Hi-vis vest"],
                "standard_safety_language": "Maintain positive vehicle control.",
                "default_spe": {"severity": 3, "probability": 3, "exposure": 3},
                "active": True,
            },
        )
        assert created.status_code == 201
        response = client.get("/api/hazard-types/search", params={"q": "spotter"})
        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 1,
                "name": "Vehicle Movement",
                "category": "Vehicle",
                "default_spe_band": "Possible",
                "matched_on": "control",
            }
        ]
    _clear()
