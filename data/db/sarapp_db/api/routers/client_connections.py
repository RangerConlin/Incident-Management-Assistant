"""Device/client connection registry shared by mobile, web, and desktop.

This is the durable client identity/session layer. Push notification tokens
are optional delivery addresses attached to a connection; location tracking
uses the connection token directly and does not depend on notification
permission.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

router = APIRouter()


def _connections_col():
    return get_master_db()[MasterCollections.CLIENT_CONNECTIONS]


def _personnel_col():
    return get_master_db()[MasterCollections.PERSONNEL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


def _clean(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    clean = dict(doc)
    clean.pop("_id", None)
    clean.pop("connection_token_hash", None)
    return clean


def resolve_connection_token(token: str) -> dict[str, Any] | None:
    """Return an active connection doc for a bearer/body connection token."""
    value = str(token or "").strip()
    if not value:
        return None
    return _connections_col().find_one(
        {"connection_token_hash": _hash_token(value), "status": {"$ne": "revoked"}}
    )


@router.post("/register", status_code=200)
def register_connection(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    device_id = str(body.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    person_id_raw = body.get("person_id")
    lookup_key = body.get("person_record") if body.get("person_record") is not None else person_id_raw
    person = _find_person(lookup_key)
    person_record = int(person["person_record"]) if person and person.get("person_record") is not None else None
    if person_record is None:
        raise HTTPException(status_code=400, detail="person_record could not be resolved")

    now = _utcnow()
    existing = _connections_col().find_one({"device_id": device_id})
    connection_token = secrets.token_urlsafe(32)
    fields = {
        "device_id": device_id,
        "connection_token_hash": _hash_token(connection_token),
        "platform": body.get("platform") or "mobile",
        "device_name": body.get("device_name"),
        "app_version": body.get("app_version"),
        "person_record": person_record,
        "person_id": str(person_id_raw).strip() if person_id_raw else person.get("person_id"),
        "incident_id": body.get("incident_id"),
        "team_id": body.get("team_id"),
        "team_name": body.get("team_name"),
        "role": body.get("role"),
        "status": "active",
        "location_tracking_enabled": bool(body.get("location_tracking_enabled", False)),
        "fcm_token": body.get("fcm_token"),
        "push_provider": "fcm" if body.get("fcm_token") else None,
        "notification_permission": body.get("notification_permission"),
        "last_seen_at": now,
        "updated_at": now,
    }
    if existing:
        _connections_col().update_one({"_id": existing["_id"]}, {"$set": fields})
        doc = _connections_col().find_one({"_id": existing["_id"]})
    else:
        fields["created_at"] = now
        inserted = _connections_col().insert_one(fields)
        doc = _connections_col().find_one({"_id": inserted.inserted_id})

    response = _clean(doc) or {}
    response["connection_token"] = connection_token
    return response


@router.patch("/{device_id}/push-token", status_code=200)
def update_push_token(device_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    doc = _connections_col().find_one({"device_id": device_id})
    if not doc:
        raise HTTPException(status_code=404, detail="client connection not found")
    now = _utcnow()
    updates = {
        "fcm_token": body.get("fcm_token"),
        "push_provider": "fcm" if body.get("fcm_token") else None,
        "notification_permission": body.get("notification_permission"),
        "last_seen_at": now,
        "updated_at": now,
    }
    _connections_col().update_one({"_id": doc["_id"]}, {"$set": updates})
    return _clean(_connections_col().find_one({"_id": doc["_id"]})) or {}


@router.post("/{device_id}/heartbeat", status_code=200)
def heartbeat(device_id: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    doc = _connections_col().find_one({"device_id": device_id})
    if not doc:
        raise HTTPException(status_code=404, detail="client connection not found")
    now = _utcnow()
    updates = {"last_seen_at": now, "updated_at": now, "status": "active"}
    if "location_tracking_enabled" in body:
        updates["location_tracking_enabled"] = bool(body.get("location_tracking_enabled"))
    _connections_col().update_one({"_id": doc["_id"]}, {"$set": updates})
    return _clean(_connections_col().find_one({"_id": doc["_id"]})) or {}


@router.get("", status_code=200)
def list_connections() -> list[dict[str, Any]]:
    return [
        _clean(doc) or {}
        for doc in _connections_col().find({}, sort=[("last_seen_at", -1)])
    ]
