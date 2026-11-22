"""Planned Event Toolkit Assignments (quick-assignments) — Phase 2A coverage.

Exercises the lightweight Assignments system end to end: CRUD, free-text vs.
resource assignees, status/completion, deletion, incident isolation,
promotion to formal Operations Tasking (and duplicate-promotion
prevention), read-only behavior after promotion, and confirms the obsolete
planned-event "tasks" tool is gone without touching Operations Tasking.
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


INCIDENT_ID = "TEST_PLANNED_TOOLKIT_ASSIGNMENTS"
OTHER_INCIDENT_ID = "TEST_PLANNED_TOOLKIT_ASSIGNMENTS_OTHER"
BASE = f"/api/incidents/{INCIDENT_ID}"
OTHER_BASE = f"/api/incidents/{OTHER_INCIDENT_ID}"


def _clear(incident_id: str) -> None:
    db = get_incident_db(incident_id)
    for collection in (
        IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.OPERATIONS_TASKS,
    ):
        db[collection].delete_many({})


def setup_function(_fn) -> None:
    _clear(INCIDENT_ID)
    _clear(OTHER_INCIDENT_ID)


def teardown_function(_fn) -> None:
    _clear(INCIDENT_ID)
    _clear(OTHER_INCIDENT_ID)


def test_obsolete_tasks_tool_removed_without_breaking_quick_assignments():
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"{BASE}/planned/tasks")
        assert res.status_code == 404

        res = client.post(f"{BASE}/planned/tasks", json={"title": "Should not exist"})
        assert res.status_code == 404

        res = client.get(f"{BASE}/planned/quick-assignments")
        assert res.status_code == 200


def test_create_retrieve_edit_status_and_delete():
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Staff water station", "priority": "Low", "location": "Aid Tent 2"},
        )
        assert res.status_code == 201, res.text
        record = res.json()
        assert record["title"] == "Staff water station"

        res = client.get(f"{BASE}/planned/quick-assignments")
        assert res.status_code == 200
        assert any(r["id"] == record["id"] for r in res.json())

        res = client.patch(
            f"{BASE}/planned/quick-assignments/{record['id']}",
            json={"title": "Staff water station — north", "priority": "High", "location": "Aid Tent 1"},
        )
        assert res.status_code == 200, res.text
        updated = res.json()
        assert updated["title"] == "Staff water station — north"
        assert updated["priority"] == "High"

        res = client.patch(f"{BASE}/planned/quick-assignments/{record['id']}", json={"status": "In Progress"})
        assert res.status_code == 200
        assert res.json()["status"] == "In Progress"

        res = client.patch(f"{BASE}/planned/quick-assignments/{record['id']}", json={"status": "Completed"})
        assert res.status_code == 200
        assert res.json()["status"] == "Completed"

        res = client.delete(f"{BASE}/planned/quick-assignments/{record['id']}")
        assert res.status_code == 204

        res = client.get(f"{BASE}/planned/quick-assignments")
        assert all(r["id"] != record["id"] for r in res.json())


def test_free_text_assignee_round_trips():
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Coordinate parking", "assigned_to": "Jordan Alvarez (Volunteer Lead)"},
        )
        assert res.status_code == 201, res.text
        record = res.json()
        assert record["assigned_to"] == "Jordan Alvarez (Volunteer Lead)"
        assert record["assigned_person_id"] == ""
        assert record["assigned_team_id"] == ""


def test_personnel_and_team_resource_ids_persist_and_edit_switches_cleanly():
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Open south gate", "assigned_to": "T. Rivera", "assigned_person_id": "42"},
        )
        assert res.status_code == 201, res.text
        record = res.json()
        assert record["assigned_person_id"] == "42"
        assert record["assigned_team_id"] == ""

        # Switching from a personnel assignee to a team assignee must clear
        # the stale assigned_person_id so the record never carries both.
        res = client.patch(
            f"{BASE}/planned/quick-assignments/{record['id']}",
            json={"assigned_to": "Team Alpha", "assigned_team_id": "7", "assigned_person_id": ""},
        )
        assert res.status_code == 200, res.text
        updated = res.json()
        assert updated["assigned_team_id"] == "7"
        assert updated["assigned_person_id"] == ""

        # Switching to free text clears both resource ids.
        res = client.patch(
            f"{BASE}/planned/quick-assignments/{record['id']}",
            json={"assigned_to": "Gate volunteers", "assigned_team_id": "", "assigned_person_id": ""},
        )
        assert res.status_code == 200, res.text
        cleared = res.json()
        assert cleared["assigned_to"] == "Gate volunteers"
        assert cleared["assigned_team_id"] == ""
        assert cleared["assigned_person_id"] == ""


def test_incident_isolation():
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{BASE}/planned/quick-assignments", json={"title": "Incident A assignment"})
        assert res.status_code == 201
        res = client.post(f"{OTHER_BASE}/planned/quick-assignments", json={"title": "Incident B assignment"})
        assert res.status_code == 201

        a_titles = {r["title"] for r in client.get(f"{BASE}/planned/quick-assignments").json()}
        b_titles = {r["title"] for r in client.get(f"{OTHER_BASE}/planned/quick-assignments").json()}
        assert "Incident A assignment" in a_titles
        assert "Incident B assignment" not in a_titles
        assert "Incident B assignment" in b_titles
        assert "Incident A assignment" not in b_titles


def test_promotion_creates_linked_task_and_blocks_duplicate_promotion():
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Promote me", "priority": "High", "due_at": "2026-10-14T09:00:00"},
        )
        assert res.status_code == 201, res.text
        record = res.json()

        res = client.post(f"{BASE}/planned/quick-assignments/{record['id']}/promote", json={"promoted_by": "planner"})
        assert res.status_code == 200, res.text
        promoted = res.json()
        assert promoted["linked_tasking_id"]
        assert promoted["promoted_read_only"] is True

        # Tasks live in a per-incident database already (see _tasks_repo),
        # so operations.create_task() never stamps an incident_id field onto
        # the document itself -- count within this incident's own database.
        db = get_incident_db(INCIDENT_ID)
        tasks_before = db[IncidentCollections.OPERATIONS_TASKS].count_documents({})
        assert tasks_before == 1

        # Repeated promotion requests must not create a second formal task.
        res = client.post(f"{BASE}/planned/quick-assignments/{record['id']}/promote", json={"promoted_by": "planner"})
        assert res.status_code == 200, res.text
        assert res.json()["linked_tasking_id"] == promoted["linked_tasking_id"]

        tasks_after = db[IncidentCollections.OPERATIONS_TASKS].count_documents({})
        assert tasks_after == 1


def test_promoted_assignment_is_read_only():
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{BASE}/planned/quick-assignments", json={"title": "Lock after promotion"})
        assert res.status_code == 201, res.text
        record = res.json()

        res = client.post(f"{BASE}/planned/quick-assignments/{record['id']}/promote", json={})
        assert res.status_code == 200, res.text

        res = client.patch(f"{BASE}/planned/quick-assignments/{record['id']}", json={"title": "Edited after promotion"})
        assert res.status_code == 409


def test_assignment_can_optionally_link_to_an_existing_schedule_item():
    """Phase 2B: an assignment may reference zero or one schedule item, and a
    schedule item may have multiple assignments pointing back at it, via a
    stable schedule_item_id rather than duplicated schedule data."""
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{BASE}/planned/promotions/schedule",
            json={"name": "Opening Briefing", "starts_at": "2026-12-01T09:00:00"},
        )
        assert res.status_code == 201, res.text
        schedule_item = res.json()

        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Set up chairs", "schedule_item_id": schedule_item["record_id"]},
        )
        assert res.status_code == 201, res.text
        assignment_one = res.json()
        assert assignment_one["schedule_item_id"] == schedule_item["record_id"]

        res = client.post(f"{BASE}/planned/quick-assignments", json={"title": "Untethered assignment"})
        assert res.status_code == 201, res.text
        assert res.json()["schedule_item_id"] == ""

        res = client.post(
            f"{BASE}/planned/quick-assignments",
            json={"title": "Set up PA system", "schedule_item_id": schedule_item["record_id"]},
        )
        assert res.status_code == 201, res.text
        assignment_two = res.json()

        res = client.get(f"{BASE}/planned/quick-assignments", params={"schedule_item_id": schedule_item["record_id"]})
        assert res.status_code == 200
        linked_ids = {r["id"] for r in res.json()}
        assert linked_ids == {assignment_one["id"], assignment_two["id"]}

        res = client.patch(
            f"{BASE}/planned/quick-assignments/{assignment_one['id']}",
            json={"schedule_item_id": ""},
        )
        assert res.status_code == 200, res.text
        assert res.json()["schedule_item_id"] == ""

        res = client.get(f"{BASE}/planned/quick-assignments", params={"schedule_item_id": schedule_item["record_id"]})
        assert res.status_code == 200
        assert {r["id"] for r in res.json()} == {assignment_two["id"]}
