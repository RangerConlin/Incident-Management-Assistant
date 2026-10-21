"""Router + pure-logic tests for Resource Packages (Stage 3).

`test_counts_*` exercise `_counts` directly (no DB). Everything else drives
the real FastAPI app and requires a live MongoDB via SARAPP_MONGO_URI.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers.resource_packages import _counts
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


def test_counts_tallies_each_resource_kind():
    resources = [
        {"resource_type": "personnel", "resource_id": 1},
        {"resource_type": "personnel", "resource_id": 2},
        {"resource_type": "vehicle", "resource_id": 3},
        {"resource_type": "equipment", "resource_id": 4},
    ]
    counts = _counts(resources)
    assert counts["personnel"] == 2
    assert counts["vehicle"] == 1
    assert counts["equipment"] == 1
    assert counts["aircraft"] == 0


def test_counts_empty_list():
    counts = _counts([])
    assert all(v == 0 for v in counts.values())


# ---------------------------------------------------------------------------
# Router integration (requires live MongoDB)
# ---------------------------------------------------------------------------

_PERSON_IDS = [881001, 881002]
_VEHICLE_ID = 881010


def _reset():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].delete_many({"person_record": {"$in": _PERSON_IDS}})
    master[MasterCollections.VEHICLES].delete_many({"vehicle_record": _VEHICLE_ID})
    master[MasterCollections.RESOURCE_PACKAGES].delete_many({"name": {"$regex": "^Stage3 Test"}})


def _seed():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].insert_many(
        [{"person_record": pid, "name": f"Package Test Person {pid}"} for pid in _PERSON_IDS]
    )
    master[MasterCollections.VEHICLES].insert_one({"vehicle_record": _VEHICLE_ID, "vehicle_id": "PKG-V1"})


def test_create_package_with_mixed_resource_kinds_and_vacant_positions():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            payload = {
                "name": "Stage3 Test Ground Team",
                "owning_organization": "CAP Squadron 1",
                "default_team_designation": "GT-1",
                "resources": [
                    {"resource_type": "personnel", "resource_id": 881001, "membership": "fixed", "role": "Team Leader"},
                    {"resource_type": "vehicle", "resource_id": 881010, "membership": "fixed", "role": "Primary"},
                ],
                "required_positions": [
                    {"role": "Ground Team Member", "qualification": "GTM3", "quantity": 2},
                ],
                "minimum_quantities": [
                    {"description": "4 qualified personnel", "resource_kind": "personnel", "minimum_count": 4},
                ],
            }
            created = client.post("/api/resource-packages", json=payload)
            assert created.status_code == 201, created.text
            pkg = created.json()
            # Saveable while understaffed: required_positions vacant, minimum
            # of 4 personnel not met by only 1 fixed person.
            assert pkg["personnel_count"] == 1
            assert pkg["vehicle_count"] == 1
            assert pkg["required_positions"][0]["role"] == "Ground Team Member"

            fetched = client.get(f"/api/resource-packages/{pkg['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["name"] == "Stage3 Test Ground Team"
    finally:
        _reset()


def test_duplicate_resource_in_same_package_rejected():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            payload = {
                "name": "Stage3 Test Dup",
                "resources": [
                    {"resource_type": "personnel", "resource_id": 881001, "membership": "fixed"},
                    {"resource_type": "personnel", "resource_id": 881001, "membership": "preferred"},
                ],
            }
            response = client.post("/api/resource-packages", json=payload)
            assert response.status_code == 409
    finally:
        _reset()


def test_invalid_resource_reference_rejected():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            payload = {
                "name": "Stage3 Test Invalid",
                "resources": [{"resource_type": "personnel", "resource_id": 999999, "membership": "fixed"}],
            }
            response = client.post("/api/resource-packages", json=payload)
            assert response.status_code == 404
    finally:
        _reset()


def test_duplicate_package_action_and_archive():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            created = client.post("/api/resource-packages", json={"name": "Stage3 Test Archive Me"})
            pkg = created.json()

            dup = client.post(f"/api/resource-packages/{pkg['id']}/duplicate")
            assert dup.status_code == 201
            assert dup.json()["name"] == "Stage3 Test Archive Me Copy 1"

            archived = client.patch(f"/api/resource-packages/{pkg['id']}/active", json={"active": False})
            assert archived.status_code == 200
            assert archived.json()["is_active"] is False

            listed_active = client.get("/api/resource-packages", params={"active_filter": "Active"})
            assert pkg["id"] not in [p["id"] for p in listed_active.json()]
    finally:
        _reset()


def test_packages_for_resource_endpoint():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            client.post(
                "/api/resource-packages",
                json={
                    "name": "Stage3 Test Lookup",
                    "resources": [{"resource_type": "personnel", "resource_id": 881001, "membership": "fixed"}],
                },
            )
            response = client.get("/api/resource-packages/for-resource/personnel/881001")
            assert response.status_code == 200
            names = [p["name"] for p in response.json()]
            assert "Stage3 Test Lookup" in names
    finally:
        _reset()
