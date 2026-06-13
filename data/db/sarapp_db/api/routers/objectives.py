"""Incident objectives API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import get_incident_db_name
from sarapp_db.mongo.collection_names import IncidentCollections

router = APIRouter()


def _col(incident_id: str):
    client = get_client()
    return client[get_incident_db_name(incident_id)][IncidentCollections.INCIDENT_OBJECTIVES]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw MongoDB document, handling seeded vs. new-schema fields."""
    d = dict(doc)
    # Seeded docs used 'description'; new docs use 'text'
    if not d.get("text"):
        d["text"] = d.get("description") or ""
    # Seeded docs used 'objective_id' as the human-readable code
    if not d.get("code"):
        d["code"] = d.get("objective_id") or d["_id"]
    d.setdefault("display_order", 0)
    d.setdefault("tags", d.get("tags_json") or [])
    d.setdefault("narrative", None)
    d.setdefault("strategies", [])
    d.setdefault("open_tasks", 0)
    d.setdefault("total_tasks", 0)
    return d


# ------------------------------------------------------------------
# List

@router.get("")
def list_objectives(
    incident_id: str,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    section: str | None = Query(None),
    op_period_id: str | None = Query(None),
    search: str | None = Query(None),
) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = [{"incident_id": incident_id, "deleted": False}]

    if status and status not in ("", "All"):
        conditions.append({"status": {"$regex": f"^{status}$", "$options": "i"}})
    if priority and priority not in ("", "All"):
        conditions.append({"priority": {"$regex": f"^{priority}$", "$options": "i"}})
    if section and section not in ("", "All"):
        conditions.append({"$or": [
            {"assigned_section": {"$regex": f"^{section}$", "$options": "i"}},
            {"owner_section": {"$regex": f"^{section}$", "$options": "i"}},
        ]})
    if op_period_id:
        conditions.append({"op_period_id": op_period_id})
    if search:
        token = search.strip()
        conditions.append({"$or": [
            {"text": {"$regex": token, "$options": "i"}},
            {"description": {"$regex": token, "$options": "i"}},
            {"objective_id": {"$regex": token, "$options": "i"}},
        ]})

    query = {"$and": conditions} if len(conditions) > 1 else conditions[0]
    docs = list(_col(incident_id).find(query).sort([("display_order", 1), ("created_at", 1)]))
    return [_normalize(d) for d in docs]


# ------------------------------------------------------------------
# Create

class CreateObjectiveRequest(BaseModel):
    incident_id: str
    text: str
    priority: str = "normal"
    status: str = "draft"
    owner_section: str | None = None
    op_period_id: str | None = None
    due_time: str | None = None
    tags: list[str] = []
    display_order: int | None = None
    created_by: str | None = None


@router.post("", status_code=201)
def create_objective(body: CreateObjectiveRequest) -> dict[str, Any]:
    col = _col(body.incident_id)
    count = col.count_documents({"incident_id": body.incident_id, "deleted": False})
    code = f"OBJ-{count + 1}"
    display_order = body.display_order if body.display_order is not None else count
    now = _utcnow()
    doc: dict[str, Any] = {
        "_id": _new_id(),
        "incident_id": body.incident_id,
        "code": code,
        "text": body.text,
        "priority": body.priority,
        "status": body.status,
        "owner_section": body.owner_section,
        "op_period_id": body.op_period_id,
        "due_time": body.due_time,
        "tags": body.tags,
        "display_order": display_order,
        "narrative": None,
        "created_by": body.created_by,
        "updated_by": body.created_by,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    return _normalize(doc)


# ------------------------------------------------------------------
# Reorder — must be defined before /{objective_id} to avoid path conflicts

class ReorderRequest(BaseModel):
    ids: list[str]


@router.post("/reorder")
def reorder_objectives(incident_id: str, body: ReorderRequest) -> dict[str, Any]:
    col = _col(incident_id)
    now = _utcnow()
    for position, obj_id in enumerate(body.ids):
        col.update_one(
            {"_id": obj_id, "incident_id": incident_id},
            {"$set": {"display_order": position, "updated_at": now}},
        )
    return {"ok": True}


# ------------------------------------------------------------------
# Get one

@router.get("/{objective_id}")
def get_objective(objective_id: str, incident_id: str) -> dict[str, Any]:
    doc = _col(incident_id).find_one({"_id": objective_id, "deleted": False})
    if doc is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    return _normalize(doc)


# ------------------------------------------------------------------
# Update

class UpdateObjectiveRequest(BaseModel):
    text: str | None = None
    priority: str | None = None
    status: str | None = None
    owner_section: str | None = None
    tags: list[str] | None = None
    op_period_id: str | None = None
    narrative: str | None = None
    updated_by: str | None = None


@router.patch("/{objective_id}")
def update_objective(
    objective_id: str,
    incident_id: str,
    body: UpdateObjectiveRequest,
) -> dict[str, Any]:
    updates: dict[str, Any] = {"updated_at": _utcnow()}
    for field in ("text", "priority", "status", "owner_section", "tags", "op_period_id", "narrative", "updated_by"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
    col = _col(incident_id)
    result = col.update_one({"_id": objective_id, "deleted": False}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Objective not found")
    doc = col.find_one({"_id": objective_id})
    return _normalize(doc) if doc else {}


# ------------------------------------------------------------------
# Soft delete

@router.delete("/{objective_id}", status_code=204)
def delete_objective(objective_id: str, incident_id: str) -> None:
    _col(incident_id).update_one(
        {"_id": objective_id},
        {"$set": {"deleted": True, "updated_at": _utcnow()}},
    )
