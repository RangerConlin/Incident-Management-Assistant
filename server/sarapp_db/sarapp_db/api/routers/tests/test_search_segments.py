"""Router-level tests for Search Segment Management (SAR Toolkit)."""
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

INCIDENT_ID = "TEST_SEARCH_SEGMENTS"


def _clear() -> None:
    get_incident_db(INCIDENT_ID)[IncidentCollections.SEARCH_SEGMENTS].delete_many({})


def test_create_segment_with_no_gis_geometry() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-segments",
            json={
                "name": "Segment 1",
                "description": "North ridge area",
                "boundary_description": "Bounded by the creek and the fire road",
                "map_reference": "Quad 12-NE",
                "created_by": "planner1",
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "Segment 1"
        assert body["gis_reference"] is None
        assert body["planning_status"] == "draft"
        assert body["search_status"] == "unassigned"
        assert body["review_status"] == "pending review"
        assert body["segment_id"]
    _clear()


def test_create_segment_rejects_invalid_status() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-segments",
            json={"name": "Segment X", "planning_status": "not-a-status"},
        )
        assert res.status_code == 422
    _clear()


def test_list_update_delete_segment() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        created = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-segments",
            json={"name": "Segment A"},
        ).json()
        segment_id = created["segment_id"]

        listed = client.get(f"/api/incidents/{INCIDENT_ID}/search-segments").json()
        assert any(s["segment_id"] == segment_id for s in listed)

        updated = client.put(
            f"/api/incidents/{INCIDENT_ID}/search-segments/{segment_id}",
            json={
                "name": "Segment A",
                "planning_status": "ready for assignment",
                "search_status": "assigned",
                "review_status": "pending review",
            },
        ).json()
        assert updated["planning_status"] == "ready for assignment"
        assert updated["search_status"] == "assigned"

        deleted = client.delete(f"/api/incidents/{INCIDENT_ID}/search-segments/{segment_id}")
        assert deleted.status_code == 200
        after = client.get(f"/api/incidents/{INCIDENT_ID}/search-segments").json()
        assert not any(s["segment_id"] == segment_id for s in after)
    _clear()


def test_auto_create_grid_generates_expected_count_and_size() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-segments/auto-create-grid",
            json={
                "origin_lat": 39.0,
                "origin_lon": -105.0,
                "orientation_deg": 0,
                "cell_acres": 40,
                "rows": 2,
                "columns": 3,
                "naming_scheme": "sequential",
                "name_prefix": "SEG",
            },
        )
        assert res.status_code == 201
        rows = res.json()
        assert len(rows) == 6
        for row in rows:
            assert row["size_estimate"] == 40
            assert row["gis_reference"] is not None
            assert len(row["gis_reference"]["corners"]) == 4
            assert row["name"].startswith("SEG-")
    _clear()


def test_auto_create_grid_row_col_naming() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-segments/auto-create-grid",
            json={
                "origin_lat": 39.0,
                "origin_lon": -105.0,
                "cell_acres": 10,
                "rows": 1,
                "columns": 2,
                "naming_scheme": "row_col",
            },
        )
        assert res.status_code == 201
        names = sorted(row["name"] for row in res.json())
        assert names == ["A1", "A2"]
    _clear()


def test_auto_create_grid_rejects_bad_dimensions() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-segments/auto-create-grid",
            json={"origin_lat": 39.0, "origin_lon": -105.0, "rows": 0, "columns": 1},
        )
        assert res.status_code == 422
    _clear()
