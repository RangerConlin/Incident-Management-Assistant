"""Incident-scoped chat, shared by the desktop app, mobile app, and web client.

Two collections: `chat_channels` (group channels and 1:1 DMs) and `messages`
(scoped by `channel_id`). Both ride the existing
`/api/incidents/{incident_id}/ws` broadcast — BaseRepository announces every
write to that hub automatically, no separate chat socket needed. Clients
POST to send/create, GET for history/backfill or the channel list on join or
reconnect, and otherwise listen on the incident WebSocket for live updates.

Every incident is seeded with a default set of ICS-section channels the
first time its channel list is loaded (see `_ensure_default_channels`), on
top of which users can create their own channels and DMs.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

DEFAULT_CHANNEL_NAMES = [
    "General",
    "Command",
    "Operations",
    "Planning",
    "Logistics",
    "Finance/Admin",
]


class ChatChannelRepository(BaseRepository):
    collection_name = IncidentCollections.CHAT_CHANNELS


class ChatRepository(BaseRepository):
    collection_name = IncidentCollections.MESSAGES
    # Messages are an append-only log; nothing here is ever edited or
    # soft-deleted, so skip the `deleted` filtering BaseRepository does by
    # default for every read.
    soft_deletes = False


def _channel_repo(incident_id: str) -> ChatChannelRepository:
    return ChatChannelRepository(get_incident_db(incident_id))


def _message_repo(incident_id: str) -> ChatRepository:
    return ChatRepository(get_incident_db(incident_id))


def _clean(doc: dict[str, Any]) -> dict[str, Any]:
    clean = dict(doc)
    clean["id"] = clean.pop("_id")
    return clean


def _dm_key(user_a: str, user_b: str) -> str:
    return "|".join(sorted([user_a, user_b]))


def _ensure_default_channels(repo: ChatChannelRepository) -> None:
    if repo.count({"type": "group"}) > 0:
        return
    for name in DEFAULT_CHANNEL_NAMES:
        repo.insert_one(
            {
                "type": "group",
                "name": name,
                "participant_ids": [],
                "created_by": "system",
            }
        )


@router.post("/incidents/{incident_id}/chat/channels", status_code=201)
def create_channel(incident_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    created_by = str(body.get("created_by") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not created_by:
        raise HTTPException(status_code=400, detail="created_by is required")

    participant_ids = body.get("participant_ids") or []
    doc = _channel_repo(incident_id).insert_one(
        {
            "type": "group",
            "name": name,
            "participant_ids": [str(p) for p in participant_ids],
            "created_by": created_by,
        }
    )
    return _clean(doc)


@router.get("/incidents/{incident_id}/chat/channels")
def list_channels(incident_id: str, user_id: str = Query(...)) -> dict[str, Any]:
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    repo = _channel_repo(incident_id)
    _ensure_default_channels(repo)
    docs = repo.find_many(
        {"$or": [{"type": "group"}, {"type": "dm", "participant_ids": user_id}]},
        sort=[("created_at", 1)],
    )
    return {"items": [_clean(doc) for doc in docs]}


@router.post("/incidents/{incident_id}/chat/dms", status_code=200)
def find_or_create_dm(incident_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    user_a = str(body.get("user_a") or "").strip()
    user_b = str(body.get("user_b") or "").strip()
    if not user_a or not user_b:
        raise HTTPException(status_code=400, detail="user_a and user_b are required")
    if user_a == user_b:
        raise HTTPException(status_code=400, detail="user_a and user_b must be different")

    repo = _channel_repo(incident_id)
    key = _dm_key(user_a, user_b)
    existing = repo.find_one({"type": "dm", "dm_key": key})
    if existing is not None:
        return _clean(existing)

    doc = repo.insert_one(
        {
            "type": "dm",
            "name": None,
            "participant_ids": [user_a, user_b],
            "dm_key": key,
            "created_by": user_a,
        }
    )
    return _clean(doc)


@router.post("/incidents/{incident_id}/chat/channels/{channel_id}/messages", status_code=201)
def send_message(incident_id: str, channel_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    sender_id = str(body.get("sender_id") or "").strip()
    text = str(body.get("text") or "").strip()
    if not sender_id:
        raise HTTPException(status_code=400, detail="sender_id is required")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    doc = _message_repo(incident_id).insert_one(
        {
            "channel_id": channel_id,
            "sender_id": sender_id,
            "sender_name": body.get("sender_name"),
            "text": text,
        }
    )
    return _clean(doc)


@router.get("/incidents/{incident_id}/chat/channels/{channel_id}/messages")
def list_messages(
    incident_id: str,
    channel_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    before: str | None = Query(default=None, description="Return messages created before this ISO timestamp"),
) -> dict[str, Any]:
    query: dict[str, Any] = {"channel_id": channel_id}
    if before:
        query["created_at"] = {"$lt": before}
    docs = _message_repo(incident_id).find_many(
        query,
        sort=[("created_at", -1)],
        limit=limit,
    )
    docs.reverse()
    return {"items": [_clean(doc) for doc in docs]}
