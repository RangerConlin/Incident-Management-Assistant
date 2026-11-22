"""Router tests for the master checklist-template catalog."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


def _clear() -> None:
    get_master_db()[MasterCollections.CHECKLIST_TEMPLATES].delete_many({})


def _template_body(**overrides) -> dict:
    body = {
        "name": "Vehicle Pre-Trip Inspection",
        "category": "Logistics",
        "description": "Pre-trip safety inspection",
        "instructions": "Complete before every dispatch.",
        "sections": [
            {
                "id": "sec-1",
                "name": "Exterior",
                "items": [
                    {
                        "id": "item-lights",
                        "item_type": "checkbox",
                        "label": "Lights functional",
                        "required": True,
                        "na_allowed": False,
                    },
                    {
                        "id": "item-tires",
                        "item_type": "pass_fail_na",
                        "label": "Tire condition",
                        "required": True,
                        "na_allowed": True,
                    },
                ],
            }
        ],
        "active": True,
    }
    body.update(overrides)
    return body


def test_create_and_get_checklist_template() -> None:
    _clear()
    with TestClient(create_app()) as client:
        created = client.post("/api/checklist-templates", json=_template_body())
        assert created.status_code == 201
        body = created.json()
        assert body["id"] == 1
        assert body["category"] == "Logistics"
        assert len(body["sections"][0]["items"]) == 2

        fetched = client.get(f"/api/checklist-templates/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == "Vehicle Pre-Trip Inspection"
    _clear()


def test_duplicate_item_id_across_sections_is_rejected() -> None:
    _clear()
    with TestClient(create_app()) as client:
        body = _template_body(
            sections=[
                {"id": "sec-1", "name": "A", "items": [{"id": "dup", "item_type": "checkbox", "label": "x"}]},
                {"id": "sec-2", "name": "B", "items": [{"id": "dup", "item_type": "checkbox", "label": "y"}]},
            ]
        )
        response = client.post("/api/checklist-templates", json=body)
        assert response.status_code == 422
    _clear()


def test_selection_item_requires_options() -> None:
    _clear()
    with TestClient(create_app()) as client:
        body = _template_body(
            sections=[
                {
                    "id": "sec-1",
                    "name": "A",
                    "items": [{"id": "sel-1", "item_type": "selection", "label": "Pick one", "options": []}],
                }
            ]
        )
        response = client.post("/api/checklist-templates", json=body)
        assert response.status_code == 422
    _clear()


def test_categories_endpoint_and_default_category() -> None:
    _clear()
    with TestClient(create_app()) as client:
        client.post("/api/checklist-templates", json=_template_body(category="Logistics"))
        client.post("/api/checklist-templates", json=_template_body(name="Other Template", category=""))
        categories = client.get("/api/checklist-templates/categories")
        assert categories.status_code == 200
        assert "Logistics" in categories.json()
        assert "Other" in categories.json()
    _clear()


def test_clone_and_set_active() -> None:
    _clear()
    with TestClient(create_app()) as client:
        created = client.post("/api/checklist-templates", json=_template_body())
        template_id = created.json()["id"]

        cloned = client.post(f"/api/checklist-templates/{template_id}/clone")
        assert cloned.status_code == 201
        assert cloned.json()["name"] == "Vehicle Pre-Trip Inspection Copy 1"

        deactivated = client.patch(
            f"/api/checklist-templates/{template_id}/active", json={"active": False}
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["active"] is False

        active_only = client.get("/api/checklist-templates")
        assert template_id not in [row["id"] for row in active_only.json()]

        with_inactive = client.get("/api/checklist-templates", params={"include_inactive": True})
        assert template_id in [row["id"] for row in with_inactive.json()]
    _clear()
