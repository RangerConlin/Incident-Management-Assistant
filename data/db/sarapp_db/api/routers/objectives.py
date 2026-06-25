"""Incident objectives API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import get_incident_db_name
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class ObjectivesRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_OBJECTIVES


def _incident_db(incident_id: str):
    return get_client()[get_incident_db_name(incident_id)]


def _objectives_repo(incident_id: str) -> ObjectivesRepository:
    return ObjectivesRepository(_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_audit(
    repo: ObjectivesRepository,
    objective_id: str,
    action: str,
    field: str | None = None,
    old: Any = None,
    new: Any = None,
    user_id: str | None = None,
) -> None:
    entry = {
        "ts": _utcnow(),
        "action": action,
        "field": field,
        "old_value": old,
        "new_value": new,
        "user_id": user_id,
    }
    repo._col.update_one({"_id": objective_id}, {"$push": {"audit": entry}})


def _next_link_id(links: list[dict[str, Any]]) -> int:
    if not links:
        return 1
    return max((l.get("id", 0) for l in links), default=0) + 1


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
    d.setdefault("task_links", [])
    d.setdefault("audit", [])
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
    docs = _objectives_repo(incident_id).find_many(
        query, sort=[("display_order", 1), ("created_at", 1)], include_deleted=True,
    )
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
    repo = _objectives_repo(body.incident_id)
    count = repo.count({"incident_id": body.incident_id})
    code = f"OBJ-{count + 1}"
    display_order = body.display_order if body.display_order is not None else count
    doc: dict[str, Any] = {
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
    }
    doc = repo.insert_one(doc)
    _append_audit(repo, doc["_id"], "create", new=body.text, user_id=body.created_by)
    return _normalize(doc)


# ------------------------------------------------------------------
# Reorder — must be defined before /{objective_id} to avoid path conflicts

class ReorderRequest(BaseModel):
    ids: list[str]


@router.post("/reorder")
def reorder_objectives(incident_id: str, body: ReorderRequest) -> dict[str, Any]:
    repo = _objectives_repo(incident_id)
    for position, obj_id in enumerate(body.ids):
        existing = repo.find_by_id(obj_id)
        if existing and existing.get("display_order") == position:
            continue
        repo.update_one(obj_id, {"display_order": position}, extra_filter={"incident_id": incident_id})
        if existing:
            _append_audit(
                repo, obj_id, "reorder",
                field="display_order",
                old=existing.get("display_order"),
                new=position,
            )
    return {"ok": True}


# ------------------------------------------------------------------
# Get one

@router.get("/{objective_id}")
def get_objective(objective_id: str, incident_id: str) -> dict[str, Any]:
    doc = _objectives_repo(incident_id).find_by_id(objective_id)
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
    repo = _objectives_repo(incident_id)
    existing = repo.find_by_id(objective_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Objective not found")
    updates: dict[str, Any] = {}
    for field in ("text", "priority", "status", "owner_section", "tags", "op_period_id", "narrative", "updated_by"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
    repo.update_one(objective_id, updates)
    for field, new_val in updates.items():
        if field == "updated_by":
            continue
        old_val = existing.get(field)
        if old_val != new_val:
            _append_audit(repo, objective_id, "update", field=field, old=old_val, new=new_val, user_id=body.updated_by)
    doc = repo.find_by_id(objective_id)
    return _normalize(doc) if doc else {}


# ------------------------------------------------------------------
# Task links — tasks tied directly to this objective (embedded on the doc,
# mirrors the work_assignments.task_links pattern).

class LinkTaskRequest(BaseModel):
    task_id: int
    link_type: str = "Linked Existing"
    created_by: str | None = None


@router.get("/{objective_id}/tasks")
def list_task_links(objective_id: str, incident_id: str) -> list[dict[str, Any]]:
    doc = _objectives_repo(incident_id).find_by_id(objective_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    return doc.get("task_links") or []


@router.post("/{objective_id}/tasks", status_code=201)
def link_task(
    objective_id: str,
    incident_id: str,
    body: LinkTaskRequest,
) -> dict[str, Any]:
    repo = _objectives_repo(incident_id)
    doc = repo.find_by_id(objective_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    existing = [t for t in doc.get("task_links", []) if t.get("task_id") == body.task_id]
    if existing:
        return existing[0]
    link = {
        "id": _next_link_id(doc.get("task_links", [])),
        "task_id": body.task_id,
        "link_type": body.link_type,
        "created_at": _utcnow(),
        "created_by": body.created_by,
    }
    repo._col.update_one({"_id": objective_id}, {"$push": {"task_links": link}, "$set": {"updated_at": _utcnow()}})
    _append_audit(repo, objective_id, "task.link", new=f"task_id={body.task_id}", user_id=body.created_by)
    return link


@router.delete("/{objective_id}/tasks/{link_id}", status_code=204)
def unlink_task(objective_id: str, link_id: int, incident_id: str) -> None:
    repo = _objectives_repo(incident_id)
    doc = repo.find_by_id(objective_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    links = doc.get("task_links", [])
    target = next((l for l in links if l.get("id") == link_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Task link not found")
    repo._col.update_one({"_id": objective_id}, {"$pull": {"task_links": {"id": link_id}}})
    _append_audit(repo, objective_id, "task.unlink", old=f"task_id={target.get('task_id')}")


# ------------------------------------------------------------------
# Audit log

@router.get("/{objective_id}/audit")
def list_audit(objective_id: str, incident_id: str) -> list[dict[str, Any]]:
    doc = _objectives_repo(incident_id).find_by_id(objective_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    return list(reversed(doc.get("audit") or []))


# ------------------------------------------------------------------
# Soft delete

@router.delete("/{objective_id}", status_code=204)
def delete_objective(objective_id: str, incident_id: str) -> None:
    _objectives_repo(incident_id).soft_delete(objective_id)
