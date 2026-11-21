"""Phase 0 Workstream 7: the thin vertical prototype.

Deliberately not a UI feature (per the Phase 0 brief: "Do not build a
polished interface for this prototype... a minimal development-facing
control or test harness is acceptable") — this automated test *is* that
harness. It walks the exact chain the brief specifies end to end against
real backend code, through the actual API layer wherever a client would
use it:

1. Create an event schedule item.
2. Attach a reminder trigger to it.
3. Persist the trigger (via the real `/planned-meta/schedule-triggers` API).
4. Execute the trigger through the authoritative scheduler
   (`trigger_engine.evaluate_due_triggers` — the same function
   `NotificationTriggerLoop` calls on every poll tick in lan_server/
   cloud_server).
5. Emit a notification through the main (shared) notification subsystem.
6. Persist the delivered notification.
7. Link the notification back to its source schedule item (via the
   trigger's `source_id`/`schedule_item_id` chain).
8. Resolve the source schedule item starting only from the notification.
9. Re-run the scheduler (simulating a reconnect/re-poll) and confirm no
   duplicate notification is produced.
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

INCIDENT_ID = "TEST_PLANNED_EVENTS_THIN_VERTICAL"
BASE = f"/api/incidents/{INCIDENT_ID}"


def _clear(db):
    for collection in (
        IncidentCollections.PLANNED_EVENT_SCHEDULES,
        IncidentCollections.PLANNED_SCHEDULE_TRIGGERS,
        IncidentCollections.NOTIFICATIONS,
    ):
        db[collection].delete_many({})


def test_schedule_item_to_notification_end_to_end_without_duplication():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        # 1. Create an event schedule item.
        res = client.post(
            f"{BASE}/planned/promotions/schedule",
            json={"name": "Staff Briefing", "kind": "Milestone", "starts_at": "2026-12-01T07:45:00"},
        )
        assert res.status_code == 201, res.text
        schedule_item = res.json()

        # 2 & 3. Attach and persist a reminder trigger, due in the past so
        # the scheduler treats it as due now.
        due_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        res = client.post(
            f"{BASE}/planned-meta/schedule-triggers",
            json={
                "schedule_item_id": schedule_item["record_id"],
                "trigger_type": "notification",
                "label": "Briefing reminder",
                "title": "Staff Briefing starting",
                "message_template": "Staff Briefing starts now in the ICP.",
                "trigger_at": due_at,
                "relative_to": "start",
                "enabled": True,
            },
        )
        assert res.status_code == 201, res.text
        trigger = res.json()
        assert trigger["schedule_item_id"] == schedule_item["record_id"]

        # 4, 5, 6. Execute via the authoritative scheduler; this emits
        # through and persists in the shared notification subsystem.
        fired = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
        assert fired == 1

        res = client.get(f"{BASE}/notifications")
        assert res.status_code == 200, res.text
        notifications = res.json()
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification["title"] == "Staff Briefing starting"

        # 7 & 8. Resolve the source record starting only from the
        # notification: source_id is the trigger's compound id, which
        # carries schedule_item_id back to the schedule record.
        assert notification["source_type"] == "planned_schedule_trigger"
        res = client.get(f"{BASE}/planned-meta/schedule-triggers")
        assert res.status_code == 200, res.text
        matching_triggers = [
            row for row in res.json() if row["trigger_id"] == notification["source_id"]
        ]
        assert len(matching_triggers) == 1
        resolved_trigger = matching_triggers[0]

        res = client.get(f"{BASE}/planned/promotions/schedule")
        assert res.status_code == 200, res.text
        matching_schedule_items = [
            row for row in res.json() if row["record_id"] == resolved_trigger["schedule_item_id"]
        ]
        assert len(matching_schedule_items) == 1
        assert matching_schedule_items[0]["title"] == "Staff Briefing"

        # 9. Re-run the scheduler (simulating a reconnect/re-poll) — no
        # duplicate notification.
        fired_again = trigger_engine.evaluate_due_triggers(INCIDENT_ID)
        assert fired_again == 0
        res = client.get(f"{BASE}/notifications")
        assert len(res.json()) == 1

    _clear(db)
