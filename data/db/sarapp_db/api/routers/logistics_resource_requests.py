"""FastAPI router for the Logistics Resource Request (ICS-213RR) module."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

ACTION_STATUS_MAP = {
    "SUBMIT": "SUBMITTED",
    "REVIEW": "REVIEWED",
    "APPROVE": "APPROVED",
    "DENY": "DENIED",
    "CANCEL": "CANCELLED",
    "REOPEN": "REVIEWED",
}

ALLOWED_STATUS_TRANSITIONS = {
    "DRAFT": {"DRAFT", "SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"REVIEWED", "DENIED", "CANCELLED"},
    "REVIEWED": {"APPROVED", "DENIED", "CANCELLED"},
    "APPROVED": {"ASSIGNED", "DENIED", "CANCELLED"},
    "ASSIGNED": {"INTRANSIT", "CANCELLED"},
    "INTRANSIT": {"DELIVERED", "PARTIAL", "CANCELLED"},
    "DELIVERED": {"CLOSED", "PARTIAL"},
    "PARTIAL": {"CLOSED", "ASSIGNED"},
    "DENIED": {"REVIEWED"},
    "CANCELLED": {"REVIEWED"},
    "CLOSED": set(),
}


class LogisticsResourceRequestsRepository(BaseRepository):
    collection_name = IncidentCollections.LOGISTICS_RESOURCE_REQUESTS
    # Keyed by app-defined `id` (hex uuid), not `_id`; no `deleted` field.
    soft_deletes = False


def _repo(incident_id: str) -> LogisticsResourceRequestsRepository:
    return LogisticsResourceRequestsRepository(get_incident_db(incident_id))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _fetch(repo: LogisticsResourceRequestsRepository, request_id: str) -> dict:
    doc = repo.find_one({"id": request_id})
    if not doc:
        raise HTTPException(404, f"Resource request not found: {request_id}")
    return doc


# ---------------------------------------------------------------------------
# List / create requests
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/logistics/resource-requests")
def list_requests(
    incident_id: str,
    status: str | None = None,
    priority: str | None = None,
    text: str | None = None,
) -> list[dict]:
    repo = _repo(incident_id)
    query: dict = {"incident_id": incident_id}
    if status:
        query["status"] = status.upper()
    if priority:
        query["priority"] = priority.upper()
    if text:
        import re
        pattern = re.compile(re.escape(text), re.IGNORECASE)
        query["$or"] = [{"title": pattern}, {"justification": pattern}]
    docs = repo._col.find(query, {"items": 0, "approvals": 0, "fulfillments": 0, "audit": 0}, sort=[("created_utc", -1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/logistics/resource-requests", status_code=201)
def create_request(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    now = _now()
    request_id = body.get("id") or _new_id()
    items = body.pop("items", [])
    doc = {
        **body,
        "id": request_id,
        "incident_id": incident_id,
        "status": body.get("status", "DRAFT"),
        "created_utc": body.get("created_utc", now),
        "last_updated_utc": now,
        "version": body.get("version", 1),
        "items": [{"id": item.get("id") or _new_id(), **item} for item in items],
        "approvals": [],
        "fulfillments": [],
        "audit": [{"event": "create", "ts_utc": now, "actor_id": body.get("created_by_id")}],
    }
    saved = repo.insert_one(doc)
    return _strip(saved)


# ---------------------------------------------------------------------------
# Get / update single request
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/logistics/resource-requests/{request_id}")
def get_request(incident_id: str, request_id: str) -> dict:
    repo = _repo(incident_id)
    doc = _fetch(repo, request_id)
    return _strip(doc)


@router.patch("/incidents/{incident_id}/logistics/resource-requests/{request_id}")
def update_request(incident_id: str, request_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    doc = _fetch(repo, request_id)
    body.pop("id", None)
    body.pop("incident_id", None)
    actor_id = body.pop("actor_id", None)
    if doc.get("status", "DRAFT") != "DRAFT":
        body["version"] = doc.get("version", 1) + 1
    audit_entry = {"event": "update", "ts_utc": _now(), "actor_id": actor_id, "fields": list(body.keys())}
    # $set + $push to an audit array in one atomic op — not expressible via
    # BaseRepository's generic methods, so we drop to the raw collection
    # and broadcast ourselves, mirroring update_one's pattern.
    result = repo._col.find_one_and_update(
        {"id": request_id},
        {"$set": {**body, "last_updated_utc": _now()}, "$push": {"audit": audit_entry}},
        return_document=True,
    )
    if result:
        repo._broadcast("updated", result["_id"], result)
    return _strip(result)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

@router.post("/incidents/{incident_id}/logistics/resource-requests/{request_id}/status")
def change_status(incident_id: str, request_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    doc = _fetch(repo, request_id)
    new_status = str(body.get("status", "")).upper()
    actor_id = body.get("actor_id", "unknown")
    note = body.get("note")
    current = doc.get("status", "DRAFT")
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise HTTPException(400, f"Cannot transition from {current} to {new_status}")
    now = _now()
    updates = {"status": new_status, "last_updated_utc": now}
    if current != "DRAFT":
        updates["version"] = doc.get("version", 1) + 1
    audit_entry = {"event": "status_change", "old": current, "new": new_status, "actor_id": actor_id, "note": note, "ts_utc": now}
    result = repo._col.find_one_and_update(
        {"id": request_id},
        {"$set": updates, "$push": {"audit": audit_entry}},
        return_document=True,
    )
    if result:
        repo._broadcast("updated", result["_id"], result)
    return _strip(result)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

@router.post("/incidents/{incident_id}/logistics/resource-requests/{request_id}/approvals", status_code=201)
def record_approval(incident_id: str, request_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    doc = _fetch(repo, request_id)
    action = str(body.get("action", "")).upper()
    actor_id = str(body.get("actor_id", "unknown"))
    note = body.get("note")
    approval_id = _new_id()
    now = _now()
    approval = {"id": approval_id, "action": action, "actor_id": actor_id, "note": note, "ts_utc": now}
    updates: dict = {}
    target_status = ACTION_STATUS_MAP.get(action)
    if target_status:
        current = doc.get("status", "DRAFT")
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
        if target_status in allowed:
            updates["status"] = target_status
            if current != "DRAFT":
                updates["version"] = doc.get("version", 1) + 1
    updates["last_updated_utc"] = now
    audit_entry = {"event": f"approval:{action}", "ts_utc": now, "actor_id": actor_id}
    repo._col.update_one(
        {"id": request_id},
        {"$push": {"approvals": approval, "audit": audit_entry}, "$set": updates},
    )
    updated = repo._col.find_one({"id": request_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return {"id": approval_id}


# ---------------------------------------------------------------------------
# Fulfillments
# ---------------------------------------------------------------------------

@router.post("/incidents/{incident_id}/logistics/resource-requests/{request_id}/fulfillments", status_code=201)
def assign_fulfillment(incident_id: str, request_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    _fetch(repo, request_id)
    now = _now()
    fulfillment_id = _new_id()
    has_assignment = any(body.get(k) for k in ("supplier_id", "team_id", "vehicle_id"))
    fulfillment = {
        "id": fulfillment_id,
        "request_id": request_id,
        "supplier_id": body.get("supplier_id"),
        "assigned_team_id": body.get("team_id"),
        "assigned_vehicle_id": body.get("vehicle_id"),
        "eta_utc": body.get("eta_utc"),
        "status": "ASSIGNED" if has_assignment else "SOURCING",
        "note": body.get("note"),
        "ts_utc": now,
    }
    repo._col.update_one(
        {"id": request_id},
        {"$push": {"fulfillments": fulfillment}, "$set": {"last_updated_utc": now}},
    )
    updated = repo._col.find_one({"id": request_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return {"id": fulfillment_id}


@router.patch("/incidents/{incident_id}/logistics/resource-requests/{request_id}/fulfillments/{fulfillment_id}")
def update_fulfillment(incident_id: str, request_id: str, fulfillment_id: str, body: dict[str, Any]) -> dict:
    repo = _repo(incident_id)
    doc = _fetch(repo, request_id)
    fulfillments = doc.get("fulfillments") or []
    match = next((f for f in fulfillments if f.get("id") == fulfillment_id), None)
    if not match:
        raise HTTPException(404, "Fulfillment not found")
    now = _now()
    update: dict = {
        "fulfillments.$.status": str(body.get("status", match.get("status", ""))).upper(),
        "fulfillments.$.ts_utc": now,
        "last_updated_utc": now,
    }
    if "note" in body:
        update["fulfillments.$.note"] = body["note"]
    if "eta_utc" in body:
        update["fulfillments.$.eta_utc"] = body["eta_utc"]
    repo._col.update_one(
        {"id": request_id, "fulfillments.id": fulfillment_id},
        {"$set": update},
    )
    updated = repo._col.find_one({"id": request_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.post("/incidents/{incident_id}/logistics/resource-requests/{request_id}/items", status_code=201)
def add_items(incident_id: str, request_id: str, body: list[dict[str, Any]]) -> dict:
    repo = _repo(incident_id)
    _fetch(repo, request_id)
    items = [{"id": item.get("id") or _new_id(), **item} for item in body]
    repo._col.update_one({"id": request_id}, {"$push": {"items": {"$each": items}}})
    updated = repo._col.find_one({"id": request_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return {"ids": [item["id"] for item in items]}


@router.put("/incidents/{incident_id}/logistics/resource-requests/{request_id}/items")
def replace_items(incident_id: str, request_id: str, body: list[dict[str, Any]]) -> dict:
    repo = _repo(incident_id)
    _fetch(repo, request_id)
    items = [{"id": item.get("id") or _new_id(), **item} for item in body]
    repo._col.update_one({"id": request_id}, {"$set": {"items": items, "last_updated_utc": _now()}})
    updated = repo._col.find_one({"id": request_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return {"ids": [item["id"] for item in items]}
