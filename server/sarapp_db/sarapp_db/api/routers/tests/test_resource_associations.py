"""Router + pure-logic tests for Resource Associations (Stage 2).

`test_find_path_*` exercise the cycle-detection graph search directly and
need no database. Every other test drives the real FastAPI app end to end
and requires a live MongoDB reachable via SARAPP_MONGO_URI, matching this
repo's existing router-test convention.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.api.routers.resource_associations import find_path
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db


# ---------------------------------------------------------------------------
# Pure logic: cycle detection (no DB)
# ---------------------------------------------------------------------------

def test_find_path_detects_direct_and_transitive_reachability():
    edges = [
        (("personnel", 1), ("vehicle", 2)),
        (("vehicle", 2), ("equipment", 3)),
    ]
    assert find_path(edges, ("personnel", 1), ("equipment", 3)) is True
    assert find_path(edges, ("equipment", 3), ("personnel", 1)) is False


def test_find_path_same_node_is_trivially_reachable():
    assert find_path([], ("personnel", 1), ("personnel", 1)) is True


def test_find_path_no_edges_means_unreachable():
    assert find_path([], ("personnel", 1), ("vehicle", 2)) is False


# ---------------------------------------------------------------------------
# Router integration (requires live MongoDB)
# ---------------------------------------------------------------------------

_PERSON = {"person_record": 880001, "name": "Assoc Test Person"}
_VEHICLE = {"vehicle_record": 880002, "vehicle_id": "ASSOC-V1"}
_VEHICLE_2 = {"vehicle_record": 880003, "vehicle_id": "ASSOC-V2"}


def _reset():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].delete_many({"person_record": {"$in": [880001]}})
    master[MasterCollections.VEHICLES].delete_many({"vehicle_record": {"$in": [880002, 880003]}})
    master[MasterCollections.RESOURCE_ASSOCIATIONS].delete_many({})


def _seed():
    master = get_master_db()
    master[MasterCollections.PERSONNEL].insert_one(dict(_PERSON))
    master[MasterCollections.VEHICLES].insert_one(dict(_VEHICLE))
    master[MasterCollections.VEHICLES].insert_one(dict(_VEHICLE_2))


def test_create_list_and_remove_association():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            payload = {
                "source": {"resource_type": "personnel", "resource_id": 880001},
                "target": {"resource_type": "vehicle", "resource_id": 880002},
                "association_type": "Assigned",
                "notes": "Primary driver",
            }
            created = client.post("/api/resource-associations", json=payload)
            assert created.status_code == 201, created.text
            assoc = created.json()
            assert assoc["source_label"] == "Assoc Test Person"
            assert assoc["target_label"] == "ASSOC-V1"

            listed = client.get(
                "/api/resource-associations",
                params={"resource_type": "personnel", "resource_id": 880001},
            )
            assert listed.status_code == 200
            assert len(listed.json()) == 1

            deleted = client.delete(f"/api/resource-associations/{assoc['id']}")
            assert deleted.status_code == 204

            listed_after = client.get(
                "/api/resource-associations",
                params={"resource_type": "personnel", "resource_id": 880001},
            )
            assert listed_after.json() == []
    finally:
        _reset()


def test_duplicate_association_is_rejected():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            payload = {
                "source": {"resource_type": "personnel", "resource_id": 880001},
                "target": {"resource_type": "vehicle", "resource_id": 880002},
                "association_type": "Assigned",
            }
            first = client.post("/api/resource-associations", json=payload)
            assert first.status_code == 201
            second = client.post("/api/resource-associations", json=payload)
            assert second.status_code == 409
    finally:
        _reset()


def test_invalid_reference_is_rejected():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            payload = {
                "source": {"resource_type": "personnel", "resource_id": 880001},
                "target": {"resource_type": "vehicle", "resource_id": 999999},
                "association_type": "Assigned",
            }
            response = client.post("/api/resource-associations", json=payload)
            assert response.status_code == 404
    finally:
        _reset()


def test_cycle_is_rejected():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            first = client.post(
                "/api/resource-associations",
                json={
                    "source": {"resource_type": "personnel", "resource_id": 880001},
                    "target": {"resource_type": "vehicle", "resource_id": 880002},
                    "association_type": "Associated",
                },
            )
            assert first.status_code == 201

            second = client.post(
                "/api/resource-associations",
                json={
                    "source": {"resource_type": "vehicle", "resource_id": 880002},
                    "target": {"resource_type": "vehicle", "resource_id": 880003},
                    "association_type": "Associated",
                },
            )
            assert second.status_code == 201

            # vehicle 880003 -> personnel 880001 would close the loop
            # 880001 -> 880002 -> 880003 -> 880001.
            cyclic = client.post(
                "/api/resource-associations",
                json={
                    "source": {"resource_type": "vehicle", "resource_id": 880003},
                    "target": {"resource_type": "personnel", "resource_id": 880001},
                    "association_type": "Associated",
                },
            )
            assert cyclic.status_code == 409
    finally:
        _reset()


def test_self_association_is_rejected():
    _reset()
    try:
        _seed()
        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/resource-associations",
                json={
                    "source": {"resource_type": "personnel", "resource_id": 880001},
                    "target": {"resource_type": "personnel", "resource_id": 880001},
                    "association_type": "Associated",
                },
            )
            assert response.status_code == 400
    finally:
        _reset()
