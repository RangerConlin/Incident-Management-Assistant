import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from datetime import datetime
import uuid
import pytest

from modules._infra.repository import with_mission_session
from modules.ics214.models import ICS214Stream, ICS214Entry


def test_entry_unique_hash():
    mission_id = "testmission"
    with with_mission_session(mission_id) as session:
        stream = ICS214Stream(id=str(uuid.uuid4()), mission_id=mission_id, name="Stream")
        session.add(stream)
        session.flush()
        e1 = ICS214Entry(id=str(uuid.uuid4()), stream_id=stream.id, timestamp_utc=datetime.utcnow(), text="one", idempotency_hash="h")
        session.add(e1)
        session.flush()
        e2 = ICS214Entry(id=str(uuid.uuid4()), stream_id=stream.id, timestamp_utc=datetime.utcnow(), text="two", idempotency_hash="h")
        with pytest.raises(Exception):
            session.add(e2)
            session.flush()
        session.rollback()


def test_tags_roundtrip():
    mission_id = "testmission2"
    with with_mission_session(mission_id) as session:
        stream = ICS214Stream(id=str(uuid.uuid4()), mission_id=mission_id, name="Stream")
        session.add(stream)
        session.flush()
        tags = ["a", "b"]
        e1 = ICS214Entry(id=str(uuid.uuid4()), stream_id=stream.id, timestamp_utc=datetime.utcnow(), text="t", idempotency_hash=str(uuid.uuid4()), tags=tags)
        session.add(e1)
        session.flush()
        session.refresh(e1)
        assert e1.tags == tags
