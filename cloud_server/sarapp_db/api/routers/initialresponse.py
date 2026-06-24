"""Initial Response router (MongoDB-backed).

Manages hasty search tasks and reflex action records for an incident's
initial response phase.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class InitialResponseOverviewRepository(BaseRepository):
    collection_name = IncidentCollections.INITIAL_RESPONSE_OVERVIEW
    soft_deletes = False


class InitialHastyTasksRepository(BaseRepository):
    collection_name = IncidentCollections.INITIAL_HASTY_TASKS
    soft_deletes = False


class InitialReflexActionsRepository(BaseRepository):
    collection_name = IncidentCollections.INITIAL_REFLEX_ACTIONS
    soft_deletes = False


def _overview_repo(incident_id: str) -> InitialResponseOverviewRepository:
    return InitialResponseOverviewRepository(get_incident_db(incident_id))


def _hasty_repo(incident_id: str) -> InitialHastyTasksRepository:
    return InitialHastyTasksRepository(get_incident_db(incident_id))


def _reflex_repo(incident_id: str) -> InitialReflexActionsRepository:
    return InitialReflexActionsRepository(get_incident_db(incident_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_int_ids(repo: BaseRepository) -> None:
    col = repo._col
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _next_int_id(repo: BaseRepository) -> int:
    top = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


def _default_overview(incident_id: str) -> Dict[str, Any]:
    return {
        "incident_id": incident_id,
        "incident_mode": "Missing Person",
        "behavior_category": "",
        "source_info": {},
        "subject_info": {},
        "aircraft_info": {},
        "timeline_info": {},
        "primary_anchor": {},
        "related_locations": [],
        "clues_environment": {},
        "operations_summary": {},
        "narrative": "",
        "updated_at": "",
    }


class InitialOverviewPayload(BaseModel):
    incident_mode: str = "Missing Person"
    behavior_category: str = ""
    source_info: Dict[str, Any] = Field(default_factory=dict)
    subject_info: Dict[str, Any] = Field(default_factory=dict)
    aircraft_info: Dict[str, Any] = Field(default_factory=dict)
    timeline_info: Dict[str, Any] = Field(default_factory=dict)
    primary_anchor: Dict[str, Any] = Field(default_factory=dict)
    related_locations: List[Dict[str, Any]] = Field(default_factory=list)
    clues_environment: Dict[str, Any] = Field(default_factory=dict)
    operations_summary: Dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""


@router.get("/incidents/{incident_id}/initialresponse/overview")
def get_initial_overview(incident_id: str):
    repo = _overview_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id})
    if not doc:
        return _default_overview(incident_id)
    doc.pop("_id", None)
    payload = _default_overview(incident_id)
    payload.update(doc)
    return payload


@router.put("/incidents/{incident_id}/initialresponse/overview")
def save_initial_overview(incident_id: str, data: InitialOverviewPayload):
    repo = _overview_repo(incident_id)
    payload = data.model_dump()
    payload["incident_id"] = incident_id
    existing = repo.find_one({"incident_id": incident_id})
    if existing:
        repo.update_one(existing["_id"], payload)
        saved = repo.find_by_id(existing["_id"])
    else:
        saved = repo.insert_one(payload)
    if saved:
        saved.pop("_id", None)
    return saved or _default_overview(incident_id)


# ---------------------------------------------------------------------------
# Hasty Tasks
# ---------------------------------------------------------------------------

def _map_hasty(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "incident_id": doc.get("incident_id", ""),
        "area": doc.get("area", ""),
        "priority": doc.get("priority"),
        "notes": doc.get("notes"),
        "operations_task_id": doc.get("operations_task_id"),
        "logistics_request_id": doc.get("logistics_request_id"),
        "created_at": doc.get("created_at", ""),
    }


class HastyTaskCreate(BaseModel):
    incident_id: str
    area: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    operations_task_id: Optional[int] = None
    logistics_request_id: Optional[str] = None


class HastyTaskUpdate(BaseModel):
    operations_task_id: Optional[int] = None
    logistics_request_id: Optional[str] = None


@router.get("/incidents/{incident_id}/initialresponse/hasty")
def list_hasty_tasks(incident_id: str):
    repo = _hasty_repo(incident_id)
    _ensure_int_ids(repo)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("created_at", -1)])
    return [_map_hasty(d) for d in docs]


@router.post("/incidents/{incident_id}/initialresponse/hasty", status_code=201)
def create_hasty_task(incident_id: str, data: HastyTaskCreate):
    repo = _hasty_repo(incident_id)
    _ensure_int_ids(repo)
    int_id = _next_int_id(repo)
    doc = {
        "int_id": int_id,
        "incident_id": incident_id,
        "area": data.area,
        "priority": data.priority,
        "notes": data.notes,
        "operations_task_id": data.operations_task_id,
        "logistics_request_id": data.logistics_request_id,
    }
    repo.insert_one(doc)
    return _map_hasty(repo.find_one({"int_id": int_id}))


@router.patch("/incidents/{incident_id}/initialresponse/hasty/{task_id}")
def update_hasty_task(incident_id: str, task_id: int, data: HastyTaskUpdate):
    repo = _hasty_repo(incident_id)
    updates: Dict[str, Any] = {}
    if data.operations_task_id is not None:
        updates["operations_task_id"] = data.operations_task_id
    if data.logistics_request_id is not None:
        updates["logistics_request_id"] = data.logistics_request_id
    existing = repo.find_one({"int_id": task_id, "incident_id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Hasty task not found")
    if not updates:
        return _map_hasty(existing)
    repo.update_one(existing["_id"], updates)
    result = repo.find_by_id(existing["_id"])
    return _map_hasty(result)


# ---------------------------------------------------------------------------
# Reflex Actions
# ---------------------------------------------------------------------------

def _map_reflex(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "incident_id": doc.get("incident_id", ""),
        "trigger": doc.get("trigger", ""),
        "action": doc.get("action"),
        "communications_alert_id": doc.get("communications_alert_id"),
        "created_at": doc.get("created_at", ""),
    }


class ReflexActionCreate(BaseModel):
    incident_id: str
    trigger: str
    action: Optional[str] = None
    communications_alert_id: Optional[str] = None


class ReflexNotificationUpdate(BaseModel):
    communications_alert_id: str


@router.get("/incidents/{incident_id}/initialresponse/reflex")
def list_reflex_actions(incident_id: str):
    repo = _reflex_repo(incident_id)
    _ensure_int_ids(repo)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("created_at", -1)])
    return [_map_reflex(d) for d in docs]


@router.post("/incidents/{incident_id}/initialresponse/reflex", status_code=201)
def create_reflex_action(incident_id: str, data: ReflexActionCreate):
    repo = _reflex_repo(incident_id)
    _ensure_int_ids(repo)
    int_id = _next_int_id(repo)
    doc = {
        "int_id": int_id,
        "incident_id": incident_id,
        "trigger": data.trigger,
        "action": data.action,
        "communications_alert_id": data.communications_alert_id,
    }
    repo.insert_one(doc)
    return _map_reflex(repo.find_one({"int_id": int_id}))


@router.patch("/incidents/{incident_id}/initialresponse/reflex/{action_id}/notification")
def update_reflex_notification(incident_id: str, action_id: int, data: ReflexNotificationUpdate):
    repo = _reflex_repo(incident_id)
    existing = repo.find_one({"int_id": action_id, "incident_id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Reflex action not found")
    repo.update_one(existing["_id"], {"communications_alert_id": data.communications_alert_id})
    result = repo.find_by_id(existing["_id"])
    return _map_reflex(result)
