"""Phase 1E: trigger-engine reliability under concurrent evaluators and
delivery failure.

`lan_server` and `cloud_server` each run their own `NotificationTriggerLoop`
for cloud-connected incidents, so two evaluators really can race on the same
trigger. These tests simulate that race directly (calling
`evaluate_due_triggers` twice back to back, which exercises the same atomic
claim path a true concurrent call would) and the restart-recovery case
(claim succeeds, delivery fails, no retry).
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
from sarapp_db.services import notification_service, trigger_engine

INCIDENT_ID = "TEST_TRIGGER_ENGINE_RELIABILITY"


def _clear(db):
    for collection in (IncidentCollections.PLANNED_SCHEDULE_TRIGGERS, IncidentCollections.NOTIFICATIONS):
        db[collection].delete_many({})


def _insert_due_trigger(db, trigger_id: str, **overrides):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    doc = {
        "trigger_id": trigger_id,
        "incident_id": INCIDENT_ID,
        "title": "x",
        "trigger_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "enabled": True,
        "recurring": False,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    doc.update(overrides)
    db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].insert_one(doc)


def test_two_racing_evaluators_fire_the_trigger_at_most_once():
    """Simulates lan_server and cloud_server both evaluating the same
    incident at (effectively) the same time."""
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _insert_due_trigger(db, f"{INCIDENT_ID}-PLAN-TRIGGER-1")

    fired_by_evaluator_1 = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    fired_by_evaluator_2 = trigger_engine.evaluate_due_triggers(INCIDENT_ID)

    assert fired_by_evaluator_1 == 1
    assert fired_by_evaluator_2 == 0
    assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_ID}) == 1
    _clear(db)


def test_claim_is_atomic_even_when_due_at_the_same_instant():
    """Directly exercises the claim primitive two evaluators would race on."""
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _insert_due_trigger(db, f"{INCIDENT_ID}-PLAN-TRIGGER-1")
    col = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS]
    doc = col.find_one({"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-1"})

    first_claim = trigger_engine._claim_trigger(col, doc["_id"])
    second_claim = trigger_engine._claim_trigger(col, doc["_id"])

    assert first_claim is not None
    assert second_claim is None
    _clear(db)


def test_restart_between_claim_and_delivery_does_not_duplicate_on_retry():
    """A crash after the atomic claim but before/during delivery leaves
    fired_at set; the brief requires this cost a missed notification, never
    a duplicate one -- re-running evaluate_due_triggers after "restart" must
    not re-fire it."""
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _insert_due_trigger(db, f"{INCIDENT_ID}-PLAN-TRIGGER-1")

    original_emit = notification_service.emit_notification
    notification_service.emit_notification = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("process killed"))
    try:
        fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    finally:
        notification_service.emit_notification = original_emit
    assert fired == 0  # delivery failed

    trigger = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].find_one({"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-1"})
    assert trigger.get("fired_at")  # claimed -- will not be retried
    assert "process killed" in trigger.get("fire_error", "")

    # "Restart" and evaluate again -- must not re-fire or duplicate.
    fired_after_restart = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    assert fired_after_restart == 0
    assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_ID}) == 0
    _clear(db)


def test_successful_delivery_clears_any_prior_fire_error():
    """If a trigger's claim is ever retried in a future extension of this
    engine, a stale fire_error from an earlier failed attempt must not
    linger once delivery succeeds. Exercised directly against the claim
    primitive since the current engine never retries a claimed trigger."""
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _insert_due_trigger(db, f"{INCIDENT_ID}-PLAN-TRIGGER-1", fire_error="stale error from a previous run")
    col = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS]
    doc = col.find_one({"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-1"})
    # Simulate "not yet fired" (insert above would be an inconsistent state
    # in practice, but the claim must still clear the stale field).
    col.update_one({"_id": doc["_id"]}, {"$unset": {"fired_at": ""}})

    claimed = trigger_engine._claim_trigger(col, doc["_id"])
    assert claimed is not None
    stored = col.find_one({"_id": doc["_id"]})
    assert "fire_error" not in stored
    _clear(db)


def test_failed_delivery_is_distinguishable_from_successful_delivery():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)
    _insert_due_trigger(db, f"{INCIDENT_ID}-PLAN-TRIGGER-1")
    _insert_due_trigger(db, f"{INCIDENT_ID}-PLAN-TRIGGER-2")

    original_emit = notification_service.emit_notification

    # Fail trigger 1 specifically by id, succeed trigger 2.
    def selective_emit(incident_id, *, source_id="", **kwargs):
        if source_id.endswith("-1"):
            raise RuntimeError("delivery failed")
        return original_emit(incident_id, source_id=source_id, **kwargs)

    notification_service.emit_notification = selective_emit
    try:
        trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    finally:
        notification_service.emit_notification = original_emit

    col = db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS]
    failed = col.find_one({"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-1"})
    succeeded = col.find_one({"trigger_id": f"{INCIDENT_ID}-PLAN-TRIGGER-2"})
    assert failed.get("fire_error")
    assert not succeeded.get("fire_error")
    assert failed.get("fired_at") and succeeded.get("fired_at")  # both claimed
    assert db[IncidentCollections.NOTIFICATIONS].count_documents({"incident_id": INCIDENT_ID}) == 1
    _clear(db)
