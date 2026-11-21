"""Phase 0.5 backend tests for the shared notification emission service.

Covers Workstream 2's required capabilities: persistence, incident scope,
source entity type/id (entity-link resolution), user targeting,
acknowledgement, dismissal, and that the desktop-toast broadcast never
blocks persistence if it fails.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.services import notification_service

INCIDENT_ID = "TEST_NOTIFICATION_SERVICE"


def _clear(db):
    db[IncidentCollections.NOTIFICATIONS].delete_many({})


def test_emit_notification_persists_with_incident_scope_and_source_link():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    doc = notification_service.emit_notification(
        INCIDENT_ID,
        title="Briefing reminder",
        message="Briefing in 15 minutes",
        source_type="planned_schedule_trigger",
        source_id="TRIGGER-1",
        severity="priority",
        category="planning",
        audience_user_id=42,
    )

    assert doc["incident_id"] == INCIDENT_ID
    assert doc["source_type"] == "planned_schedule_trigger"
    assert doc["source_id"] == "TRIGGER-1"
    assert doc["delivery"]["recipients"] == [42]

    stored = db[IncidentCollections.NOTIFICATIONS].find_one({"notification_id": doc["notification_id"]})
    assert stored is not None
    assert stored["title"] == "Briefing reminder"

    _clear(db)


def test_acknowledge_then_dismiss_update_recipient_state():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    doc = notification_service.emit_notification(
        INCIDENT_ID,
        title="t",
        message="m",
        source_type="x",
        source_id="1",
        audience_user_id=7,
    )
    notification_id = doc["notification_id"]

    acked = notification_service.acknowledge_notification(INCIDENT_ID, notification_id, person_record=7)
    state = next(r for r in acked["recipient_states"] if r["person_record"] == 7)
    assert state["read"] is True
    assert state.get("acknowledged_at")

    dismissed = notification_service.dismiss_notification(INCIDENT_ID, notification_id, person_record=7)
    state = next(r for r in dismissed["recipient_states"] if r["person_record"] == 7)
    assert state.get("dismissed_at")

    _clear(db)


def test_acknowledge_rejects_person_not_in_resolved_audience():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    doc = notification_service.emit_notification(
        INCIDENT_ID, title="t", message="m", source_type="x", source_id="1", audience_user_id=7,
    )
    result = notification_service.acknowledge_notification(INCIDENT_ID, doc["notification_id"], person_record=999)
    assert result is None

    _clear(db)


def test_list_notifications_filters_by_source():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    notification_service.emit_notification(
        INCIDENT_ID, title="a", message="m", source_type="planned_schedule_trigger", source_id="T-1",
    )
    notification_service.emit_notification(
        INCIDENT_ID, title="b", message="m", source_type="planned_quick_assignment", source_id="QA-1",
    )

    matches = notification_service.list_notifications(
        INCIDENT_ID, source_type="planned_schedule_trigger", source_id="T-1",
    )
    assert len(matches) == 1
    assert matches[0]["title"] == "a"

    _clear(db)


def test_emit_notification_broadcast_failure_does_not_block_persistence():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    import sarapp_db.api.ws_hub as ws_hub

    original_broadcast = ws_hub.hub.broadcast
    ws_hub.hub.broadcast = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ws down"))
    try:
        doc = notification_service.emit_notification(
            INCIDENT_ID, title="t", message="m", source_type="x", source_id="1",
        )
    finally:
        ws_hub.hub.broadcast = original_broadcast

    assert db[IncidentCollections.NOTIFICATIONS].find_one({"notification_id": doc["notification_id"]})

    _clear(db)
