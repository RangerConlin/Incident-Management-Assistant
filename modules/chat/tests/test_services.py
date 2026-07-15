from __future__ import annotations

from utils.api_client import api_client

from modules.chat import services


def test_list_channels_passes_user_id(monkeypatch):
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        return {"items": [{"id": "c1", "type": "group", "name": "General"}]}

    monkeypatch.setattr(api_client, "get", fake_get)

    items = services.list_channels("incident-1", user_id="u1")

    assert calls == [("/api/incidents/incident-1/chat/channels", {"user_id": "u1"})]
    assert items == [{"id": "c1", "type": "group", "name": "General"}]


def test_create_channel_posts_expected_payload(monkeypatch):
    calls = []

    def fake_post(path, json=None, params=None):
        calls.append((path, json))
        return {"id": "c2", **json}

    monkeypatch.setattr(api_client, "post", fake_post)

    result = services.create_channel(
        "incident-1", name="Ops", created_by="u1", participant_ids=["u2"]
    )

    assert calls == [
        (
            "/api/incidents/incident-1/chat/channels",
            {"name": "Ops", "created_by": "u1", "participant_ids": ["u2"]},
        )
    ]
    assert result["id"] == "c2"


def test_find_or_create_dm_posts_expected_payload(monkeypatch):
    calls = []

    def fake_post(path, json=None, params=None):
        calls.append((path, json))
        return {"id": "c3", **json}

    monkeypatch.setattr(api_client, "post", fake_post)

    result = services.find_or_create_dm("incident-1", user_a="u1", user_b="u2")

    assert calls == [
        ("/api/incidents/incident-1/chat/dms", {"user_a": "u1", "user_b": "u2"})
    ]
    assert result["id"] == "c3"


def test_list_messages_passes_channel_id_and_limit(monkeypatch):
    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        return {"items": [{"id": "m1", "channel_id": "c1", "text": "hi"}]}

    monkeypatch.setattr(api_client, "get", fake_get)

    items = services.list_messages("incident-1", "c1", limit=50)

    assert calls == [
        ("/api/incidents/incident-1/chat/channels/c1/messages", {"limit": 50})
    ]
    assert items == [{"id": "m1", "channel_id": "c1", "text": "hi"}]


def test_send_message_posts_expected_payload(monkeypatch):
    calls = []

    def fake_post(path, json=None, params=None):
        calls.append((path, json))
        return {"id": "m2", **json}

    monkeypatch.setattr(api_client, "post", fake_post)

    result = services.send_message(
        "incident-1", "c1", sender_id="u1", text="hello", sender_name="Brendan"
    )

    assert calls == [
        (
            "/api/incidents/incident-1/chat/channels/c1/messages",
            {"sender_id": "u1", "sender_name": "Brendan", "text": "hello"},
        )
    ]
    assert result["id"] == "m2"


def test_resolve_display_name_falls_back_on_error(monkeypatch):
    def fake_get(path, params=None):
        raise RuntimeError("unreachable")

    monkeypatch.setattr(api_client, "get", fake_get)

    assert services.resolve_display_name("u1") == "u1"


def test_resolve_display_name_uses_master_name(monkeypatch):
    monkeypatch.setattr(api_client, "get", lambda path, params=None: {"name": "Brendan Pheley"})

    assert services.resolve_display_name("u1") == "Brendan Pheley"
