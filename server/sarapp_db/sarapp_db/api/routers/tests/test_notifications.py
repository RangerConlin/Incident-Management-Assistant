"""Router/service-level tests for the shared notification engine."""

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
from sarapp_db.services import notification_service, trigger_engine

INCIDENT_ID = "TESTCACHE_NOTIFICATIONS"


def _reset_db():
    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.NOTIFICATIONS].delete_many({})
    db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].delete_many({})
    db[IncidentCollections.INCIDENT_PERSONNEL].delete_many({})
    db[IncidentCollections.INCIDENT_PERSONNEL].insert_one(
        {"_id": "person-1", "person_record": 501, "role": "Safety Officer", "incident_id": INCIDENT_ID}
    )
    return db


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def test_emit_notification_persists_and_resolves_role_audience():
    _reset_db()
    doc = notification_service.emit_notification(
        INCIDENT_ID,
        title="Briefing starting",
        message="07:45 staff briefing",
        source_type="planned_schedule_trigger",
        source_id="trigger-1",
        audience_role="Safety Officer",
    )
    assert doc["notification_id"] >= 1
    assert doc["delivery"]["recipients"] == [501]

    listed = notification_service.list_notifications(INCIDENT_ID, audience_role="Safety Officer")
    assert len(listed) == 1
    assert listed[0]["title"] == "Briefing starting"


def test_acknowledge_and_dismiss_endpoints():
    _reset_db()
    doc = notification_service.emit_notification(
        INCIDENT_ID,
        title="Test",
        message="Test message",
        source_type="test",
        source_id="1",
    )
    notification_id = doc["notification_id"]

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/notifications/{notification_id}/acknowledge",
            json={"acknowledged_by": "user-1"},
        )
        assert res.status_code == 200
        assert res.json()["acknowledged_by"] == "user-1"
        assert res.json()["read"] is True

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/notifications/{notification_id}/dismiss",
            json={"dismissed_by": "user-2"},
        )
        assert res.status_code == 200
        assert res.json()["dismissed_by"] == "user-2"

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/notifications/999999/acknowledge",
            json={"acknowledged_by": "user-1"},
        )
        assert res.status_code == 404


def _insert_trigger(db, *, trigger_id: str, trigger_at: str, **overrides):
    doc = {
        "trigger_id": trigger_id,
        "incident_id": INCIDENT_ID,
        "title": "Test trigger",
        "summary": "Test trigger fired",
        "trigger_at": trigger_at,
        "enabled": True,
        "recurring": False,
        "audience_user_id": "501",
    }
    doc.update(overrides)
    db[IncidentCollections.PLANNED_SCHEDULE_TRIGGERS].insert_one(doc)
    return doc


def test_due_trigger_fires_exactly_once():
    db = _reset_db()
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    _insert_trigger(db, trigger_id="trigger-due", trigger_at=past)

    fired_first = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
    fired_second = trigger_engine.evaluate_due_triggers(INCIDENT_ID)

    assert fired_first == 1
    assert fired_second == 0

    notifications = notification_service.list_notifications(INCIDENT_ID, source_type="planned_schedule_trigger")
    assert len(notifications) == 1
    assert notifications[0]["source_id"] == "trigger-due"


def test_future_trigger_is_not_fired():
    db = _reset_db()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds")
    _insert_trigger(db, trigger_id="trigger-future", trigger_at=future)

    fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)

    assert fired == 0
    assert notification_service.list_notifications(INCIDENT_ID, source_type="planned_schedule_trigger") == []


def test_recurring_trigger_is_skipped():
    db = _reset_db()
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    _insert_trigger(db, trigger_id="trigger-recurring", trigger_at=past, recurring=True)

    fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)

    assert fired == 0
