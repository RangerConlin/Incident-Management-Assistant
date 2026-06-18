"""Planned Event Toolkit router (MongoDB-backed)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.int_id import next_int_id

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
    "quick-assignments": {
        "collection": IncidentCollections.PLANNED_QUICK_ASSIGNMENTS,
        "id_field": "quick_assignment_id",
        "prefix": "PLAN-QA",
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
        "assigned_team_id": doc.get("assigned_team_id", ""),
        "assigned_person_id": doc.get("assigned_person_id", ""),
        "location": doc.get("location", ""),
        "zone": doc.get("zone", ""),
        "scheduled_at": doc.get("starts_at", doc.get("scheduled_at", "")) if is_schedule else doc.get("scheduled_at", ""),
        "due_at": doc.get("ends_at", doc.get("due_at", "")) if is_schedule else doc.get("due_at", ""),
        "starts_at": doc.get("starts_at", ""),
        "ends_at": doc.get("ends_at", ""),
        "kind": doc.get("kind", ""),
        "owner": doc.get("owner", ""),
        "tags": doc.get("tags", []),
        "recurring": doc.get("recurring", False),
        "recurrence_rule": doc.get("recurrence_rule", ""),
        "recurrence_start_at": doc.get("recurrence_start_at", ""),
        "recurrence_end_at": doc.get("recurrence_end_at", ""),
        "missed_occurrence_behavior": doc.get("missed_occurrence_behavior", ""),
        "template_id": doc.get("template_id", ""),
        "generated_from_template_id": doc.get("generated_from_template_id", ""),
        "lifecycle_state": doc.get("lifecycle_state", ""),
        "active_at": doc.get("active_at", ""),
        "triggered_at": doc.get("triggered_at", ""),
        "source_type": doc.get("source_type", ""),
        "source_id": doc.get("source_id", ""),
        "source_label": doc.get("source_label", ""),
        "source_tool": doc.get("source_tool", ""),
        "linked_tasking_id": doc.get("linked_tasking_id", ""),
        "promoted_at": doc.get("promoted_at", ""),
        "promoted_by": doc.get("promoted_by", ""),
        "promoted_read_only": doc.get("promoted_read_only", False),
        "audience": doc.get("audience", ""),
        "channel": doc.get("channel", ""),
        "metadata": doc.get("metadata") or {},
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


class PlannedRecordCreate(BaseModel):
    title: str = ""
    summary: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team_id: Optional[str] = None
    assigned_person_id: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    scheduled_at: Optional[str] = None
    due_at: Optional[str] = None
    recurring: bool = False
    recurrence_rule: Optional[str] = None
    recurrence_start_at: Optional[str] = None
    recurrence_end_at: Optional[str] = None
    missed_occurrence_behavior: Optional[str] = None
    template_id: Optional[str] = None
    generated_from_template_id: Optional[str] = None
    lifecycle_state: Optional[str] = None
    active_at: Optional[str] = None
    triggered_at: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_label: Optional[str] = None
    source_tool: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduleItemCreate(BaseModel):
    name: str = ""
    kind: str = "Milestone"
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    notes: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ScheduleTriggerCreate(BaseModel):
    schedule_item_id: Optional[str] = None
    trigger_type: str = "notification"
    label: str = ""
    offset_minutes: Optional[int] = None
    trigger_at: Optional[str] = None
    relative_to: str = "start"
    enabled: bool = True
    audience_role: Optional[str] = None
    audience_user_id: Optional[str] = None
    notification_channel: Optional[str] = None
    requires_acknowledgement: bool = False
    message_template: Optional[str] = None
    link_to_schedule_item: bool = True
    quick_assignment_template_id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team_id: Optional[str] = None
    assigned_person_id: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    priority: Optional[str] = None
    recurring: bool = False
    recurrence_rule: Optional[str] = None
    missed_occurrence_behavior: Optional[str] = None


class NotificationCreate(BaseModel):
    title: str = ""
    message: str = ""
    severity: str = ""
    audience_role: Optional[str] = None
    audience_user_id: Optional[str] = None
    notification_channel: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    scheduled_at: Optional[str] = None
    triggered_at: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_label: Optional[str] = None


class PromotionRequest(BaseModel):
    promoted_by: str = ""


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = ""


def _schedule_trigger_config() -> dict[str, Any]:
    return {
        "collection": IncidentCollections.PLANNED_SCHEDULE_TRIGGERS,
        "id_field": "trigger_id",
        "prefix": "PLAN-TRIGGER",
        "sort": "trigger_at",
    }


def _notification_config() -> dict[str, Any]:
    return {
        "collection": IncidentCollections.PLANNED_NOTIFICATIONS,
        "id_field": "notification_id",
        "prefix": "PLAN-NOTIFY",
        "sort": "scheduled_at",
    }


def _map_schedule_trigger(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": _public_id(doc.get("trigger_id")),
        "trigger_id": doc.get("trigger_id", ""),
        "incident_id": doc.get("incident_id", ""),
        "schedule_item_id": doc.get("schedule_item_id", ""),
        "trigger_type": doc.get("trigger_type", "notification"),
        "label": doc.get("label", ""),
        "offset_minutes": doc.get("offset_minutes"),
        "trigger_at": doc.get("trigger_at", ""),
        "relative_to": doc.get("relative_to", "start"),
        "enabled": doc.get("enabled", True),
        "audience_role": doc.get("audience_role", ""),
        "audience_user_id": doc.get("audience_user_id", ""),
        "notification_channel": doc.get("notification_channel", ""),
        "requires_acknowledgement": doc.get("requires_acknowledgement", False),
        "message_template": doc.get("message_template", ""),
        "link_to_schedule_item": doc.get("link_to_schedule_item", True),
        "quick_assignment_template_id": doc.get("quick_assignment_template_id", ""),
        "title": doc.get("title", ""),
        "summary": doc.get("summary", ""),
        "assigned_to": doc.get("assigned_to", ""),
        "assigned_team_id": doc.get("assigned_team_id", ""),
        "assigned_person_id": doc.get("assigned_person_id", ""),
        "location": doc.get("location", ""),
        "zone": doc.get("zone", ""),
        "priority": doc.get("priority", ""),
        "recurring": doc.get("recurring", False),
        "recurrence_rule": doc.get("recurrence_rule", ""),
        "missed_occurrence_behavior": doc.get("missed_occurrence_behavior", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


def _map_notification(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": _public_id(doc.get("notification_id")),
        "notification_id": doc.get("notification_id", ""),
        "incident_id": doc.get("incident_id", ""),
        "title": doc.get("title", ""),
        "message": doc.get("message", ""),
        "severity": doc.get("severity", ""),
        "audience_role": doc.get("audience_role", ""),
        "audience_user_id": doc.get("audience_user_id", ""),
        "notification_channel": doc.get("notification_channel", ""),
        "location": doc.get("location", ""),
        "zone": doc.get("zone", ""),
        "scheduled_at": doc.get("scheduled_at", ""),
        "triggered_at": doc.get("triggered_at", ""),
        "acknowledged_at": doc.get("acknowledged_at", ""),
        "acknowledged_by": doc.get("acknowledged_by", ""),
        "dismissed_at": doc.get("dismissed_at", ""),
        "source_type": doc.get("source_type", ""),
        "source_id": doc.get("source_id", ""),
        "source_label": doc.get("source_label", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


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
        "assigned_team_id": body.assigned_team_id or "",
        "assigned_person_id": body.assigned_person_id or "",
        "location": body.location or config["defaults"].get("location", ""),
        "zone": body.zone or "",
        "scheduled_at": body.scheduled_at or "",
        "due_at": body.due_at or "",
        "recurring": body.recurring,
        "recurrence_rule": body.recurrence_rule or "",
        "recurrence_start_at": body.recurrence_start_at or "",
        "recurrence_end_at": body.recurrence_end_at or "",
        "missed_occurrence_behavior": body.missed_occurrence_behavior or "",
        "template_id": body.template_id or "",
        "generated_from_template_id": body.generated_from_template_id or "",
        "lifecycle_state": body.lifecycle_state or "",
        "active_at": body.active_at or "",
        "triggered_at": body.triggered_at or "",
        "source_type": body.source_type or "",
        "source_id": body.source_id or "",
        "source_label": body.source_label or "",
        "source_tool": body.source_tool or "",
        "linked_tasking_id": "",
        "promoted_at": "",
        "promoted_by": "",
        "promoted_read_only": False,
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
        "location": body.location or "",
        "zone": body.zone or "",
        "owner": body.owner or "",
        "status": body.status or "",
        "tags": body.tags or [],
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
    allowed = {"name", "kind", "starts_at", "ends_at", "notes", "location", "zone", "owner", "status", "tags"}
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
        "assigned_team_id",
        "assigned_person_id",
        "location",
        "zone",
        "scheduled_at",
        "due_at",
        "recurring",
        "recurrence_rule",
        "recurrence_start_at",
        "recurrence_end_at",
        "missed_occurrence_behavior",
        "template_id",
        "generated_from_template_id",
        "lifecycle_state",
        "active_at",
        "triggered_at",
        "source_type",
        "source_id",
        "source_label",
        "source_tool",
        "metadata",
    }
    existing = col.find_one(
        {config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"_id": 0, "promoted_read_only": 1},
    )
    if existing and existing.get("promoted_read_only"):
        raise HTTPException(status_code=409, detail="Promoted Quick Assignment is read-only")
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


@router.get("/incidents/{incident_id}/planned-meta/schedule-triggers")
def list_schedule_triggers(incident_id: str, schedule_item_id: Optional[str] = None):
    config = _schedule_trigger_config()
    col = get_incident_db(incident_id)[config["collection"]]
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if schedule_item_id:
        query["schedule_item_id"] = schedule_item_id
    docs = list(col.find(query, {"_id": 0}).sort(config["sort"], 1))
    return [_map_schedule_trigger(doc) for doc in docs]


@router.post("/incidents/{incident_id}/planned-meta/schedule-triggers", status_code=201)
def create_schedule_trigger(incident_id: str, body: ScheduleTriggerCreate):
    config = _schedule_trigger_config()
    col = get_incident_db(incident_id)[config["collection"]]
    record_id = _next_compound_id(col, incident_id, config)
    now = _utcnow()
    doc: Dict[str, Any] = {
        "_id": _new_id(),
        config["id_field"]: record_id,
        "incident_id": incident_id,
        "schedule_item_id": body.schedule_item_id or "",
        "trigger_type": body.trigger_type or "notification",
        "label": body.label,
        "offset_minutes": body.offset_minutes,
        "trigger_at": body.trigger_at or "",
        "relative_to": body.relative_to or "start",
        "enabled": body.enabled,
        "audience_role": body.audience_role or "",
        "audience_user_id": body.audience_user_id or "",
        "notification_channel": body.notification_channel or "",
        "requires_acknowledgement": body.requires_acknowledgement,
        "message_template": body.message_template or "",
        "link_to_schedule_item": body.link_to_schedule_item,
        "quick_assignment_template_id": body.quick_assignment_template_id or "",
        "title": body.title or "",
        "summary": body.summary or "",
        "assigned_to": body.assigned_to or "",
        "assigned_team_id": body.assigned_team_id or "",
        "assigned_person_id": body.assigned_person_id or "",
        "location": body.location or "",
        "zone": body.zone or "",
        "priority": body.priority or "",
        "recurring": body.recurring,
        "recurrence_rule": body.recurrence_rule or "",
        "missed_occurrence_behavior": body.missed_occurrence_behavior or "",
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    saved = col.find_one({config["id_field"]: record_id}, {"_id": 0})
    return _map_schedule_trigger(saved)


@router.patch("/incidents/{incident_id}/planned-meta/schedule-triggers/{record_id}")
def update_schedule_trigger(incident_id: str, record_id: int, patch: Dict[str, Any] = Body(...)):
    config = _schedule_trigger_config()
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    allowed = {
        "schedule_item_id",
        "trigger_type",
        "label",
        "offset_minutes",
        "trigger_at",
        "relative_to",
        "enabled",
        "audience_role",
        "audience_user_id",
        "notification_channel",
        "requires_acknowledgement",
        "message_template",
        "link_to_schedule_item",
        "quick_assignment_template_id",
        "title",
        "summary",
        "assigned_to",
        "assigned_team_id",
        "assigned_person_id",
        "location",
        "zone",
        "priority",
        "recurring",
        "recurrence_rule",
        "missed_occurrence_behavior",
    }
    updates = {key: value for key, value in patch.items() if key in allowed}
    updates["updated_at"] = _utcnow()
    doc = col.find_one_and_update(
        {config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Schedule trigger not found")
    return _map_schedule_trigger(doc)


@router.delete("/incidents/{incident_id}/planned-meta/schedule-triggers/{record_id}", status_code=204)
def delete_schedule_trigger(incident_id: str, record_id: int):
    config = _schedule_trigger_config()
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    result = col.update_one(
        {config["id_field"]: compound_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "updated_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Schedule trigger not found")


@router.get("/incidents/{incident_id}/planned-meta/notifications")
def list_notifications(incident_id: str):
    config = _notification_config()
    col = get_incident_db(incident_id)[config["collection"]]
    docs = list(col.find({"incident_id": incident_id, "deleted": {"$ne": True}}, {"_id": 0}).sort(config["sort"], 1))
    return [_map_notification(doc) for doc in docs]


@router.post("/incidents/{incident_id}/planned-meta/notifications", status_code=201)
def create_notification(incident_id: str, body: NotificationCreate):
    config = _notification_config()
    col = get_incident_db(incident_id)[config["collection"]]
    record_id = _next_compound_id(col, incident_id, config)
    now = _utcnow()
    doc: Dict[str, Any] = {
        "_id": _new_id(),
        config["id_field"]: record_id,
        "incident_id": incident_id,
        "title": body.title,
        "message": body.message,
        "severity": body.severity,
        "audience_role": body.audience_role or "",
        "audience_user_id": body.audience_user_id or "",
        "notification_channel": body.notification_channel or "",
        "location": body.location or "",
        "zone": body.zone or "",
        "scheduled_at": body.scheduled_at or "",
        "triggered_at": body.triggered_at or now,
        "acknowledged_at": "",
        "acknowledged_by": "",
        "dismissed_at": "",
        "source_type": body.source_type or "",
        "source_id": body.source_id or "",
        "source_label": body.source_label or "",
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    saved = col.find_one({config["id_field"]: record_id}, {"_id": 0})
    return _map_notification(saved)


@router.post("/incidents/{incident_id}/planned-meta/notifications/{record_id}/acknowledge")
def acknowledge_notification(incident_id: str, record_id: int, body: AcknowledgeRequest):
    config = _notification_config()
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    now = _utcnow()
    doc = col.find_one_and_update(
        {config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"$set": {"acknowledged_at": now, "acknowledged_by": body.acknowledged_by, "updated_at": now}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _map_notification(doc)


@router.post("/incidents/{incident_id}/planned-meta/notifications/{record_id}/dismiss")
def dismiss_notification(incident_id: str, record_id: int):
    config = _notification_config()
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    now = _utcnow()
    doc = col.find_one_and_update(
        {config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"$set": {"dismissed_at": now, "updated_at": now}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _map_notification(doc)


@router.post("/incidents/{incident_id}/planned/quick-assignments/{record_id}/promote")
def promote_quick_assignment(incident_id: str, record_id: int, body: PromotionRequest):
    config = _tool_config("quick-assignments")
    col = get_incident_db(incident_id)[config["collection"]]
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    doc = col.find_one({config["id_field"]: compound_id, "incident_id": incident_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Quick Assignment not found")
    if doc.get("linked_tasking_id"):
        return _map_doc(doc, config)

    task_config = {
        "id_field": "task_id",
        "prefix": "TASK",
    }
    tasks_col = get_incident_db(incident_id)[IncidentCollections.OPERATIONS_TASKS]
    task_id = _next_compound_id(tasks_col, incident_id, task_config)
    task_int_id = next_int_id(tasks_col)
    now = _utcnow()
    task_doc: Dict[str, Any] = {
        "_id": _new_id(),
        "int_id": task_int_id,
        "task_id": task_id,
        "incident_id": incident_id,
        "title": doc.get("title", ""),
        "assignment": doc.get("summary", ""),
        "status": doc.get("status") or "Planned",
        "priority": doc.get("priority") or "Medium",
        "location": doc.get("location") or doc.get("zone", ""),
        "due_time": doc.get("due_at") or doc.get("scheduled_at", ""),
        "source_type": "planned_quick_assignment",
        "source_id": doc.get(config["id_field"], ""),
        "source_label": doc.get("title", ""),
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    tasks_col.insert_one(task_doc)
    updates = {
        "linked_tasking_id": str(task_int_id),
        "promoted_at": now,
        "promoted_by": body.promoted_by,
        "promoted_read_only": True,
        "lifecycle_state": "Promoted",
        "updated_at": now,
    }
    saved = col.find_one_and_update(
        {config["id_field"]: compound_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    return _map_doc(saved, config)
