"""FastAPI router for the Logistics resource status board."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.client import get_db
from sarapp_db.mongo.collection_names import IncidentCollections

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _items_col(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.LOGISTICS_RESOURCE_STATUS_ITEMS]


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Resource status items
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/logistics/resource-status")
def list_resources(incident_id: str) -> list[dict]:
    col = _items_col(incident_id)
    return [_strip(d) for d in col.find(sort=[("resource_type", 1), ("resource_name", 1)])]


@router.post("/incidents/{incident_id}/logistics/resource-status", status_code=201)
def create_resource(incident_id: str, body: dict[str, Any]) -> dict:
    col = _items_col(incident_id)
    now = _now()
    doc = {
        **body,
        "id": body.get("id") or _new_id(),
        "last_updated": now,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}")
def get_resource(incident_id: str, resource_status_id: str) -> dict:
    col = _items_col(incident_id)
    doc = col.find_one({"id": resource_status_id})
    if not doc:
        raise HTTPException(404, "Resource status item not found")
    return _strip(doc)


@router.patch("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}")
def update_resource(incident_id: str, resource_status_id: str, body: dict[str, Any]) -> dict:
    col = _items_col(incident_id)
    now = _now()
    body.pop("id", None)
    body["last_updated"] = now
    body["updated_at"] = now
    result = col.find_one_and_update(
        {"id": resource_status_id},
        {"$set": body},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, "Resource status item not found")
    return _strip(result)


@router.get("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}/by-source")
def get_by_source(incident_id: str, source_entity_type: str, source_record_id: str) -> dict | None:
    col = _items_col(incident_id)
    doc = col.find_one({"source_entity_type": source_entity_type, "source_record_id": source_record_id})
    return _strip(doc) if doc else None


@router.post("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}/audit", status_code=201)
def append_audit(incident_id: str, resource_status_id: str, body: list[dict[str, Any]]) -> dict:
    col = _items_col(incident_id)
    result = col.find_one_and_update(
        {"id": resource_status_id},
        {"$push": {"audit": {"$each": body}}},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, "Resource status item not found")
    return {"ok": True}


@router.get("/incidents/{incident_id}/logistics/resource-status/{resource_status_id}/audit")
def list_audit(incident_id: str, resource_status_id: str, limit: int = 50) -> list[dict]:
    col = _items_col(incident_id)
    doc = col.find_one({"id": resource_status_id}, {"audit": 1})
    if not doc:
        raise HTTPException(404, "Resource status item not found")
    entries = list(reversed(doc.get("audit") or []))
    return entries[:limit]
