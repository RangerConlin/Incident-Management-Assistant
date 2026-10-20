"""Router-level tests for the Search Assignment Planner's linked collection
(search_task_details), which augments — not replaces — the Operations task
record. See api/routers/search_task_details.py for the ownership writeup.
"""
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

INCIDENT_ID = "TEST_SEARCH_TASK_DETAILS"


def _clear() -> None:
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.SEARCH_TASK_DETAILS].delete_many({})
    db[IncidentCollections.TASKS].delete_many({})


def _create_task(client: TestClient) -> int:
    res = client.post(
        f"/api/incidents/{INCIDENT_ID}/operations/tasks",
        json={"title": "Segment A search", "priority": "Medium", "status": "Draft"},
    )
    assert res.status_code in (200, 201), res.text
    return int(res.json()["int_id"])


def test_create_search_task_detail_links_to_existing_operations_task() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        task_id = _create_task(client)
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-task-details",
            json={
                "task_id": task_id,
                "search_method": "Grid",
                "track_spacing": "20m",
                "completion_criteria": "100% segment coverage",
                "safety_notes": "Watch for loose rock",
                "radio_channel": "TAC-2",
                "team_leader": "J. Rivera",
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["task_id"] == task_id
        assert body["search_method"] == "Grid"

        fetched = client.get(
            f"/api/incidents/{INCIDENT_ID}/search-task-details/by-task/{task_id}"
        ).json()
        assert fetched["task_id"] == task_id
    _clear()


def test_duplicate_task_id_rejected() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        task_id = _create_task(client)
        first = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-task-details",
            json={"task_id": task_id, "search_method": "Parallel"},
        )
        assert first.status_code == 201
        second = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-task-details",
            json={"task_id": task_id, "search_method": "Sector"},
        )
        assert second.status_code == 409
    _clear()


def test_invalid_search_method_rejected() -> None:
    _clear()
    app = create_app()
    with TestClient(app) as client:
        task_id = _create_task(client)
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/search-task-details",
            json={"task_id": task_id, "search_method": "Not A Method"},
        )
        assert res.status_code == 422
    _clear()
