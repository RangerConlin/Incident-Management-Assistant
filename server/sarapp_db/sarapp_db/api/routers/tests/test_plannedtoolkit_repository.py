"""Guard Planned Event Toolkit writes through BaseRepository.

The router owns several small planned-event collections plus a promotion path
that creates an Operations task. This test exercises representative writes and
checks for the BaseRepository-managed fields those paths should stamp.
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


INCIDENT_ID = "TEST_PLANNED_TOOLKIT_REPOSITORY"
BASE = f"/api/incidents/{INCIDENT_ID}"


def _clear(db):
    for collection in (
        IncidentCollections.PLANNED_CAMPAIGNS,
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
        IncidentCollections.PLANNED_NOTIFICATIONS,
        IncidentCollections.OPERATIONS_TASKS,
    ):
        db[collection].delete_many({})


def _assert_repository_doc(doc: dict) -> None:
    assert isinstance(doc["_id"], str)
    assert doc.get("created_at")
    assert doc.get("updated_at")


def test_planned_toolkit_writes_use_base_repository():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{BASE}/planned/promotions",
            json={"title": "Public info campaign", "summary": "Gate timing reminders"},
        )
        assert res.status_code == 201, res.text
        campaign = res.json()
        assert campaign["id"] == 1

        res = client.patch(f"{BASE}/planned/promotions/{campaign['id']}", json={"status": "Ready"})
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "Ready"

        res = client.post(
            f"{BASE}/planned/promotions/schedule",
            json={"name": "Staff briefing", "starts_at": "2026-10-14T09:00:00"},
        )
        assert res.status_code == 201, res.text

        res = client.post(
            f"{BASE}/planned-meta/notifications",
            json={"title": "Reminder", "message": "Briefing in 15 minutes"},
        )
        assert res.status_code == 201, res.text
        notification = res.json()

        res = client.post(
            f"{BASE}/planned-meta/notifications/{notification['id']}/acknowledge",
            json={"acknowledged_by": "planner"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["acknowledged_by"] == "planner"

        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={
                "title": "Open south gate",
                "summary": "Unlock and staff before arrival surge",
                "priority": "High",
                "location": "South Gate",
            },
        )
        assert res.status_code == 201, res.text
        quick_assignment = res.json()

        res = client.post(f"{BASE}/planned/quick-assignments/{quick_assignment['id']}/promote", json={})
        assert res.status_code == 200, res.text
        assert res.json()["linked_tasking_id"]

    for collection in (
        IncidentCollections.PLANNED_CAMPAIGNS,
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
        IncidentCollections.PLANNED_NOTIFICATIONS,
        IncidentCollections.OPERATIONS_TASKS,
    ):
        docs = list(db[collection].find({"incident_id": INCIDENT_ID}))
        assert docs, collection
        for doc in docs:
            _assert_repository_doc(doc)

    _clear(db)
