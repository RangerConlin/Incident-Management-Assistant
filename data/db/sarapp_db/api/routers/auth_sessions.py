"""User login session and presence API.

The server owns authenticated users and session/presence state.  Desktop uses
these routes today to register local/offline operator context; cloud auth can
reuse the same records when password/token endpoints are added.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.mongo_client import get_client

router = APIRouter()

_ACTIVE_STATUSES = {"online", "available", "busy", "away", "offline"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _master_db():
    return get_client()[DB_MASTER]


def _users_col():
    return _master_db()[MasterCollections.USERS]


def _sessions_col():
    return _master_db()[MasterCollections.USER_SESSIONS]


def _personnel_col():
    return _master_db()[MasterCollections.PERSONNEL]


def _clean_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    clean = dict(doc)
    clean.pop("_id", None)
    return clean


def _normalize_person(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    clean = _clean_doc(doc)
    if not clean:
        return None
    person_id = next((clean[k] for k in ("person_id", "int_id", "id") if clean.get(k) is not None), None)
    clean["id"] = str(person_id) if person_id is not None else None
    clean["primary_role"] = clean.get("primary_role") or clean.get("role") or clean.get("rank")
    return clean


def _find_person(identifier: Any) -> dict[str, Any] | None:
    if identifier is None:
        return None
    value = str(identifier).strip()
    if not value:
        return None
    if value.isdigit():
        doc = _personnel_col().find_one({"person_record": int(value)})
        if doc:
            return doc
    return _personnel_col().find_one({"person_id": value})


def _resolve_person_record(body: dict[str, Any], existing_user: dict[str, Any] | None = None) -> int | None:
    explicit = body.get("person_record") or body.get("personnel_id") or (existing_user or {}).get("person_record")
    person = _find_person(explicit)
    if person:
        return int(person["person_record"]) if person.get("person_record") is not None else None

    for candidate in (body.get("username"), body.get("user_id"), body.get("badge_number")):
        person = _find_person(candidate)
        if person and person.get("person_record") is not None:
            return int(person["person_record"])
    return None


def _normalize_status(status: Any) -> str:
    value = str(status or "online").strip().lower()
    return value if value in _ACTIVE_STATUSES else "online"


def _public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    clean = _clean_doc(user)
    if not clean:
        return None
    clean.pop("password_hash", None)
    clean.pop("password_salt", None)
    return clean


def _session_response(session: dict[str, Any]) -> dict[str, Any]:
    doc = _clean_doc(session) or {}
    user = _users_col().find_one({"user_id": doc.get("user_id")})
    person = _find_person(doc.get("person_record") or (user or {}).get("person_record"))
    doc["user"] = _public_user(user)
    doc["personnel"] = _normalize_person(person)
    return doc


@router.post("/sessions", status_code=201)
def start_session(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    username = str(body.get("username") or body.get("user_id") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username or user_id is required")

    now = _utcnow()
    user_id = str(body.get("user_id") or username)
    existing_user = _users_col().find_one({"user_id": user_id}) or _users_col().find_one({"username": username})
    person_record = _resolve_person_record(body, existing_user)
    user_doc = {
        "user_id": user_id,
        "username": username,
        "display_name": body.get("display_name") or body.get("name") or username,
        "badge_number": body.get("badge_number") or username,
        "person_record": person_record,
        "updated_at": now,
    }
    if existing_user:
        _users_col().update_one({"_id": existing_user["_id"]}, {"$set": user_doc})
    else:
        user_doc["created_at"] = now
        _users_col().insert_one(user_doc)

    session = {
        "session_id": str(uuid4()),
        "user_id": user_id,
        "username": username,
        "display_name": user_doc["display_name"],
        "person_record": person_record,
        "role": body.get("role") or "",
        "status": _normalize_status(body.get("status")),
        "mode": body.get("mode") or "",
        "incident_id": body.get("incident_id"),
        "device_name": body.get("device_name") or "",
        "started_at": now,
        "last_seen_at": now,
        "ended_at": None,
    }
    _sessions_col().insert_one(session)
    return _session_response(session)


@router.get("/sessions/active")
def list_active_sessions(
    incident_id: str | None = Query(None),
    include_offline: bool = Query(False),
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"ended_at": None}
    if incident_id:
        query["incident_id"] = incident_id
    if not include_offline:
        query["status"] = {"$ne": "offline"}
    docs = list(_sessions_col().find(query).sort("last_seen_at", -1))
    return [_session_response(doc) for doc in docs]


@router.patch("/sessions/{session_id}/status")
def update_session_status(session_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    status = _normalize_status(body.get("status"))
    update = {"status": status, "last_seen_at": _utcnow()}
    result = _sessions_col().update_one({"session_id": session_id, "ended_at": None}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Active session not found")
    doc = _sessions_col().find_one({"session_id": session_id})
    return _session_response(doc or {})


@router.post("/sessions/{session_id}/logout")
def end_session(session_id: str) -> dict[str, Any]:
    now = _utcnow()
    result = _sessions_col().update_one(
        {"session_id": session_id, "ended_at": None},
        {"$set": {"status": "offline", "last_seen_at": now, "ended_at": now}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Active session not found")
    doc = _sessions_col().find_one({"session_id": session_id})
    return _session_response(doc or {})


@router.get("/users")
def list_users() -> list[dict[str, Any]]:
    users = list(_users_col().find().sort("display_name", 1))
    return [_public_user(user) or {} for user in users]
