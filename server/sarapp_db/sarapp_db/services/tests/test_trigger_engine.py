"""Phase 0.5 backend tests for the schedule-trigger execution engine.

Required by the Phase 0 brief (Workstream 4 / Workstream 6):
- a planned schedule trigger emits through the main notification system
- one trigger occurrence creates no more than one delivered notification
  (idempotent across repeated/"reconnect" evaluations)
- missed/recurring occurrences follow the documented, deliberately deferred
  behavior (skipped, not silently fired) rather than an untested assumption
"""
from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.services import trigger_engine

INCIDENT_ID = "TEST_TRIGGER_ENGINE"


def _clear(db):
    for collection in (
        IncidentCollections.PLANNED_SCHEDULE_TRIGGERS,
        IncidentCollections.NOTIFICATIONS,
    ):
        db[collection].delete_many({})


def _insert_trigger(db, **overrides):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = {
        "trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-{overrides.get('_n', 1)}",
        "incident_id": INCIDENT_ID,
        "schedule_item_id": "",
        "trigger_type": "notification",
        "label": "Briefing reminder",
        "title": "Staff briefing in 15 minutes",
        "summary": "",
        "message_template": "Staff briefing starts at 07:45 in the ICP.",
        "trigger_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "relative_to": "start",
        "enabled": True,
        "recurring": False,
        "audience_role": "",
        "audience_user_id": "",
        "assigned_team_id": "",
        "requires_acknowledgement": False,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    doc.update({k: v for k, v in overrides.items() if k != "_n"})
    db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].insert_one(doc)
    return doc


def test_due_trigger_emits_through_shared_notification_system():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    _insert_trigger(db)
    fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    assert fired == 1

    notifications = list(db[IncidentCollections.NOTIFICATIONS].find({"incident_id": INCIDENT_ID}))
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification["title"] == "Staff briefing in 15 minutes"
    assert notification["message"] == "Staff briefing starts at 07:45 in the ICP."
    assert notification["source_type"] == "planned_schedule_trigger"
    assert notification["source_id"] == f"{INCIDENT_ID}-PLAN-TRIGGER-1"

    trigger = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].find_one(
        {"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-1"}
    )
    assert trigger.get("fired_at")

    _clear(db)


def test_trigger_occurrence_fires_at_most_once_across_repeated_evaluations():
    """Guards the "survives reconnect/sync without duplication" requirement:
    re-running the poll loop (as happens on every tick, and again after any
    reconnect) must never re-fire an already-fired trigger."""
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    _insert_trigger(db)
    first_pass = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    second_pass = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    third_pass = trigger_engine.evaluate_due_triggers(INCIDENT_ID)

    assert (first_pass, second_pass, third_pass) == (1, 0, 0)
    notifications = list(db[IncidentCollections.NOTIFICATIONS].find({"incident_id": INCIDENT_ID}))
    assert len(notifications) == 1

    _clear(db)


def test_future_trigger_is_not_fired():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    _insert_trigger(db, trigger_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
    fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    assert fired == 0
    assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_ID}) == 0

    _clear(db)


def test_disabled_trigger_is_not_fired():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    _insert_trigger(db, enabled=False)
    fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    assert fired == 0

    _clear(db)


def test_recurring_trigger_is_skipped_not_silently_fired():
    """Recurring triggers are a documented, deliberate Phase 1 gap (no shared
    recurrence utility exists yet) — this pins that *current* behavior down
    as a test so a future change has to touch this assertion on purpose
    rather than silently start firing recurring triggers half-built."""
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    _insert_trigger(db, recurring=True)
    fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    assert fired == 0
    assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_ID}) == 0

    trigger = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].find_one(
        {"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-1"}
    )
    assert not trigger.get("fired_at")

    _clear(db)
