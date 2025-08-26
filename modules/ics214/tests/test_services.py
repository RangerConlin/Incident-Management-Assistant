import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from datetime import datetime
import uuid

from modules.ics214 import services
from modules.ics214.schemas import StreamCreate
from modules.ics214.models import ICS214IngestRule
from modules._infra.repository import with_incident_session


def test_ingest_rule_idempotency():
    incident_id = "incident"
    stream = services.create_stream(StreamCreate(incident_id=incident_id, name="Team"))
    with with_incident_session(incident_id) as session:
        rule = ICS214IngestRule(id=str(uuid.uuid4()), stream_id=stream.id, topic="operations.task_status_change", template="{message}")
        session.add(rule)
    event = {
        "event_id": "evt1",
        "topic": "operations.task_status_change",
        "incident_id": incident_id,
        "timestamp_utc": datetime.utcnow().isoformat(),
        "actor_user_id": "u1",
        "payload": {"message": "Task started"},
    }
    services.ingest_event_to_entries(event)
    services.ingest_event_to_entries(event)
    entries = services.list_entries(incident_id, stream.id)
    assert len(entries) == 1 and entries[0]["text"] == "Task started"
