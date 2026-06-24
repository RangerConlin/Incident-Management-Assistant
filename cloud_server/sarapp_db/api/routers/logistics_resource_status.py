"""FastAPI router for the Logistics resource status board."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class LogisticsResourceStatusItemsRepository(BaseRepository):
    collection_name = IncidentCollections.LOGISTICS_RESOURCE_STATUS_ITEMS
    # Keyed by app-defined `id` (hex uuid), not `_id`; no `deleted` field.
    soft_deletes = False


def _repo(incident_id: str) -> LogisticsResourceStatusItemsRepository:
    return LogisticsResourceStatusItemsRepository(get_incident_db(incident_id))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Resource status items
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/logistics/resource-status")
def list_resources(incident_id: str) -> list[dict]:
    repo = _repo(incident_id)
    docs = repo.find_many({}, sort=[("resource_type", 1), ("resource_name", 1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/logistics/resource-status", status_code=201)
def create_resource(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    now = _now()
    doc = {
        **body,
        "id": body.get("id") or _new_id(),
        "last_updated": now,
    }
    saved = repo.insert_one(doc)
    return _strip(saved)


@router.get("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}")
def get_resource(incident_id: str, resource_status_id: str) -> dict:
    repo = _repo(incident_id)
    doc = repo.find_one({"id": resource_status_id})
    if not doc:
        raise HTTPException(404, "Resource status item not found")
    return _strip(doc)


@router.patch("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}")
def update_resource(incident_id: str, resource_status_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    existing = repo.find_one({"id": resource_status_id})
    if not existing:
        raise HTTPException(404, "Resource status item not found")
    body.pop("id", None)
    body["last_updated"] = _now()
    repo.update_one(existing["_id"], body)
    result = repo.find_by_id(existing["_id"])
    return _strip(result)


@router.get("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}/by-source")
def get_by_source(incident_id: str, source_entity_type: str, source_record_id: str) -> dict | None:
    repo = _repo(incident_id)
    doc = repo.find_one({"source_entity_type": source_entity_type, "source_record_id": source_record_id})
    return _strip(doc) if doc else None


@router.post("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}/audit", status_code=201)
def append_audit(incident_id: str, resource_status_id: str, body: list[dict[str, Any]]) -> dict:
    repo = _repo(incident_id)
    existing = repo.find_one({"id": resource_status_id})
    if not existing:
        raise HTTPException(404, "Resource status item not found")
    # $push to an embedded array — not expressible via BaseRepository's
    # generic methods, so we drop to the raw collection and broadcast
    # ourselves, mirroring update_one's pattern.
    repo._col.update_one(
        {"id": resource_status_id},
        {"$push": {"audit": {"$each": body}}},
    )
    result = repo._col.find_one({"id": resource_status_id})
    if result:
        repo._broadcast("updated", result["_id"], result)
    return {"ok": True}


@router.get("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}/audit")
def list_audit(incident_id: str, resource_status_id: str, limit: int = 50) -> list[dict]:
    repo = _repo(incident_id)
    doc = repo.find_one({"id": resource_status_id})
    if not doc:
        raise HTTPException(404, "Resource status item not found")
    entries = list(reversed(doc.get("audit") or []))
    return entries[:limit]
