"""Idempotency and tag-roundtrip behavior for ICS-214 entries.

Rewritten against the real MongoDB-backed router (data/db/sarapp_db/api/
routers/ics214.py) via modules.ics214.services — the previous version of
this test exercised modules.ics214.models' SQLAlchemy ORM classes directly,
which predate the MongoDB cutover and are no longer used by any live code
path (services.py has called the Mongo API exclusively for some time).
"""

from __future__ import annotations

from modules.ics214 import services
from modules.ics214.schemas import EntryCreate, StreamCreate


def test_duplicate_idempotency_hash_does_not_create_a_second_entry(ics214_app_client):
    incident_id = "ics214-test"
    stream = services.create_stream(StreamCreate(incident_id=incident_id, name="Stream"))

    services.add_entry(
        incident_id, stream["id"], EntryCreate(text="one"), id_hash="h",
    )
    services.add_entry(
        incident_id, stream["id"], EntryCreate(text="two"), id_hash="h",
    )

    entries = services.list_entries(incident_id, stream["id"])
    assert len(entries) == 1
    assert entries[0]["text"] == "one"


def test_tags_roundtrip(ics214_app_client):
    incident_id = "ics214-test2"
    stream = services.create_stream(StreamCreate(incident_id=incident_id, name="Stream"))
    tags = ["a", "b"]

    services.add_entry(incident_id, stream["id"], EntryCreate(text="t", tags=tags))

    entries = services.list_entries(incident_id, stream["id"])
    assert entries[0]["tags"] == tags
