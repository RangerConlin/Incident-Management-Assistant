"""Planned Event Toolkit router (MongoDB-backed)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()

_TOOLS = {
    "promotions": {
        "collection": IncidentCollections.PLANNED_CAMPAIGNS,
        "id_field": "campaign_id",
        "prefix": "PLAN-CAMPAIGN",
        "defaults": {"status": "Draft", "audience": "", "channel": "Multi-channel"},
        "sort": "scheduled_at",
    },
    "promotions/schedule": {
        "collection": IncidentCollections.PLANNED_EVENT_SCHEDULES,
        "id_field": "schedule_id",
        "prefix": "PLAN-SCHEDULE",
        "defaults": {"kind": "Milestone"},
        "sort": "starts_at",
    },
    "vendors": {
        "collection": IncidentCollections.PLANNED_VENDORS,
        "id_field": "vendor_id",
        "prefix": "PLAN-VENDOR",
        "defaults": {"status": "Pending", "contact": "", "location": ""},
        "sort": "name",
    },
    "permits": {
        "collection": IncidentCollections.PLANNED_PERMITS,
        "id_field": "permit_id",
        "prefix": "PLAN-PERMIT",
        "defaults": {"status": "Pending", "issuer": "", "expires_on": ""},
        "sort": "expires_on",
    },
    "safety-reports": {
        "collection": IncidentCollections.PLANNED_SAFETY_REPORTS,
        "id_field": "report_id",
        "prefix": "PLAN-SAFETY",
        "defaults": {"status": "Open", "category": "General", "location": ""},
        "sort": "reported_at",
    },
    "tasks": {
        "collection": IncidentCollections.PLANNED_TASKS,
        "id_field": "task_id",
        "prefix": "PLAN-TASK",
        "defaults": {"status": "Planned", "priority": "Medium", "assigned_to": ""},
        "sort": "due_at",
    },
    "health-inspections": {
        "collection": IncidentCollections.PLANNED_HEALTH_INSPECTIONS,
        "id_field": "inspection_id",
        "prefix": "PLAN-HEALTH",
        "defaults": {"status": "Scheduled", "target": "", "result": ""},
        "sort": "scheduled_at",
    },
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _tool_config(tool: str) -> dict[str, Any]:
    config = _TOOLS.get(tool)
    if not config:
        raise HTTPException(status_code=404, detail="Planned toolkit tool not found")
    return config


def _next_compound_id(col, incident_id: str, config: dict[str, Any]) -> str:
    marker = f"{incident_id}-{config['prefix']}-"
    max_id = 0
    for doc in col.find({"incident_id": incident_id}, {config["id_field"]: 1}):
        raw = doc.get(config["id_field"], "")
        if isinstance(raw, str) and raw.startswith(marker):
            try:
                max_id = max(max_id, int(raw[len(marker):]))
            except ValueError:
                pass
    return f"{marker}{max_id + 1}"


def _public_id(compound_id: object) -> int | None:
    try:
        return int(str(compound_id).rsplit("-", 1)[-1])
    except (TypeError, ValueError):
        return None


def _map_doc(doc: Dict[str, Any], config: dict[str, Any]) -> Dict[str, Any]:
    id_field = config["id_field"]
    is_schedule = id_field == "schedule_id"
    return {
        "id": _public_id(doc.get(id_field)),
        "record_id": doc.get(id_field, ""),
        "incident_id": doc.get("incident_id", ""),
        "tool": doc.get("tool", ""),
        "title": doc.get("name", doc.get("title", "")) if is_schedule else doc.get("title", ""),
        "summary": doc.get("notes", doc.get("summary", "")) if is_schedule else doc.get("summary", ""),
        "status": doc.get("status", ""),
        "priority": doc.get("priority", ""),
        "assigned_to": doc.get("assigned_to", ""),
        "location": doc.get("location", ""),
        "scheduled_at": doc.get("starts_at", doc.get("scheduled_at", "")) if is_schedule else doc.get("scheduled_at", ""),
        "due_at": doc.get("ends_at", doc.get("due_at", "")) if is_schedule else doc.get("due_at", ""),
        "starts_at": doc.get("starts_at", ""),
        "ends_at": doc.get("ends_at", ""),
        "kind": doc.get("kind", ""),
        "audience": doc.get("audience", ""),
        "channel": doc.get("channel", ""),
        "metadata": doc.get("metadata") or {},
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


class PlannedRecordCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    location: Optional[str] = None
    scheduled_at: Optional[str] = None
    due_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduleItemCreate(BaseModel):
    name: str = Field(min_length=1)
    kind: str = "Milestone"
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    notes: Optional[str] = None


@router.get("/incidents/{incident_id}/planned/{tool}")
def list_records(incident_id: str, tool: str, status: Optional[str] = None, search: Optional[str] = None):
    config = _tool_config(tool)
    col = get_incident_db(incident_id)[config["collection"]]
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
            {"location": {"$regex": search, "$options": "i"}},
        ]
    docs = list(col.find(query, {"_id": 0}).sort(config["sort"], 1))
    return [_map_doc(doc, config) for doc in docs]


@router.post("/incidents/{incident_id}/planned/{tool}", status_code=201)
def create_record(incident_id: str, tool: str, body: PlannedRecordCreate):
    config = _tool_config(tool)
    col = get_incident_db(incident_id)[config["collection"]]
    record_id = _next_compound_id(col, incident_id, config)
    now = _utcnow()
    doc: Dict[str, Any] = {
        "_id": _new_id(),
        config["id_field"]: record_id,
        "incident_id": incident_id,
        "tool": tool,
        "title": body.title,
        "summary": body.summary or "",
        "status": body.status or config["defaults"].get("status", ""),
        "priority": body.priority or config["defaults"].get("priority", ""),
        "assigned_to": body.assigned_to or config["defaults"].get("assigned_to", ""),
        "location": body.location or config["defaults"].get("location", ""),
        "scheduled_at": body.scheduled_at or "",
        "due_at": body.due_at or "",
        "metadata": dict(config["defaults"]) | dict(body.metadata or {}),
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    saved = col.find_one({config["id_field"]: record_id}, {"_id": 0})
    return _map_doc(saved, config)


@router.get("/incidents/{incident_id}/planned/promotions/schedule")
def list_schedule(incident_id: str):
    config = _tool_config("promotions/schedule")
    col = get_incident_db(incident_id)[config["collection"]]
    docs = list(col.find({"incident_id": incident_id, "deleted": {"$ne": True}}, {"_id": 0}).sort(config["sort"], 1))
    return [_map_doc(doc, config) for doc in docs]


@router.post("/incidents/{incident_id}/planned/promotions/schedule", status_code=201)
def create_schedule(incident_id: str, body: ScheduleItemCreate):
    config = _tool_config("promotions/schedule")
    col = get_incident_db(incident_id)[config["collection"]]
    record_id = _next_compound_id(col, incident_id, config)
    now = _utcnow()
    doc: Dict[str, Any] = {
        "_id": _new_id(),
        config["id_field"]: record_id,
        "incident_id": incident_id,
        "tool": "promotions/schedule",
        "name": body.name,
        "kind": body.kind or "Milestone",
        "starts_at": body.starts_at or "",
        "ends_at": body.ends_at or "",
        "notes": body.notes or "",
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    saved = col.find_one({config["id_field"]: record_id}, {"_id": 0})
    return _map_doc(saved, config)


@router.patch("/incidents/{incident_id}/planned/promotions/schedule/{record_id}")
def update_schedule(incident_id: str, record_id: int, patch: Dict[str, Any] = Body(...)):
    config = _tool_config("promotions/schedule")
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    allowed = {"name", "kind", "starts_at", "ends_at", "notes"}
    updates = {key: value for key, value in patch.items() if key in allowed}
    updates["updated_at"] = _utcnow()
    doc = col.find_one_and_update(
        {config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    return _map_doc(doc, config)


@router.delete("/incidents/{incident_id}/planned/promotions/schedule/{record_id}", status_code=204)
def delete_schedule(incident_id: str, record_id: int):
    config = _tool_config("promotions/schedule")
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    result = col.update_one(
        {config["id_field"]: compound_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "updated_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Schedule item not found")


@router.patch("/incidents/{incident_id}/planned/{tool}/{record_id}")
def update_record(incident_id: str, tool: str, record_id: int, patch: Dict[str, Any] = Body(...)):
    config = _tool_config(tool)
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    allowed = {
        "title",
        "summary",
        "status",
        "priority",
        "assigned_to",
        "location",
        "scheduled_at",
        "due_at",
        "metadata",
    }
    updates = {key: value for key, value in patch.items() if key in allowed}
    updates["updated_at"] = _utcnow()
    doc = col.find_one_and_update(
        {config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Planned toolkit record not found")
    return _map_doc(doc, config)


@router.delete("/incidents/{incident_id}/planned/{tool}/{record_id}", status_code=204)
def delete_record(incident_id: str, tool: str, record_id: int):
    config = _tool_config(tool)
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    result = col.update_one(
        {config["id_field"]: compound_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "updated_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Planned toolkit record not found")
