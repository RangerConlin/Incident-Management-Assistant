"""Stream/entry creation against the real MongoDB-backed router.

Rewritten: the previous version tested modules.ics214.api, a local FastAPI
router that duplicated routing already provided by
data/db/sarapp_db/api/routers/ics214.py and was never registered into the
real app (main.py's ICS-214 panel calls modules.ics214.services directly).
That dead router also exposed its own per-stream WebSocket and a local PDF
export endpoint, neither of which exist in the current architecture — live
updates now go through the generic IncidentCache hub, and PDF export happens
client-side via services.export_stream. Both are exercised elsewhere; this
test now covers what the real router actually does: streams and entries.
"""

from __future__ import annotations

from modules.ics214 import services
from modules.ics214.schemas import EntryCreate, StreamCreate


def test_create_stream_and_entry(ics214_app_client):
    stream = services.create_stream(StreamCreate(incident_id="m1", name="Test"))
    assert stream["name"] == "Test"

    services.add_entry("m1", stream["id"], EntryCreate(text="hello"))

    entries = services.list_entries("m1", stream["id"])
    assert len(entries) == 1
    assert entries[0]["text"] == "hello"
