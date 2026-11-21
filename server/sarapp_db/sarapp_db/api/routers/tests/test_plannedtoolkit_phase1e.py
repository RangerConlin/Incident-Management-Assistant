"""Phase 1E: execution controls and schedule reliability (backend half).

Covers the tightened lifecycle (Resume targets Scheduled-vs-In Progress
"as appropriate"; Complete now requires In Progress, not Delayed directly),
the /correct override for terminal-status reopening, revision-based
optimistic concurrency, a revised start time on delay, and backward
compatibility with pre-Phase-1E records that have no `revision` field.
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

INCIDENT_A = "TEST_SCHEDULE_PHASE1E_A"
INCIDENT_B = "TEST_SCHEDULE_PHASE1E_B"


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


def test_new_item_starts_at_revision_zero():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        assert res.json()["revision"] == 0
    _clear(db)


def test_resume_targets_scheduled_when_never_actually_started():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/delay", json={"delay_reason": "weather"})
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/resume", json={})
        assert res.status_code == 200
        assert res.json()["status"] == "Scheduled"
        assert not res.json()["actual_start_at"]
    _clear(db)


def test_resume_targets_in_progress_when_already_actually_started():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/delay", json={"delay_reason": "weather"})
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/resume", json={})
        assert res.status_code == 200
        assert res.json()["status"] == "In Progress"
    _clear(db)


def test_complete_from_delayed_now_requires_resume_first():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/delay", json={"delay_reason": "x"})
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/complete", json={})
        assert res.status_code == 409
    _clear(db)


def test_delay_with_revised_start_time_reschedules_and_preserves_reason():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule",
            json={"name": "A", "starts_at": "2026-12-01T09:00:00", "ends_at": "2026-12-01T10:00:00"},
        )
        rid = res.json()["id"]
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/delay",
            json={"delay_reason": "late start", "revised_start_at": "2026-12-01T09:30:00"},
        )
        assert res.status_code == 200
        assert res.json()["starts_at"] == "2026-12-01T09:30:00"
        assert res.json()["delay_reason"] == "late start"
        assert res.json()["ends_at"] == "2026-12-01T10:00:00"  # untouched
    _clear(db)


def test_correct_requires_reason_and_at_least_one_field():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/correct", json={"reason": ""})
        assert res.status_code == 422
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/correct", json={"reason": "typo"})
        assert res.status_code == 422
    _clear(db)


def test_correct_reopens_a_terminal_status_bypassing_the_transition_table():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/cancel", json={"cancellation_reason": "x"})

        # A routine action still can't reach a terminal status directly.
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        assert res.status_code == 409

        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/correct",
            json={"reason": "cancelled by mistake", "status": "Scheduled"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "Scheduled"

        # Now routine actions work again.
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        assert res.status_code == 200
    _clear(db)


def test_correct_can_fix_actual_times_without_changing_status():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={})
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/correct",
            json={"reason": "actual start logged wrong", "actual_start_at": "2026-01-01T08:00:00"},
        )
        assert res.status_code == 200
        assert res.json()["actual_start_at"] == "2026-01-01T08:00:00"
        assert res.json()["status"] == "In Progress"  # unchanged
    _clear(db)


def test_correct_rejects_invalid_actual_time_order():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        res = client.post(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/correct",
            json={
                "reason": "x",
                "actual_start_at": "2026-01-01T10:00:00",
                "actual_end_at": "2026-01-01T09:00:00",
            },
        )
        assert res.status_code == 422
    _clear(db)


def test_concurrent_edit_detected_and_rejected_via_revision(monkeypatch=None):
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        stale_revision = res.json()["revision"]

        # A second operator updates it first.
        res = client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"location": "Op 2's edit"})
        assert res.status_code == 200
        assert res.json()["revision"] == stale_revision + 1

        # First operator submits using the revision they originally loaded.
        res = client.patch(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}",
            json={"location": "Op 1's stale edit", "expected_revision": stale_revision},
        )
        assert res.status_code == 409
        current = res.json()["detail"]["current"]
        assert current["location"] == "Op 2's edit"  # the server's real state, for reload

        # Reloading and retrying with the now-current revision succeeds.
        res = client.patch(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}",
            json={"location": "Op 1's retried edit", "expected_revision": current["revision"]},
        )
        assert res.status_code == 200
        assert res.json()["location"] == "Op 1's retried edit"
    _clear(db)


def test_concurrency_check_also_applies_to_event_day_actions():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"location": "bump revision"})
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}/start", json={"expected_revision": 0})
        assert res.status_code == 409
    _clear(db)


def test_omitting_expected_revision_preserves_backward_compatible_last_write_wins():
    db = get_incident_db(INCIDENT_A)
    _clear(db)
    app = create_app()
    with TestClient(app) as client:
        res = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        rid = res.json()["id"]
        client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"location": "first"})
        res = client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{rid}", json={"location": "second"})
        assert res.status_code == 200
        assert res.json()["location"] == "second"
    _clear(db)


def test_backward_compatible_legacy_record_without_revision_field():
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
        "location": "", "zone": "", "owner": "", "status": "Scheduled", "tags": [],
        "created_at": "x", "updated_at": "x", "deleted": False,
        # deliberately no "revision" key
    })
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"{_base(INCIDENT_A)}/planned/promotions/schedule")
        legacy = res.json()[0]
        assert legacy["revision"] == 0

        res = client.patch(
            f"{_base(INCIDENT_A)}/planned/promotions/schedule/{legacy['id']}",
            json={"location": "updated", "expected_revision": 0},
        )
        assert res.status_code == 200
        assert res.json()["revision"] == 1
    _clear(db)


def test_schedule_lifecycle_fields_isolated_per_incident():
    db_a = get_incident_db(INCIDENT_A)
    db_b = get_incident_db(INCIDENT_B)
    _clear(db_a)
    _clear(db_b)
    app = create_app()
    with TestClient(app) as client:
        res_a = client.post(f"{_base(INCIDENT_A)}/planned/promotions/schedule", json={"name": "A"})
        res_b = client.post(f"{_base(INCIDENT_B)}/planned/promotions/schedule", json={"name": "B"})
        client.patch(f"{_base(INCIDENT_A)}/planned/promotions/schedule/{res_a.json()['id']}", json={"location": "x"})

        items_b = client.get(f"{_base(INCIDENT_B)}/planned/promotions/schedule").json()
        assert items_b[0]["revision"] == 0  # unaffected by incident A's edit
    _clear(db_a)
    _clear(db_b)
