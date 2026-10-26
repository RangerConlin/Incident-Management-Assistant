"""Covers the chat presence roster (heartbeat/list) and the default-channel
`is_default` flag added alongside it.
"""
from __future__ import annotations

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections


INCIDENT_ID = "TEST_CHAT_PRESENCE"


def _clear(db):
    db[IncidentCollections.CHAT_CHANNELS].delete_many({})
    db[IncidentCollections.PRESENCE].delete_many({})
    db[IncidentCollections.MESSAGES].delete_many({})
    db[IncidentCollections.CHAT_READ_STATE].delete_many({})


def test_default_channels_are_flagged():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/channels", params={"user_id": "u1"})
        assert res.status_code == 200, res.text
        defaults = [c for c in res.json()["items"] if c["type"] == "group"]
        assert len(defaults) == 6
        assert all(c["is_default"] is True for c in defaults)

    _clear(db)


def test_presence_heartbeat_list_and_stale_filtering():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/presence/heartbeat",
            json={"user_id": "u1", "status": "online"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "online"

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/presence/heartbeat",
            json={"user_id": "u2", "status": "away"},
        )
        assert res.status_code == 200, res.text

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/presence/heartbeat",
            json={"user_id": "u1", "status": "unavailable"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "unavailable"

        res = client.get(f"/api/incidents/{INCIDENT_ID}/presence")
        assert res.status_code == 200
        by_user = {item["user_id"]: item["status"] for item in res.json()["items"]}
        # u1's second heartbeat overwrote the first — one doc per user, not two.
        assert by_user == {"u1": "unavailable", "u2": "away"}

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/presence/heartbeat",
            json={"user_id": "u3", "status": "bogus"},
        )
        assert res.status_code == 400

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/presence/heartbeat",
            json={"status": "online"},
        )
        assert res.status_code == 400

    # Backdate u2's heartbeat past the staleness window and confirm they drop
    # off the roster without an explicit "I'm leaving" call.
    from sarapp_db.api.routers.chat import PRESENCE_STALE_AFTER_SECONDS
    from datetime import datetime, timedelta, timezone

    stale_at = (
        datetime.now(timezone.utc) - timedelta(seconds=PRESENCE_STALE_AFTER_SECONDS + 5)
    ).isoformat(timespec="seconds")
    db[IncidentCollections.PRESENCE].update_one({"user_id": "u2"}, {"$set": {"updated_at": stale_at}})

    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{INCIDENT_ID}/presence")
        assert res.status_code == 200
        user_ids = {item["user_id"] for item in res.json()["items"]}
        assert user_ids == {"u1"}

    _clear(db)


def test_unread_count_tracks_read_state_per_channel():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        # Seeds the six default group channels.
        channels = client.get(
            f"/api/incidents/{INCIDENT_ID}/chat/channels", params={"user_id": "u1"}
        ).json()["items"]
        general = next(c for c in channels if c["name"] == "General")

        assert client.get(
            f"/api/incidents/{INCIDENT_ID}/chat/unread-count", params={"user_id": "u1"}
        ).json()["count"] == 0

        client.post(
            f"/api/incidents/{INCIDENT_ID}/chat/channels/{general['id']}/messages",
            json={"sender_id": "u2", "text": "hello"},
        )
        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/unread-count", params={"user_id": "u1"})
        assert res.json()["count"] == 1

        # A message the user sent themselves never counts as unread for them.
        client.post(
            f"/api/incidents/{INCIDENT_ID}/chat/channels/{general['id']}/messages",
            json={"sender_id": "u1", "text": "hi back"},
        )
        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/unread-count", params={"user_id": "u1"})
        assert res.json()["count"] == 1

        res = client.post(
            f"/api/incidents/{INCIDENT_ID}/chat/channels/{general['id']}/read",
            json={"user_id": "u1"},
        )
        assert res.status_code == 200, res.text

        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/unread-count", params={"user_id": "u1"})
        assert res.json()["count"] == 0

        client.post(
            f"/api/incidents/{INCIDENT_ID}/chat/channels/{general['id']}/messages",
            json={"sender_id": "u2", "text": "new message after read"},
        )
        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/unread-count", params={"user_id": "u1"})
        assert res.json()["count"] == 1

        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/unread-count", params={"user_id": ""})
        assert res.status_code in (400, 422)

    _clear(db)


def test_chat_summary_reports_per_channel_unread_and_last_message():
    db = get_incident_db(INCIDENT_ID)
    _clear(db)

    app = create_app()
    with TestClient(app) as client:
        channels = client.get(
            f"/api/incidents/{INCIDENT_ID}/chat/channels", params={"user_id": "u1"}
        ).json()["items"]
        general = next(c for c in channels if c["name"] == "General")
        command = next(c for c in channels if c["name"] == "Command")

        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/summary", params={"user_id": "u1"})
        assert res.status_code == 200, res.text
        by_id = {item["channel_id"]: item for item in res.json()["items"]}
        assert by_id[general["id"]]["unread_count"] == 0
        assert by_id[general["id"]]["last_message"] is None

        client.post(
            f"/api/incidents/{INCIDENT_ID}/chat/channels/{general['id']}/messages",
            json={"sender_id": "u2", "sender_name": "U2", "text": "hello"},
        )
        client.post(
            f"/api/incidents/{INCIDENT_ID}/chat/channels/{command['id']}/messages",
            json={"sender_id": "u1", "text": "self-sent, not unread for u1"},
        )

        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/summary", params={"user_id": "u1"})
        by_id = {item["channel_id"]: item for item in res.json()["items"]}
        assert by_id[general["id"]]["unread_count"] == 1
        assert by_id[general["id"]]["last_message"]["text"] == "hello"
        assert by_id[general["id"]]["last_message"]["sender_name"] == "U2"
        assert by_id[command["id"]]["unread_count"] == 0
        assert by_id[command["id"]]["last_message"]["text"] == "self-sent, not unread for u1"

        res = client.get(f"/api/incidents/{INCIDENT_ID}/chat/summary", params={"user_id": ""})
        assert res.status_code in (400, 422)

    _clear(db)
