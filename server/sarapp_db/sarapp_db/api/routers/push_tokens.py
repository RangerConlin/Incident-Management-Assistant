"""Mobile push-notification token registry (FCM), master-DB scoped.

Devices can be shared across shifts (e.g. a handoff tablet): a token is
per-device, not per-login. Registration is an upsert keyed on `token`, so a
new login on an already-registered device re-associates that token to the
new person instead of accumulating duplicate rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

router = APIRouter()


def _tokens_col():
    return get_master_db()[MasterCollections.PUSH_TOKENS]


def _personnel_col():
    return get_master_db()[MasterCollections.PERSONNEL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _find_person(identifier: Any) -> dict[str, Any] | None:
    """Resolve by person_record (if numeric) or person_id, tolerating an
    unresolvable person (mirrors auth_sessions._find_person)."""
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
    return clean


@router.post("/push-token", status_code=200)
def register_push_token(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    token = str(body.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    person_id_raw = body.get("person_id")
    lookup_key = body.get("person_record") if body.get("person_record") is not None else person_id_raw
    person = _find_person(lookup_key)
    person_record = int(person["person_record"]) if person and person.get("person_record") is not None else None

    now = _utcnow()
    fields = {
        "token": token,
        "person_record": person_record,
        "person_id": str(person_id_raw).strip() if person_id_raw else None,
        "incident_id": body.get("incident_id"),
        "platform": body.get("platform") or "android",
        "device_name": body.get("device_name"),
        "app_version": body.get("app_version"),
        "updated_at": now,
    }
    _tokens_col().update_one(
        {"token": token},
        {"$set": fields, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return _clean(_tokens_col().find_one({"token": token})) or {}


@router.delete("/push-token/{token}", status_code=200)
def unregister_push_token(token: str) -> dict[str, Any]:
    result = _tokens_col().delete_one({"token": token})
    return {"ok": True, "deleted": result.deleted_count > 0}
