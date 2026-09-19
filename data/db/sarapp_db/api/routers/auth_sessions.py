"""User login session and presence API.

The server owns authenticated users and session/presence state.  Desktop uses
these routes today to register local/offline operator context; cloud auth can
reuse the same records when password/token endpoints are added.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.api.routers.personnel import PersonnelRepository
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import DB_MASTER, get_master_db
from sarapp_db.mongo.int_id import next_record_id
from sarapp_db.mongo.mongo_client import get_client

router = APIRouter()

_ACTIVE_STATUSES = {"online", "available", "busy", "away", "offline"}

# Sessions whose last_seen_at is older than this are treated as abandoned
# (client crashed or lost connectivity without a clean logout).  Clients
# heartbeat every ~60s, so 5 minutes tolerates several missed beats.
DEFAULT_ACTIVE_WITHIN_SECONDS = 300


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cutoff_iso(seconds: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return cutoff.isoformat(timespec="seconds")


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
    person_record = clean.get("person_record")
    clean["id"] = str(person_record) if person_record is not None else None
    clean["primary_role"] = clean.get("primary_role") or clean.get("role") or clean.get("rank")
    return clean


def _personnel_repo() -> PersonnelRepository:
    return PersonnelRepository(get_master_db())


def _full_name(person: dict[str, Any]) -> str:
    first = str(person.get("first_name") or "").strip()
    last = str(person.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part) or str(person.get("name") or "").strip()


# Optional master-record fields a client may supply when creating its own
# profile (all stored as plain text on the personnel record).
_PROFILE_TEXT_FIELDS = ("organization", "title", "phone", "email", "radio_id")


def _login_person(person: dict[str, Any]) -> dict[str, Any]:
    """The slice of a personnel record that login clients may see."""

    return {
        "person_record": person.get("person_record"),
        "person_id": str(person.get("person_id") or ""),
        "first_name": person.get("first_name") or "",
        "last_name": person.get("last_name") or "",
        "name": _full_name(person),
        **{field: person.get(field) or "" for field in _PROFILE_TEXT_FIELDS},
    }


def _person_id_matches(person_id: str) -> list[dict[str, Any]]:
    """All personnel records whose visible person_id equals ``person_id``."""

    matches = list(_personnel_col().find({"person_id": person_id}))
    if person_id.isdigit():
        seen = {m.get("person_record") for m in matches}
        for match in _personnel_col().find({"person_id": int(person_id)}):
            if match.get("person_record") not in seen:
                matches.append(match)
    return matches


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
    return _find_unique_person_by_person_id(value)


def _find_unique_person_by_person_id(person_id: Any) -> dict[str, Any] | None:
    if person_id is None:
        return None
    value = str(person_id).strip()
    if not value:
        return None
    matches = list(_personnel_col().find({"person_id": value}).sort("person_record", 1))
    if value.isdigit():
        numeric_matches = list(
            _personnel_col().find({"person_id": int(value)}).sort("person_record", 1)
        )
        seen: set[object] = {
            match.get("_id", match.get("person_record"))
            for match in matches
        }
        for match in numeric_matches:
            key = match.get("_id", match.get("person_record"))
            if key not in seen:
                matches.append(match)
                seen.add(key)
    if len(matches) != 1:
        return None
    return matches[0]


def _resolve_person_record(body: dict[str, Any], existing_user: dict[str, Any] | None = None) -> int | None:
    explicit = body.get("person_record") or body.get("personnel_id")
    if explicit is not None:
        person = _find_person(explicit)
        if person:
            return int(person["person_record"]) if person.get("person_record") is not None else None

    for candidate in (body.get("username"), body.get("user_id")):
        person = _find_unique_person_by_person_id(candidate)
        if person and person.get("person_record") is not None:
            return int(person["person_record"])
    existing_record = (existing_user or {}).get("person_record")
    if existing_record is not None:
        return int(existing_record)
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


@router.get("/lookup")
def lookup_person(person_id: str = Query(...)) -> dict[str, Any]:
    """Check a login ID against the personnel roster.

    Returns ``status`` of ``found`` (with the person), ``not_found`` (the client
    should offer to create a profile) or ``ambiguous`` (several records share
    the ID, so it cannot be used to sign in until the roster is fixed).
    """

    value = person_id.strip()
    if not value:
        raise HTTPException(status_code=400, detail="person_id is required")
    matches = _person_id_matches(value)
    if not matches:
        return {"status": "not_found", "person": None}
    if len(matches) > 1:
        return {"status": "ambiguous", "person": None}
    return {"status": "found", "person": _login_person(matches[0])}


@router.post("/register", status_code=201)
def register_person(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Create the personnel record for a login ID that has none yet."""

    person_id = str(body.get("person_id") or "").strip()
    first_name = str(body.get("first_name") or "").strip()
    last_name = str(body.get("last_name") or "").strip()
    if not (person_id and first_name and last_name):
        raise HTTPException(status_code=400, detail="person_id, first_name and last_name are required")
    if _person_id_matches(person_id):
        raise HTTPException(
            status_code=409,
            detail="A personnel record with this ID already exists; sign in instead.",
        )

    optional = {
        field: str(body.get(field) or "").strip() for field in _PROFILE_TEXT_FIELDS
    }
    repo = _personnel_repo()
    now = _utcnow()
    saved = repo.insert_one(
        {
            "person_record": next_record_id(repo._col, "person_record"),
            "person_id": person_id,
            "first_name": first_name,
            "last_name": last_name,
            **{field: value for field, value in optional.items() if value},
            "status": "available",
            "created_at": now,
            "updated_at": now,
        }
    )
    return {"status": "found", "person": _login_person(saved)}


@router.put("/profile")
def update_profile(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Apply a device's profile to the personnel (master) record for its ID.

    The device is the source of truth for what the person entered, so each
    non-blank field overwrites the record. Blank fields are left alone rather
    than cleared, so a partly filled profile on a new device can't wipe details
    an administrator entered. ``person_id`` identifies the record and is never
    changed here.
    """

    person_id = str(body.get("person_id") or "").strip()
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id is required")
    matches = _person_id_matches(person_id)
    if not matches:
        raise HTTPException(status_code=404, detail="No personnel record matches this ID.")
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Several personnel records share this ID; ask an administrator to fix the roster.",
        )

    person = matches[0]
    updates = {
        field: value
        for field in ("first_name", "last_name", *_PROFILE_TEXT_FIELDS)
        if (value := str(body.get(field) or "").strip())
        and value != str(person.get(field) or "")
    }
    if updates:
        _personnel_repo().update_one(person["_id"], updates)
        person = {**person, **updates}
    return {"status": "found", "person": _login_person(person)}


@router.post("/sessions", status_code=201)
def start_session(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    username = str(body.get("username") or body.get("user_id") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username or user_id is required")

    now = _utcnow()
    user_id = str(body.get("user_id") or username)
    existing_user = _users_col().find_one({"user_id": user_id}) or _users_col().find_one({"username": username})
    person_record = _resolve_person_record(body, existing_user)
    person = _find_person(person_record)
    if person is None:
        ambiguous = len(_person_id_matches(username)) > 1
        raise HTTPException(
            status_code=409 if ambiguous else 404,
            detail=(
                "Several personnel records share this ID; ask an administrator to fix the roster."
                if ambiguous
                else "No personnel record matches this ID; create a profile first."
            ),
        )
    user_doc = {
        "user_id": user_id,
        "username": username,
        "display_name": _full_name(person) or username,
        "badge_number": body.get("badge_number"),
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


def _sweep_abandoned_sessions(active_within_seconds: int) -> None:
    """End sessions that stopped heartbeating without a clean logout.

    Keeps /sessions/active honest after client crashes and cleans up historic
    zombie records (ISO-8601 UTC strings compare correctly as text).
    """

    cutoff = _cutoff_iso(active_within_seconds)
    now = _utcnow()
    _sessions_col().update_many(
        {"ended_at": None, "last_seen_at": {"$lt": cutoff}},
        {"$set": {"status": "offline", "ended_at": now}},
    )


@router.get("/sessions/active")
def list_active_sessions(
    incident_id: str | None = Query(None),
    include_offline: bool = Query(False),
    active_within_seconds: int = Query(DEFAULT_ACTIVE_WITHIN_SECONDS, ge=0),
) -> list[dict[str, Any]]:
    if active_within_seconds:
        _sweep_abandoned_sessions(active_within_seconds)
    query: dict[str, Any] = {"ended_at": None}
    if incident_id:
        query["incident_id"] = incident_id
    if not include_offline:
        query["status"] = {"$ne": "offline"}
    docs = list(_sessions_col().find(query).sort("last_seen_at", -1))
    return [_session_response(doc) for doc in docs]


@router.post("/sessions/{session_id}/heartbeat")
def heartbeat_session(session_id: str) -> dict[str, Any]:
    """Refresh a session's last_seen_at so it stays out of the abandoned sweep."""

    result = _sessions_col().update_one(
        {"session_id": session_id, "ended_at": None},
        {"$set": {"last_seen_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Active session not found")
    return {"ok": True, "session_id": session_id}


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
