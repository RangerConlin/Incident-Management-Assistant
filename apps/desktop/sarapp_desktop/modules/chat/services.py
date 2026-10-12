"""HTTP-backed service functions for incident chat.

Mirrors the module `services.py` pattern used elsewhere (e.g.
`modules/ics214/services.py`) — all reads/writes go through `api_client`,
never a Mongo repository directly, per the UI -> API server -> MongoDB rule
in agents.md.
"""

from __future__ import annotations

from typing import Any


def _client():
    from utils.api_client import api_client

    return api_client


def list_channels(incident_id: str, *, user_id: str) -> list[dict[str, Any]]:
    response = _client().get(
        f"/api/incidents/{incident_id}/chat/channels", params={"user_id": user_id}
    )
    return response.get("items", [])


def create_channel(
    incident_id: str,
    *,
    name: str,
    created_by: str,
    participant_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _client().post(
        f"/api/incidents/{incident_id}/chat/channels",
        json={
            "name": name,
            "created_by": created_by,
            "participant_ids": participant_ids or [],
        },
    )


def find_or_create_dm(incident_id: str, *, user_a: str, user_b: str) -> dict[str, Any]:
    return _client().post(
        f"/api/incidents/{incident_id}/chat/dms",
        json={"user_a": user_a, "user_b": user_b},
    )


def list_messages(
    incident_id: str,
    channel_id: str,
    *,
    limit: int = 100,
    before: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if before:
        params["before"] = before
    response = _client().get(
        f"/api/incidents/{incident_id}/chat/channels/{channel_id}/messages", params=params
    )
    return response.get("items", [])


def send_message(
    incident_id: str,
    channel_id: str,
    *,
    sender_id: str,
    text: str,
    sender_name: str | None = None,
) -> dict[str, Any]:
    return _client().post(
        f"/api/incidents/{incident_id}/chat/channels/{channel_id}/messages",
        json={
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
        },
    )


def resolve_display_name(person_record: str) -> str:
    """Best-effort lookup of a person's display name from the master roster.

    AppState only stores the active user's id, not a friendly name, so chat
    resolves one on demand the same way other modules do (e.g.
    `modules/statusboards/resource_status_desk.py`). Falls back to the raw id
    if the lookup fails or the record has no name — never raises, since a
    missing display name shouldn't block sending a message.
    """
    try:
        master = _client().get(f"/api/master/personnel/{person_record}") or {}
    except Exception:
        return person_record
    return master.get("name") or person_record
