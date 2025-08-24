import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.ics214.api import router

app = FastAPI()
app.include_router(router, prefix="/api/ics214")
client = TestClient(app)


def test_create_entry_ws_and_export(tmp_path):
    # Create stream
    res = client.post("/api/ics214/streams", json={"mission_id": "m1", "name": "Test"})
    stream_id = res.json()["id"]

    with client.websocket_connect(f"/api/ics214/streams/{stream_id}/ws") as ws:
        client.post(f"/api/ics214/streams/{stream_id}/entries", params={"mission_id": "m1"}, json={"text": "hello"})
        data = ws.receive_json()
        assert data["text"] == "hello"

    res = client.get(f"/api/ics214/streams/{stream_id}/entries", params={"mission_id": "m1"})
    assert len(res.json()) == 1

    res = client.post(f"/api/ics214/streams/{stream_id}/export", params={"mission_id": "m1"}, json={"include_auto": True, "include_attachments": False})
    path = res.json()["file_path"]
    assert os.path.exists(path)
