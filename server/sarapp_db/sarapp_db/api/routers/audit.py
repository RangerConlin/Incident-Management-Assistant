"""Audit log API.

POST /api/audit  — record an audit event (best-effort; always returns 201)
GET  /api/audit  — retrieve recent events (debug / admin use)

Global events (no incident_id) go into SystemCollections.AUDIT_GLOBAL.
Incident-scoped events go into IncidentCollections.AUDIT_LOGS via BaseRepository
so they are broadcast to connected clients like every other incident write.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections, SystemCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_system_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class AuditLogRepository(BaseRepository):
    collection_name = IncidentCollections.AUDIT_LOGS
    soft_deletes = False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _system_col():
    return get_system_db()[SystemCollections.AUDIT_GLOBAL]


class AuditRequest(BaseModel):
    action: str
    detail: Optional[dict[str, Any]] = None
    incident_id: Optional[str] = None
    user_id: Optional[str] = None
    ts_utc: Optional[str] = None


@router.post("", status_code=201)
def write_audit_event(body: AuditRequest) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "ts_utc": body.ts_utc or _utcnow(),
        "action": body.action,
        "detail": body.detail,
        "incident_id": body.incident_id,
        "user_id": body.user_id,
    }
    try:
        if body.incident_id:
            repo = AuditLogRepository(get_incident_db(body.incident_id))
            inserted = repo.insert_one(doc)
            return {"id": str(inserted.get("_id", ""))}
        else:
            result = _system_col().insert_one(doc)
            return {"id": str(result.inserted_id)}
    except Exception:
        return {"id": ""}


@router.get("")
def get_audit_events(
    incident_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=200),
) -> list[dict[str, Any]]:
    try:
        if incident_id:
            col = get_incident_db(incident_id)[IncidentCollections.AUDIT_LOGS]
        else:
            col = _system_col()
        docs = list(col.find().sort("_id", -1).limit(limit))
        return [{k: v for k, v in d.items() if k != "_id"} for d in docs]
    except Exception:
        return []
