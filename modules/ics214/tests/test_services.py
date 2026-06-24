from __future__ import annotations

from datetime import datetime, timezone

from modules.ics214 import services
from modules.ics214.schemas import StreamCreate


def test_ingest_rule_idempotency(ics214_app_client):
    incident_id = "incident"
    stream = services.create_stream(StreamCreate(incident_id=incident_id, name="Team"))
    services.add_ingest_rule(
        incident_id, stream["id"], topic="operations.task_status_change", template="{message}",
    )

    event = {
        "event_id": "evt1",
        "topic": "operations.task_status_change",
        "incident_id": incident_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "actor_user_id": "u1",
        "payload": {"message": "Task started"},
    }
    services.ingest_event_to_entries(event)
    services.ingest_event_to_entries(event)

    entries = services.list_entries(incident_id, stream["id"])
    assert len(entries) == 1 and entries[0]["text"] == "Task started"
