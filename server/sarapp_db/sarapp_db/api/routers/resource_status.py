"""Unified resource status router (per-incident).

All resource types (personnel, vehicle, aircraft, equipment) tracked in a
single ``resource_status`` collection.  Every resource assigned to an incident
in any planning state gets one document here.

Endpoints are mounted under /api/incidents/{incident_id}/resource-status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

CHECKED_IN_STATUSES = {
    "Checked In",
    "Assigned",
    "Available",
    "Out of Service",
    "Preparing for Demobilization",
}


class ResourceStatusRepository(BaseRepository):
    collection_name = IncidentCollections.RESOURCE_STATUS


def _repo(incident_id: str) -> ResourceStatusRepository:
    return ResourceStatusRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _strip(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    oid = d.pop("_id", None)
    if oid is not None and "id" not in d:
        d["id"] = str(oid)
    return d


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------

@router.get("")
def list_resource_status(
    incident_id: str,
    entity_type: str = Query(""),
    status: str = Query(""),
) -> list[dict[str, Any]]:
    repo = _repo(incident_id)
    query: dict[str, Any] = {}
    if entity_type:
        query["entity_type"] = entity_type
    if status:
        query["status"] = status
    docs = repo.find_many(query, sort=[("resource_name", 1)])
    return [_strip(d) for d in docs]


@router.get("/by-entity")
def get_by_entity(
    incident_id: str,
    entity_type: str = Query(...),
    record_id: str = Query(...),
) -> dict[str, Any] | None:
    repo = _repo(incident_id)
    rid = int(record_id) if record_id.isdigit() else record_id
    doc = repo.find_one({"entity_type": entity_type, "record_id": rid})
    return _strip(doc) if doc else None


@router.get("/{item_id}")
def get_resource_status(incident_id: str, item_id: str) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = repo.find_by_id(item_id)
    if not doc:
        raise HTTPException(404, f"Resource status {item_id} not found")
    return _strip(doc)


# ---------------------------------------------------------------------------
# Create / upsert
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def upsert_resource_status(
    incident_id: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Upsert on (entity_type, record_id).

    Creates a new document if the resource has no entry yet; updates the
    existing document otherwise.  Idempotent — safe to call from multiple
    callers (desk sync, check-in service, board UI).
    """
    entity_type = str(body.get("entity_type") or "").strip()
    record_id_raw = body.get("record_id")
    if not entity_type or record_id_raw is None:
        raise HTTPException(400, "entity_type and record_id are required")

    record_id = int(record_id_raw) if str(record_id_raw).isdigit() else record_id_raw
    now = _utcnow()
    repo = _repo(incident_id)

    existing = repo.find_one({"entity_type": entity_type, "record_id": record_id})

    if existing:
        # Update non-identity fields; preserve status_log and existing status
        # unless a new status is explicitly supplied.
        updates: dict[str, Any] = {"updated_at": now}
        for field in (
            "resource_id", "resource_name", "resource_type", "eta_utc", "assigned_to",
            "assignment_reference", "location", "notes",
        ):
            if field in body:
                updates[field] = body[field]

        new_status = str(body.get("status") or "").strip()
        if new_status and new_status != existing.get("status"):
            updates["status"] = new_status
            entry = {"status": new_status, "timestamp": now, "changed_by": str(body.get("changed_by") or "")}
            repo.apply_update(existing["_id"], {"$set": updates, "$push": {"status_log": entry}})
        else:
            repo.update_one(existing["_id"], updates)

        saved = repo.find_by_id(existing["_id"])
        return _strip(saved) if saved else {}

    # New document
    status = str(body.get("status") or "Pending").strip()
    if status == "Checked In" and not body.get("checked_in_time"):
        body["checked_in_time"] = now

    doc = {
        "entity_type": entity_type,
        "record_id": record_id,
        "resource_id": body.get("resource_id") or str(record_id),
        "resource_name": str(body.get("resource_name") or record_id),
        "resource_type": str(body.get("resource_type") or entity_type.title()),
        "status": status,
        "status_log": [{"status": status, "timestamp": now, "changed_by": str(body.get("changed_by") or "")}],
        "eta_utc": body.get("eta_utc"),
        "assigned_to": body.get("assigned_to"),
        "assignment_reference": body.get("assignment_reference"),
        "location": body.get("location"),
        "notes": body.get("notes"),
        "checked_in_time": body.get("checked_in_time"),
        "created_at": now,
        "updated_at": now,
    }
    inserted = repo.insert_one(doc)
    return _strip(inserted)


# ---------------------------------------------------------------------------
# Update non-status fields
# ---------------------------------------------------------------------------

@router.patch("/{item_id}")
def patch_resource_status(
    incident_id: str,
    item_id: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = repo.find_by_id(item_id)
    if not doc:
        raise HTTPException(404, f"Resource status {item_id} not found")

    updates: dict[str, Any] = {"updated_at": _utcnow()}
    for field in (
        "resource_id", "resource_name", "resource_type", "eta_utc", "assigned_to",
        "assignment_reference", "location", "notes", "checked_in_time",
    ):
        if field in body:
            updates[field] = body[field]

    repo.update_one(doc["_id"], updates)
    saved = repo.find_by_id(doc["_id"])
    return _strip(saved) if saved else {}


# ---------------------------------------------------------------------------
# Status transition
# ---------------------------------------------------------------------------

@router.patch("/{item_id}/status")
def update_status(
    incident_id: str,
    item_id: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Apply a status transition.

    Appends an entry to status_log, updates the status field, and stamps
    checked_in_time when transitioning into a checked-in state.
    """
    repo = _repo(incident_id)
    doc = repo.find_by_id(item_id)
    if not doc:
        raise HTTPException(404, f"Resource status {item_id} not found")

    new_status = str(body.get("status") or "").strip()
    if not new_status:
        raise HTTPException(400, "status is required")

    now = _utcnow()
    entry = {"status": new_status, "timestamp": now, "changed_by": str(body.get("changed_by") or "")}

    updates: dict[str, Any] = {"status": new_status, "updated_at": now}
    if new_status in CHECKED_IN_STATUSES and not doc.get("checked_in_time"):
        updates["checked_in_time"] = now

    repo.apply_update(doc["_id"], {"$set": updates, "$push": {"status_log": entry}})
    saved = repo.find_by_id(doc["_id"])
    return _strip(saved) if saved else {}
