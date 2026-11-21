"""Phase 1A/1B: Event Schedule backend tests.

Covers schedule item creation, editing/persistence, timestamp validation,
status transitions, actual-vs-planned times, cancellation/delay handling,
incident isolation, backward compatibility with pre-Phase-1A records, and
that existing schedule triggers still fire unaffected by these changes.
"""
from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.services import trigger_engine

INCIDENT_A = "TEST_EVENT_SCHEDULE_A"
INCIDENT_B = "TEST_EVENT_SCHEDULE_B"


def _base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}"


def _clear(db):
    for collection in (
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.PLANNED_SCHEDULE_TRIGGERS,
        IncidentCollections.NOTIFICATIONS,
        IncidentCollections.AUDIT_LOGS,
    ):
        db[collection].delete_many({})


def test_create_schedule_item_defaults_and_persists_new_fields():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={
                "name": "Staff Briefing",
                "kind": "Briefing",
                "starts_at": "2026-12-01T07:45:00",
                "ends_at": "2026-12-01T08:00:00",
                "assigned_to": "Ops Chief",
                "assigned_team_id": "17",
                "time_zone": "America/New_York",
                "location": "ICP Tent",
                "notes": "Bring the whiteboard.",
            },
        )
        assert res.status_code == 201, res.text
        item = res.json()
        assert item["status"] == "Scheduled"
        assert item["assigned_to"] == "Ops Chief"
        assert item["assigned_team_id"] == "17"
        assert item["time_zone"] == "America/New_York"
        assert item["actual_start_at"] == ""
        assert item["actual_end_at"] == ""
    _clear(db)


def test_create_rejects_invalid_planned_time_range():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Bad range", "starts_at": "2026-12-01T10:00:00", "ends_at": "2026-12-01T09:00:00"},
        )
        assert res.status_code == 422
    _clear(db)


def test_create_rejects_unknown_status():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Bad status", "status": "Not A Real Status"},
        )
        assert res.status_code == 422
    _clear(db)


def test_edit_and_persist_after_refresh():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "Orig"})
        rid = res.json()["id"]

        res = client.patch(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}",
            json={"location": "ICP Tent", "notes": "Updated notes", "owner": "Logistics"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["location"] == "ICP Tent"
        assert res.json()["owner"] == "Logistics"

        # Simulate reopening the schedule (a fresh GET, as the UI would do
        # after a refresh) and confirm the edit persisted.
        res = client.get(f"{_base(INCIDENT_A)}/planned/promotions/schedule")
        reopened = next(row for row in res.json() if row["id"] == rid)
        assert reopened["location"] == "ICP Tent"
        assert reopened["summary"] == "Updated notes"  # "notes" maps to "summary" in _map_doc
        # Unrelated fields untouched by the patch survive.
        assert reopened["title"] == "Orig"
    _clear(db)


def test_patch_rejects_invalid_status_transition():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        res = client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"status": "Completed"})
        assert res.status_code == 409
    _clear(db)


def test_full_lifecycle_start_delay_resume_complete_preserves_planned_times():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Opening Ceremony", "starts_at": "2026-12-01T09:00:00", "ends_at": "2026-12-01T09:30:00"},
        )
        rid = res.json()["id"]

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        assert res.status_code == 200
        started = res.json()
        assert started["status"] == "In Progress"
        assert started["actual_start_at"]
        # planned times untouched
        assert started["starts_at"] == "2026-12-01T09:00:00"
        assert started["ends_at"] == "2026-12-01T09:30:00"

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        assert res.status_code == 409  # already in progress

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/delay", json={})
        assert res.status_code == 422  # reason required

        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/delay",
            json={"delay_reason": "Waiting on vendor setup"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "Delayed"
        assert res.json()["delay_reason"] == "Waiting on vendor setup"

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/resume", json={})
        assert res.status_code == 200
        assert res.json()["status"] == "In Progress"

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/complete", json={})
        assert res.status_code == 200
        completed = res.json()
        assert completed["status"] == "Completed"
        assert completed["actual_end_at"]
        assert completed["starts_at"] == "2026-12-01T09:00:00"  # still untouched

        # Completed is terminal.
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/cancel",
            json={"cancellation_reason": "too late"},
        )
        assert res.status_code == 409
    _clear(db)


def test_cancel_requires_reason_and_is_terminal():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/cancel", json={})
        assert res.status_code == 422

        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/cancel",
            json={"cancellation_reason": "Severe weather"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "Cancelled"
        assert res.json()["cancellation_reason"] == "Severe weather"

        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        assert res.status_code == 409
    _clear(db)


def test_backward_compatible_with_pre_phase1a_records():
    """A schedule item written before these fields existed must still be
    readable, and its existing free-text status must not be silently
    rewritten to one of the new canonical values."""
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    db[IncidentCollections.PLANNED_EVENT_SCHEDULES].insert_one({
        "_id": "legacy-1",
        "schedule_id": f"{INCIDENT_A}-PLAN-SCHEDULE-1",
        "seq": 1,
        "incident_id": INCIDENT_A,
        "tool": "promotions/schedule",
        "name": "Legacy item",
        "kind": "Milestone",
        "starts_at": "2026-01-01T00:00:00",
        "ends_at": "",
        "notes": "",
        "location": "", "zone": "", "owner": "", "status": "Planned", "tags": [],
        "created_at": "x", "updated_at": "x", "deleted": False,
    })
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"{_base(INCIDENT_A)}/planned/promotions/schedule")
        assert res.status_code == 200
        legacy = res.json()[0]
        assert legacy["status"] == "Planned"
        assert legacy["actual_start_at"] == ""
        assert legacy["title"] == "Legacy item"
    _clear(db)


def test_schedule_items_are_isolated_per_incident():
    db_a = get_incident_db(INCIDENT_A)
    db_b = get_incident_db(INCIDENT_B)
    _clear(db_a)
    _clear(db_b)
    app = create_app()
    with TestClient(app) as client:
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A-only"})
        client.post(f"{_base(INCIDENT_B)}/planned/promotions/schedule", json={"name": "B-only"})

        a_items = client.get(f"{_base(INCIDENT_A)}/planned/promotions/schedule").json()
        b_items = client.get(f"{_base(INCIDENT_B)}/planned/promotions/schedule").json()
        assert [row["title"] for row in a_items] == ["A-only"]
        assert [row["title"] for row in b_items] == ["B-only"]
    _clear(db_a)
    _clear(db_b)


def test_mutations_produce_audit_records():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"location": "Tent 2"})
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        client.delete(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}")

    actions = [doc["action"] for doc in db[IncidentCollections.AUDIT_LOGS].find({"incident_id": INCIDENT_A})]
    assert "schedule_item.created" in actions
    assert "schedule_item.updated" in actions
    assert "schedule_item.in_progress" in actions
    assert "schedule_item.deleted" in actions
    _clear(db)


def test_404_for_unknown_schedule_item_on_every_action():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        for suffix in ("", "/start", "/resume", "/complete", "/delay", "/cancel"):
            method = client.patch if suffix == "" else client.post
            payload = {"cancellation_reason": "x"} if suffix == "/cancel" else (
                {"delay_reason": "x"} if suffix == "/delay" else {}
            )
            res = method(f"{_base(INCIDENT_A)}/planned/promotions/schedule/999{suffix}", json=payload)
            assert res.status_code == 404, (suffix, res.text)
    _clear(db)


def test_existing_schedule_triggers_still_fire_unaffected_by_schema_changes():
    """Preserve-existing-trigger-behavior regression guard: a ScheduleTrigger
    linked to a schedule item created under the new schema still fires
    through the shared notification system exactly as before."""
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "Staff Briefing", "starts_at": "2026-12-01T07:45:00"},
        )
        schedule_item = res.json()

        due_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        res = client.post(
            f"{_base(INCIDENT_A)}/planned-meta/schedule-triggers",
            json={
                "schedule_item_id": schedule_item["record_id"],
                "title": "Briefing starting",
                "trigger_at": due_at,
            },
        )
        assert res.status_code == 201, res.text

        fired = trigger_engine.evaluate_due_triggers(INCIDENT_A)
        assert fired == 1
        notifications = db[IncidentCollections.NOTIFICATIONS].find_one({"incident_id": INCIDENT_A})
        assert notifications is not None
        assert notifications["title"] == "Briefing starting"
    _clear(db)
