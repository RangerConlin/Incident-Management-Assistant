"""Incident objectives API router."""

from __future__ import annotations

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


class StrategiesRepository(BaseRepository):
    collection_name = IncidentCollections.STRATEGIES
    soft_deletes = False


class StrategyTaskLinksRepository(BaseRepository):
    collection_name = IncidentCollections.OBJECTIVE_STRATEGIES_TASK_LINKS
    soft_deletes = False


def _incident_db(incident_id: str):
    return get_client()[get_incident_db_name(incident_id)]


def _objectives_repo(incident_id: str) -> ObjectivesRepository:
    return ObjectivesRepository(_incident_db(incident_id))


def _strategies_repo(incident_id: str) -> StrategiesRepository:
    return StrategiesRepository(_incident_db(incident_id))


def _task_links_repo(incident_id: str) -> StrategyTaskLinksRepository:
    return StrategyTaskLinksRepository(_incident_db(incident_id))


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
    return _normalize(doc)


# ------------------------------------------------------------------
# Reorder — must be defined before /{objective_id} to avoid path conflicts

class ReorderRequest(BaseModel):
    ids: list[str]


@router.post("/reorder")
def reorder_objectives(incident_id: str, body: ReorderRequest) -> dict[str, Any]:
    repo = _objectives_repo(incident_id)
    for position, obj_id in enumerate(body.ids):
        repo.update_one(obj_id, {"display_order": position}, extra_filter={"incident_id": incident_id})
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
    updates: dict[str, Any] = {}
    for field in ("text", "priority", "status", "owner_section", "tags", "op_period_id", "narrative", "updated_by"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
    repo = _objectives_repo(incident_id)
    matched = repo.update_one(objective_id, updates)
    if not matched:
        raise HTTPException(status_code=404, detail="Objective not found")
    doc = repo.find_by_id(objective_id)
    return _normalize(doc) if doc else {}


# ------------------------------------------------------------------
# Strategies

class CreateStrategyRequest(BaseModel):
    objective_id: str
    title: str
    description: str | None = None
    status: str = "planned"
    created_by: str | None = None


@router.post("/{objective_id}/strategies", status_code=201)
def add_strategy(
    objective_id: str,
    incident_id: str,
    body: CreateStrategyRequest,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "incident_id": incident_id,
        "objective_id": objective_id,
        "title": body.title,
        "description": body.description,
        "status": body.status,
        "created_by": body.created_by,
    }
    doc = _strategies_repo(incident_id).insert_one(doc)
    doc.pop("_id", None)
    return doc


class UpdateStrategyRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    updated_by: str | None = None


@router.patch("/{objective_id}/strategies/{strategy_id}")
def update_strategy(
    objective_id: str,
    strategy_id: str,
    incident_id: str,
    body: UpdateStrategyRequest,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field in ("title", "description", "status", "updated_by"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
    repo = _strategies_repo(incident_id)
    matched = repo.update_one(strategy_id, updates, extra_filter={"objective_id": objective_id})
    if not matched:
        raise HTTPException(status_code=404, detail="Strategy not found")
    doc = repo.find_by_id(strategy_id)
    if doc:
        doc.pop("_id", None)
    return doc or {}


@router.delete("/{objective_id}/strategies/{strategy_id}", status_code=204)
def delete_strategy(objective_id: str, strategy_id: str, incident_id: str) -> None:
    deleted = _strategies_repo(incident_id).delete_one(strategy_id, extra_filter={"objective_id": objective_id})
    if not deleted:
        raise HTTPException(status_code=404, detail="Strategy not found")
    # Also delete any task links for this strategy
    _task_links_repo(incident_id).delete_many({"strategy_id": strategy_id})


# ------------------------------------------------------------------
# Task links

class LinkTaskRequest(BaseModel):
    task_id: int


@router.post("/{objective_id}/strategies/{strategy_id}/tasks", status_code=201)
def link_task(
    objective_id: str,
    strategy_id: str,
    incident_id: str,
    body: LinkTaskRequest,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "incident_id": incident_id,
        "objective_id": objective_id,
        "strategy_id": strategy_id,
        "task_id": body.task_id,
    }
    doc = _task_links_repo(incident_id).insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/{objective_id}/strategies/{strategy_id}/tasks/{task_id}", status_code=204)
def unlink_task(
    objective_id: str,
    strategy_id: str,
    task_id: int,
    incident_id: str,
) -> None:
    deleted = _task_links_repo(incident_id).delete_many({
        "objective_id": objective_id,
        "strategy_id": strategy_id,
        "task_id": task_id,
    })
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Task link not found")


# ------------------------------------------------------------------
# Soft delete

@router.delete("/{objective_id}", status_code=204)
def delete_objective(objective_id: str, incident_id: str) -> None:
    _objectives_repo(incident_id).soft_delete(objective_id)
