"""Initial Response router (MongoDB-backed).

Manages hasty search tasks and reflex action records for an incident's
initial response phase.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _ensure_int_ids(col) -> None:
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _next_int_id(col) -> int:
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


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
    col = get_incident_db(incident_id)[IncidentCollections.INITIAL_HASTY_TASKS]
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("created_at", -1))
    return [_map_hasty(d) for d in docs]


@router.post("/incidents/{incident_id}/initialresponse/hasty", status_code=201)
def create_hasty_task(incident_id: str, data: HastyTaskCreate):
    col = get_incident_db(incident_id)[IncidentCollections.INITIAL_HASTY_TASKS]
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    now = _utcnow()
    doc = {
        "_id": _new_id(),
        "int_id": int_id,
        "incident_id": incident_id,
        "area": data.area,
        "priority": data.priority,
        "notes": data.notes,
        "operations_task_id": data.operations_task_id,
        "logistics_request_id": data.logistics_request_id,
        "created_at": now,
    }
    col.insert_one(doc)
    return _map_hasty(col.find_one({"int_id": int_id}))


@router.patch("/incidents/{incident_id}/initialresponse/hasty/{task_id}")
def update_hasty_task(incident_id: str, task_id: int, data: HastyTaskUpdate):
    col = get_incident_db(incident_id)[IncidentCollections.INITIAL_HASTY_TASKS]
    updates: Dict[str, Any] = {}
    if data.operations_task_id is not None:
        updates["operations_task_id"] = data.operations_task_id
    if data.logistics_request_id is not None:
        updates["logistics_request_id"] = data.logistics_request_id
    if not updates:
        doc = col.find_one({"int_id": task_id, "incident_id": incident_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Hasty task not found")
        return _map_hasty(doc)
    result = col.find_one_and_update(
        {"int_id": task_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Hasty task not found")
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
    col = get_incident_db(incident_id)[IncidentCollections.INITIAL_REFLEX_ACTIONS]
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("created_at", -1))
    return [_map_reflex(d) for d in docs]


@router.post("/incidents/{incident_id}/initialresponse/reflex", status_code=201)
def create_reflex_action(incident_id: str, data: ReflexActionCreate):
    col = get_incident_db(incident_id)[IncidentCollections.INITIAL_REFLEX_ACTIONS]
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    now = _utcnow()
    doc = {
        "_id": _new_id(),
        "int_id": int_id,
        "incident_id": incident_id,
        "trigger": data.trigger,
        "action": data.action,
        "communications_alert_id": data.communications_alert_id,
        "created_at": now,
    }
    col.insert_one(doc)
    return _map_reflex(col.find_one({"int_id": int_id}))


@router.patch("/incidents/{incident_id}/initialresponse/reflex/{action_id}/notification")
def update_reflex_notification(incident_id: str, action_id: int, data: ReflexNotificationUpdate):
    col = get_incident_db(incident_id)[IncidentCollections.INITIAL_REFLEX_ACTIONS]
    result = col.find_one_and_update(
        {"int_id": action_id, "incident_id": incident_id},
        {"$set": {"communications_alert_id": data.communications_alert_id}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Reflex action not found")
    return _map_reflex(result)
