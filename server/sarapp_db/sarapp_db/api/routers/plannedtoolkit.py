"""Planned Event Toolkit router (MongoDB-backed)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.audit import write_audit
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.int_id import next_int_id, next_record_id
from sarapp_db.mongo.repository import BaseRepository

logger = logging.getLogger(__name__)
router = APIRouter()


class PlannedCampaignsRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_CAMPAIGNS


class PlannedEventSchedulesRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_EVENT_SCHEDULES


class PlannedVendorsRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_VENDORS


class PlannedPermitsRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_PERMITS


class PlannedQuickAssignmentsRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_QUICK_ASSIGNMENTS


class PlannedHealthInspectionsRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_HEALTH_INSPECTIONS


class PlannedScheduleTriggersRepository(BaseRepository):
    collection_name = IncidentCollections.PLANNED_SCHEDULE_TRIGGERS


class OperationsTasksRepository(BaseRepository):
    collection_name = IncidentCollections.OPERATIONS_TASKS


_REPOSITORIES: dict[str, type[BaseRepository]] = {
    IncidentCollections.PLANNED_CAMPAIGNS: PlannedCampaignsRepository,
    IncidentCollections.PLANNED_EVENT_SCHEDULES: PlannedEventSchedulesRepository,
    IncidentCollections.PLANNED_VENDORS: PlannedVendorsRepository,
    IncidentCollections.PLANNED_PERMITS: PlannedPermitsRepository,
    IncidentCollections.PLANNED_QUICK_ASSIGNMENTS: PlannedQuickAssignmentsRepository,
    IncidentCollections.PLANNED_HEALTH_INSPECTIONS: PlannedHealthInspectionsRepository,
    IncidentCollections.PLANNED_SCHEDULE_TRIGGERS: PlannedScheduleTriggersRepository,
    IncidentCollections.OPERATIONS_TASKS: OperationsTasksRepository,
}

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


def _audit(
    incident_id: str,
    *,
    entity_id: str,
    action: str,
    changed_by: str = "",
    field_changes: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Write an audit record; never blocks the caller's mutation on failure."""
    try:
        write_audit(
            get_incident_db(incident_id),
            incident_id=incident_id,
            entity_type="planned_schedule_item",
            entity_id=entity_id,
            action=action,
            changed_by=changed_by or "",
            field_changes=field_changes,
            source_module="plannedtoolkit",
        )
    except Exception:
        logger.exception("Failed to write audit record for %s/%s", entity_id, action)


def _pending_triggers_for_schedule_item(incident_id: str, schedule_item_id: str) -> list[Dict[str, Any]]:
    trig_config = _schedule_trigger_config()
    trig_repo = _repo_for_config(incident_id, trig_config)
    return trig_repo.find_many({
        "incident_id": incident_id,
        "schedule_item_id": schedule_item_id,
        "fired_at": {"$exists": False},
    })


def _disable_pending_triggers(incident_id: str, schedule_item_id: str) -> None:
    """Cancel triggers never used, per the brief: 'do not retract notifications
    already delivered' — only triggers with no `fired_at` are touched."""
    trig_config = _schedule_trigger_config()
    trig_repo = _repo_for_config(incident_id, trig_config)
    for trig in _pending_triggers_for_schedule_item(incident_id, schedule_item_id):
        if trig.get("enabled", True):
            trig_repo.update_one(trig["_id"], {"enabled": False})


def _sync_triggers_after_schedule_change(incident_id: str, schedule_item_id: str, schedule_item_doc: Dict[str, Any]) -> None:
    """After a reschedule or cancellation, keep this item's not-yet-fired
    triggers consistent: cancelled -> disable them; rescheduled -> recompute
    any relative (offset_minutes-based) trigger's absolute `trigger_at`.
    Never touches an already-fired trigger.
    """
    if schedule_item_doc.get("status") == "Cancelled":
        _disable_pending_triggers(incident_id, schedule_item_id)
        return
    trig_config = _schedule_trigger_config()
    trig_repo = _repo_for_config(incident_id, trig_config)
    for trig in _pending_triggers_for_schedule_item(incident_id, schedule_item_id):
        offset = trig.get("offset_minutes")
        if offset is None:
            continue
        anchor_field = "ends_at" if trig.get("relative_to") == "end" else "starts_at"
        anchor_dt = _parse_schedule_timestamp(schedule_item_doc.get(anchor_field))
        if anchor_dt is None:
            continue
        new_trigger_at = (anchor_dt + timedelta(minutes=int(offset))).isoformat()
        if new_trigger_at != trig.get("trigger_at"):
            trig_repo.update_one(trig["_id"], {"trigger_at": new_trigger_at})


def _resolve_trigger_at(
    incident_id: str,
    schedule_item_id: str,
    offset_minutes: Optional[int],
    relative_to: str,
    explicit_trigger_at: str,
) -> str:
    """Compute a relative reminder's absolute `trigger_at` at write time, so
    the trigger engine keeps reading only absolute timestamps (no engine
    changes needed) — see plannedtoolkit_phase0_audit.md Phase 1D notes."""
    if explicit_trigger_at:
        return explicit_trigger_at
    if not schedule_item_id or offset_minutes is None:
        return ""
    schedule_config = _tool_config("promotions/schedule")
    schedule_repo = _repo_for_config(incident_id, schedule_config)
    item = schedule_repo.find_one({schedule_config["id_field"]: schedule_item_id, "incident_id": incident_id})
    if not item:
        return ""
    anchor_field = "ends_at" if relative_to == "end" else "starts_at"
    anchor_dt = _parse_schedule_timestamp(item.get(anchor_field))
    if anchor_dt is None:
        return ""
    return (anchor_dt + timedelta(minutes=int(offset_minutes))).isoformat()


def _repo(incident_id: str, collection_name: str) -> BaseRepository:
    return _REPOSITORIES[collection_name](get_incident_db(incident_id))


def _repo_for_config(incident_id: str, config: dict[str, Any]) -> BaseRepository:
    return _repo(incident_id, config["collection"])


def _find_by_compound_id(
    repo: BaseRepository,
    incident_id: str,
    config: dict[str, Any],
    record_id: int,
) -> dict[str, Any] | None:
    compound_id = f"{incident_id}-{config['prefix']}-{record_id}"
    return repo.find_one({config["id_field"]: compound_id, "incident_id": incident_id})


def _tool_config(tool: str) -> dict[str, Any]:
    config = _TOOLS.get(tool)
    if not config:
        raise HTTPException(status_code=404, detail="Planned toolkit tool not found")
    return config


def _next_compound_id(repo: BaseRepository, incident_id: str, config: dict[str, Any]) -> str:
    """Mint the next compound id for a planned-toolkit collection.

    Each of these collections lives in a single per-incident database, so a
    dedicated indexed `seq` field (see `next_record_id`) replaces the old
    O(n) full-collection scan for the max existing suffix.
    """
    seq = next_record_id(repo._col, "seq")
    return f"{incident_id}-{config['prefix']}-{seq}"


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
        "actual_start_at": doc.get("actual_start_at", ""),
        "actual_end_at": doc.get("actual_end_at", ""),
        "time_zone": doc.get("time_zone", ""),
        "delay_reason": doc.get("delay_reason", ""),
        "cancellation_reason": doc.get("cancellation_reason", ""),
        "meeting_id": doc.get("meeting_id", ""),
        "gis_feature_id": doc.get("gis_feature_id", ""),
        "quick_assignment_id": doc.get("quick_assignment_id", ""),
        "revision": int(doc.get("revision", 0)),
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
    actual_start_at: Optional[str] = None
    actual_end_at: Optional[str] = None
    time_zone: Optional[str] = None
    notes: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    owner: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team_id: Optional[str] = None
    assigned_person_id: Optional[str] = None
    meeting_id: Optional[str] = None
    gis_feature_id: Optional[str] = None
    quick_assignment_id: Optional[str] = None
    status: Optional[str] = None
    delay_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    changed_by: Optional[str] = None


class ScheduleStatusActionRequest(BaseModel):
    """Body for the event-day action endpoints (start/complete/delay/resume/cancel).

    All fields are optional: actual timestamps default to "now" when the
    action records one, but remain overridable (e.g. backfilling an actual
    start time that was recorded late).
    """

    actual_start_at: Optional[str] = None
    actual_end_at: Optional[str] = None
    delay_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    revised_start_at: Optional[str] = None
    changed_by: Optional[str] = None
    expected_revision: Optional[int] = None


class ScheduleCorrectionRequest(BaseModel):
    """Body for the /correct endpoint -- an explicit, reason-logged override
    that bypasses the routine transition table, for the two cases that need
    one: reopening a terminal (Completed/Cancelled) status, and fixing an
    actual timestamp that was recorded wrong. `reason` is mandatory; there is
    no role/permission system in this router to check "authorized" against,
    so the explicit action plus a mandatory, audited reason is what "authorized
    correction" means here, consistent with delay/cancel's existing reason
    requirements.
    """

    reason: str
    status: Optional[str] = None
    actual_start_at: Optional[str] = None
    actual_end_at: Optional[str] = None
    corrected_by: Optional[str] = None
    expected_revision: Optional[int] = None


# The five statuses the Phase 1A/1B brief specifies. Kept as an explicit
# allow-list (not a free string) so an invalid transition is rejected
# consistently everywhere a status can change, per the brief's requirement.
SCHEDULE_STATUSES = ("Scheduled", "In Progress", "Completed", "Delayed", "Cancelled")

# A status may move to any status in its value set below, or stay unchanged.
# Completed/Cancelled are terminal — no transition out, matching "do not
# automatically change an activity's status solely because its scheduled
# time has passed" (nothing times out of a terminal state either).
_SCHEDULE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "Scheduled": {"In Progress", "Delayed", "Cancelled"},
    "In Progress": {"Completed", "Delayed", "Cancelled"},
    "Delayed": {"Scheduled", "In Progress", "Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}

# A terminal status (Completed/Cancelled) has no routine transition out --
# reaching a different status from one requires the explicit, reason-logged
# /correct endpoint below, not a plain PATCH or event-day action. This set
# mirrors the brief's matrix: Delayed can no longer reach Completed directly
# (resume first), matching "Resume Activity: return a delayed activity to
# Scheduled or In Progress as appropriate" instead of letting Delayed skip
# straight to Completed.
_TERMINAL_SCHEDULE_STATUSES = {"Completed", "Cancelled"}


def _check_schedule_concurrency(existing: Dict[str, Any], expected_revision: Any, config: Dict[str, Any]) -> None:
    """Optimistic concurrency via a small integer `revision` counter.

    `updated_at` (every document's existing timestamp field) was tried
    first and rejected: `BaseRepository` stamps it at one-second
    resolution, so two writes to the same record within the same second —
    entirely realistic for two operators clicking around, let alone two
    automated calls in a row — produce an identical value and the "stale
    update" case silently passes. `revision` is incremented by exactly 1 on
    every write (see the call sites below) and is reliable regardless of
    timing. Optional for backward compatibility: a caller that never sends
    `expected_revision` gets no check, preserving prior last-write-wins
    behavior.
    """
    if expected_revision in (None, ""):
        return
    try:
        expected_revision = int(expected_revision)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="expected_revision must be an integer")
    if int(existing.get("revision", 0)) != expected_revision:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This activity was changed by another operator. Reload to see the latest version.",
                "current": _map_doc(existing, config),
            },
        )


def _validate_schedule_status_transition(current: str, target: str) -> None:
    if target == current:
        return
    if target not in SCHEDULE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unknown schedule status: {target!r}")
    allowed = _SCHEDULE_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move a schedule item from {current!r} to {target!r}",
        )


def _parse_schedule_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid timestamp: {value!r}")


def _validate_schedule_time_range(start: Any, end: Any, *, label: str) -> None:
    start_dt = _parse_schedule_timestamp(start)
    end_dt = _parse_schedule_timestamp(end)
    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        raise HTTPException(status_code=422, detail=f"{label} end time cannot be before its start time")


class ScheduleTriggerCreate(BaseModel):
    schedule_item_id: Optional[str] = None
    trigger_type: str = "notification"
    label: str = ""
    offset_minutes: Optional[int] = None
    trigger_at: Optional[str] = None
    relative_to: str = "start"
    enabled: bool = True
    severity: Optional[str] = None
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


class PromotionRequest(BaseModel):
    promoted_by: str = ""


def _schedule_trigger_config() -> dict[str, Any]:
    return {
        "collection": IncidentCollections.PLANNED_SCHEDULE_TRIGGERS,
        "id_field": "trigger_id",
        "prefix": "PLAN-TRIGGER",
        "sort": "trigger_at",
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
        "fired_at": doc.get("fired_at", ""),
        "fire_error": doc.get("fire_error", ""),
        "severity": doc.get("severity", ""),
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


@router.get("/incidents/{incident_id}/planned/{tool}")
def list_records(incident_id: str, tool: str, status: Optional[str] = None, search: Optional[str] = None):
    config = _tool_config(tool)
    repo = _repo_for_config(incident_id, config)
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
            {"location": {"$regex": search, "$options": "i"}},
        ]
    docs = repo.find_many(query, sort=[(config["sort"], 1)])
    return [_map_doc(doc, config) for doc in docs]


@router.post("/incidents/{incident_id}/planned/{tool}", status_code=201)
def create_record(incident_id: str, tool: str, body: PlannedRecordCreate):
    config = _tool_config(tool)
    repo = _repo_for_config(incident_id, config)
    record_id = _next_compound_id(repo, incident_id, config)
    now = _utcnow()
    doc: Dict[str, Any] = {
        config["id_field"]: record_id,
        "seq": _public_id(record_id),
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
    saved = repo.insert_one(doc)
    return _map_doc(saved, config)


@router.get("/incidents/{incident_id}/planned/promotions/schedule")
def list_schedule(incident_id: str):
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    docs = repo.find_many({"incident_id": incident_id}, sort=[(config["sort"], 1)])
    return [_map_doc(doc, config) for doc in docs]


@router.post("/incidents/{incident_id}/planned/promotions/schedule", status_code=201)
def create_schedule(incident_id: str, body: ScheduleItemCreate):
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    status = body.status or "Scheduled"
    if status not in SCHEDULE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unknown schedule status: {status!r}")
    _validate_schedule_time_range(body.starts_at, body.ends_at, label="Planned")
    _validate_schedule_time_range(body.actual_start_at, body.actual_end_at, label="Actual")
    record_id = _next_compound_id(repo, incident_id, config)
    now = _utcnow()
    doc: Dict[str, Any] = {
        config["id_field"]: record_id,
        "seq": _public_id(record_id),
        "incident_id": incident_id,
        "tool": "promotions/schedule",
        "name": body.name,
        "kind": body.kind or "Milestone",
        "starts_at": body.starts_at or "",
        "ends_at": body.ends_at or "",
        "actual_start_at": body.actual_start_at or "",
        "actual_end_at": body.actual_end_at or "",
        "time_zone": body.time_zone or "",
        "notes": body.notes or "",
        "location": body.location or "",
        "zone": body.zone or "",
        "owner": body.owner or "",
        "assigned_to": body.assigned_to or "",
        "assigned_team_id": body.assigned_team_id or "",
        "assigned_person_id": body.assigned_person_id or "",
        "meeting_id": body.meeting_id or "",
        "gis_feature_id": body.gis_feature_id or "",
        "quick_assignment_id": body.quick_assignment_id or "",
        "status": status,
        "delay_reason": body.delay_reason or "",
        "cancellation_reason": body.cancellation_reason or "",
        "tags": body.tags or [],
        "revision": 0,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    saved = repo.insert_one(doc)
    _audit(incident_id, entity_id=record_id, action="schedule_item.created", changed_by=body.changed_by or "")
    return _map_doc(saved, config)


_SCHEDULE_PATCH_FIELDS = {
    "name", "kind", "starts_at", "ends_at", "actual_start_at", "actual_end_at",
    "time_zone", "notes", "location", "zone", "owner", "assigned_to",
    "assigned_team_id", "assigned_person_id", "meeting_id", "gis_feature_id",
    "quick_assignment_id", "status", "delay_reason", "cancellation_reason", "tags",
}


@router.patch("/incidents/{incident_id}/planned/promotions/schedule/{record_id}")
def update_schedule(incident_id: str, record_id: int, patch: Dict[str, Any] = Body(...)):
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    _check_schedule_concurrency(existing, patch.get("expected_revision"), config)

    updates = {key: value for key, value in patch.items() if key in _SCHEDULE_PATCH_FIELDS}
    changed_by = str(patch.get("changed_by") or "")

    target_status = updates.get("status")
    if target_status is not None:
        _validate_schedule_status_transition(existing.get("status", ""), target_status)

    starts_at = updates.get("starts_at", existing.get("starts_at"))
    ends_at = updates.get("ends_at", existing.get("ends_at"))
    _validate_schedule_time_range(starts_at, ends_at, label="Planned")
    actual_start_at = updates.get("actual_start_at", existing.get("actual_start_at"))
    actual_end_at = updates.get("actual_end_at", existing.get("actual_end_at"))
    _validate_schedule_time_range(actual_start_at, actual_end_at, label="Actual")

    field_changes = [
        {"field": key, "old": existing.get(key), "new": value}
        for key, value in updates.items()
        if existing.get(key) != value
    ]
    updates["revision"] = int(existing.get("revision", 0)) + 1
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    if "starts_at" in updates or "ends_at" in updates or "status" in updates:
        _sync_triggers_after_schedule_change(incident_id, existing[config["id_field"]], doc)
    if field_changes:
        _audit(incident_id, entity_id=existing[config["id_field"]], action="schedule_item.updated", changed_by=changed_by, field_changes=field_changes)
    return _map_doc(doc, config)


@router.delete("/incidents/{incident_id}/planned/promotions/schedule/{record_id}", status_code=204)
def delete_schedule(incident_id: str, record_id: int):
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing or not repo.soft_delete(existing["_id"]):
        raise HTTPException(status_code=404, detail="Schedule item not found")
    _disable_pending_triggers(incident_id, existing[config["id_field"]])
    _audit(incident_id, entity_id=existing[config["id_field"]], action="schedule_item.deleted")


def _schedule_status_action(
    incident_id: str,
    record_id: int,
    *,
    allowed_from: set[str],
    target_status: str,
    body: ScheduleStatusActionRequest,
    require_delay_reason: bool = False,
    require_cancellation_reason: bool = False,
    stamp_actual_start: bool = False,
    stamp_actual_end: bool = False,
) -> Dict[str, Any]:
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    _check_schedule_concurrency(existing, body.expected_revision, config)

    current_status = existing.get("status", "")
    if current_status not in allowed_from:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move a schedule item from {current_status!r} to {target_status!r}",
        )

    now = _utcnow()
    updates: Dict[str, Any] = {"status": target_status}

    if stamp_actual_start:
        updates["actual_start_at"] = body.actual_start_at or existing.get("actual_start_at") or now
    if stamp_actual_end:
        actual_end_at = body.actual_end_at or existing.get("actual_end_at") or now
        # Preserve the planned timestamps — never overwrite starts_at/ends_at
        # when recording an actual time.
        updates["actual_end_at"] = actual_end_at
        _validate_schedule_time_range(
            updates.get("actual_start_at", existing.get("actual_start_at")), actual_end_at, label="Actual"
        )

    if require_delay_reason:
        delay_reason = body.delay_reason or existing.get("delay_reason") or ""
        if not delay_reason.strip():
            raise HTTPException(status_code=422, detail="delay_reason is required to mark a schedule item delayed")
        updates["delay_reason"] = delay_reason
        if body.revised_start_at:
            # A revised expected start is just a normal reschedule of
            # starts_at -- reuses the existing field and its existing
            # trigger-resync behavior rather than a new "revised time" model.
            _validate_schedule_time_range(body.revised_start_at, existing.get("ends_at"), label="Planned")
            updates["starts_at"] = body.revised_start_at
    if require_cancellation_reason:
        cancellation_reason = body.cancellation_reason or existing.get("cancellation_reason") or ""
        if not cancellation_reason.strip():
            raise HTTPException(status_code=422, detail="cancellation_reason is required to cancel a schedule item")
        updates["cancellation_reason"] = cancellation_reason

    field_changes = [
        {"field": key, "old": existing.get(key), "new": value}
        for key, value in updates.items()
        if existing.get(key) != value
    ]
    updates["revision"] = int(existing.get("revision", 0)) + 1
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    if target_status == "Cancelled" or "starts_at" in updates:
        _sync_triggers_after_schedule_change(incident_id, existing[config["id_field"]], doc)
    _audit(
        incident_id,
        entity_id=existing[config["id_field"]],
        action=f"schedule_item.{target_status.lower().replace(' ', '_')}",
        changed_by=body.changed_by or "",
        field_changes=field_changes,
    )
    return _map_doc(doc, config)


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/start")
def start_schedule_item(incident_id: str, record_id: int, body: ScheduleStatusActionRequest = ScheduleStatusActionRequest()):
    return _schedule_status_action(
        incident_id, record_id,
        allowed_from={"Scheduled"}, target_status="In Progress", body=body,
        stamp_actual_start=True,
    )


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/resume")
def resume_schedule_item(incident_id: str, record_id: int, body: ScheduleStatusActionRequest = ScheduleStatusActionRequest()):
    """Resume returns a delayed activity to In Progress if it had already
    actually started before the delay, or back to Scheduled if it never
    did -- "as appropriate" per the brief, not an unconditional In Progress."""
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    target_status = "In Progress" if existing.get("actual_start_at") else "Scheduled"
    return _schedule_status_action(
        incident_id, record_id,
        allowed_from={"Delayed"}, target_status=target_status, body=body,
        stamp_actual_start=(target_status == "In Progress"),
    )


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/complete")
def complete_schedule_item(incident_id: str, record_id: int, body: ScheduleStatusActionRequest = ScheduleStatusActionRequest()):
    return _schedule_status_action(
        incident_id, record_id,
        allowed_from={"In Progress"}, target_status="Completed", body=body,
        stamp_actual_end=True,
    )


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/delay")
def delay_schedule_item(incident_id: str, record_id: int, body: ScheduleStatusActionRequest = ScheduleStatusActionRequest()):
    return _schedule_status_action(
        incident_id, record_id,
        allowed_from={"Scheduled", "In Progress"}, target_status="Delayed", body=body,
        require_delay_reason=True,
    )


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/cancel")
def cancel_schedule_item(incident_id: str, record_id: int, body: ScheduleStatusActionRequest = ScheduleStatusActionRequest()):
    return _schedule_status_action(
        incident_id, record_id,
        allowed_from={"Scheduled", "In Progress", "Delayed"}, target_status="Cancelled", body=body,
        require_cancellation_reason=True,
    )


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/correct")
def correct_schedule_item(incident_id: str, record_id: int, body: ScheduleCorrectionRequest):
    """Explicit, reason-logged override for the two things the routine
    transition table and event-day actions deliberately forbid: reopening a
    terminal (Completed/Cancelled) status, and fixing an actual timestamp
    that was recorded wrong. Any other field (planned times, responsibility,
    links) is still corrected through the normal PATCH -- this endpoint
    exists only for what that path can't do.
    """
    if not body.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required to correct a schedule item")

    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    _check_schedule_concurrency(existing, body.expected_revision, config)

    updates: Dict[str, Any] = {}
    if body.status is not None:
        if body.status not in SCHEDULE_STATUSES:
            raise HTTPException(status_code=422, detail=f"Unknown schedule status: {body.status!r}")
        updates["status"] = body.status
    if body.actual_start_at is not None:
        updates["actual_start_at"] = body.actual_start_at
    if body.actual_end_at is not None:
        updates["actual_end_at"] = body.actual_end_at
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one of status, actual_start_at, actual_end_at to correct")

    actual_start_at = updates.get("actual_start_at", existing.get("actual_start_at"))
    actual_end_at = updates.get("actual_end_at", existing.get("actual_end_at"))
    _validate_schedule_time_range(actual_start_at, actual_end_at, label="Actual")

    field_changes = [
        {"field": key, "old": existing.get(key), "new": value}
        for key, value in updates.items()
        if existing.get(key) != value
    ]
    field_changes.append({"field": "reason", "old": None, "new": body.reason})
    updates["revision"] = int(existing.get("revision", 0)) + 1
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    if "status" in updates:
        _sync_triggers_after_schedule_change(incident_id, existing[config["id_field"]], doc)
    _audit(
        incident_id, entity_id=existing[config["id_field"]], action="schedule_item.corrected",
        changed_by=body.corrected_by or "", field_changes=field_changes,
    )
    return _map_doc(doc, config)


@router.post("/incidents/{incident_id}/planned/promotions/schedule/{record_id}/create-quick-assignment", status_code=201)
def create_quick_assignment_from_schedule_item(incident_id: str, record_id: int):
    """Phase 1D: create a Quick Assignment from a schedule activity and
    establish the source relationship automatically, per the brief. The
    Quick Assignment's lifecycle (status, promotion) stays fully
    independent afterward — this only wires the initial link."""
    config = _tool_config("promotions/schedule")
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    if existing.get("quick_assignment_id"):
        raise HTTPException(status_code=409, detail="Schedule item already has a linked Quick Assignment")

    qa_config = _tool_config("quick-assignments")
    qa_repo = _repo_for_config(incident_id, qa_config)
    qa_record_id = _next_compound_id(qa_repo, incident_id, qa_config)
    now = _utcnow()
    qa_doc: Dict[str, Any] = {
        qa_config["id_field"]: qa_record_id,
        "seq": _public_id(qa_record_id),
        "incident_id": incident_id,
        "tool": "quick-assignments",
        "title": existing.get("name", ""),
        "summary": existing.get("notes", ""),
        "status": qa_config["defaults"].get("status", "Planned"),
        "priority": qa_config["defaults"].get("priority", "Medium"),
        "assigned_to": existing.get("assigned_to", ""),
        "assigned_team_id": existing.get("assigned_team_id", ""),
        "assigned_person_id": existing.get("assigned_person_id", ""),
        "location": existing.get("location", ""),
        "zone": existing.get("zone", ""),
        "scheduled_at": existing.get("starts_at", ""),
        "due_at": existing.get("ends_at", ""),
        "recurring": False,
        "recurrence_rule": "",
        "recurrence_start_at": "",
        "recurrence_end_at": "",
        "missed_occurrence_behavior": "",
        "template_id": "",
        "generated_from_template_id": "",
        "lifecycle_state": "Active",
        "active_at": "",
        "triggered_at": "",
        "source_type": "planned_schedule_item",
        "source_id": existing[config["id_field"]],
        "source_label": existing.get("name", ""),
        "source_tool": "promotions/schedule",
        "linked_tasking_id": "",
        "promoted_at": "",
        "promoted_by": "",
        "promoted_read_only": False,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    saved_qa = qa_repo.insert_one(qa_doc)
    repo.update_one(existing["_id"], {"quick_assignment_id": qa_record_id})
    updated_schedule = repo.find_by_id(existing["_id"])
    _audit(
        incident_id, entity_id=existing[config["id_field"]], action="schedule_item.quick_assignment_created",
        field_changes=[{"field": "quick_assignment_id", "old": "", "new": qa_record_id}],
    )
    return {
        "schedule_item": _map_doc(updated_schedule, config),
        "quick_assignment": _map_doc(saved_qa, qa_config),
    }


@router.patch("/incidents/{incident_id}/planned/{tool}/{record_id}")
def update_record(incident_id: str, tool: str, record_id: int, patch: Dict[str, Any] = Body(...)):
    config = _tool_config(tool)
    repo = _repo_for_config(incident_id, config)
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
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if existing and existing.get("promoted_read_only"):
        raise HTTPException(status_code=409, detail="Promoted Quick Assignment is read-only")
    updates = {key: value for key, value in patch.items() if key in allowed}
    if not existing:
        raise HTTPException(status_code=404, detail="Planned toolkit record not found")
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    return _map_doc(doc, config)


@router.delete("/incidents/{incident_id}/planned/{tool}/{record_id}", status_code=204)
def delete_record(incident_id: str, tool: str, record_id: int):
    config = _tool_config(tool)
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing or not repo.soft_delete(existing["_id"]):
        raise HTTPException(status_code=404, detail="Planned toolkit record not found")


@router.get("/incidents/{incident_id}/planned-meta/schedule-triggers")
def list_schedule_triggers(incident_id: str, schedule_item_id: Optional[str] = None):
    config = _schedule_trigger_config()
    repo = _repo_for_config(incident_id, config)
    query: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if schedule_item_id:
        query["schedule_item_id"] = schedule_item_id
    docs = repo.find_many(query, sort=[(config["sort"], 1)])
    return [_map_schedule_trigger(doc) for doc in docs]


@router.post("/incidents/{incident_id}/planned-meta/schedule-triggers", status_code=201)
def create_schedule_trigger(incident_id: str, body: ScheduleTriggerCreate):
    config = _schedule_trigger_config()
    repo = _repo_for_config(incident_id, config)
    record_id = _next_compound_id(repo, incident_id, config)
    now = _utcnow()
    trigger_at = _resolve_trigger_at(
        incident_id, body.schedule_item_id or "", body.offset_minutes, body.relative_to or "start", body.trigger_at or ""
    )
    doc: Dict[str, Any] = {
        config["id_field"]: record_id,
        "seq": _public_id(record_id),
        "incident_id": incident_id,
        "schedule_item_id": body.schedule_item_id or "",
        "trigger_type": body.trigger_type or "notification",
        "label": body.label,
        "offset_minutes": body.offset_minutes,
        "trigger_at": trigger_at,
        "relative_to": body.relative_to or "start",
        "enabled": body.enabled,
        "severity": body.severity or "",
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
    saved = repo.insert_one(doc)
    if doc["schedule_item_id"]:
        _audit(
            incident_id, entity_id=doc["schedule_item_id"], action="schedule_item.reminder_created",
            field_changes=[{"field": "trigger_id", "old": "", "new": record_id}],
        )
    return _map_schedule_trigger(saved)


@router.patch("/incidents/{incident_id}/planned-meta/schedule-triggers/{record_id}")
def update_schedule_trigger(incident_id: str, record_id: int, patch: Dict[str, Any] = Body(...)):
    config = _schedule_trigger_config()
    repo = _repo_for_config(incident_id, config)
    allowed = {
        "schedule_item_id",
        "trigger_type",
        "label",
        "offset_minutes",
        "trigger_at",
        "relative_to",
        "enabled",
        "severity",
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
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule trigger not found")
    if {"offset_minutes", "relative_to", "trigger_at"} & updates.keys() and not existing.get("fired_at"):
        updates["trigger_at"] = _resolve_trigger_at(
            incident_id,
            updates.get("schedule_item_id", existing.get("schedule_item_id", "")),
            updates.get("offset_minutes", existing.get("offset_minutes")),
            updates.get("relative_to", existing.get("relative_to", "start")),
            updates.get("trigger_at", "") if "trigger_at" in updates else "",
        )
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    if doc.get("schedule_item_id"):
        _audit(
            incident_id, entity_id=doc["schedule_item_id"], action="schedule_item.reminder_updated",
            field_changes=[{"field": k, "old": existing.get(k), "new": v} for k, v in updates.items() if existing.get(k) != v],
        )
    return _map_schedule_trigger(doc)


@router.delete("/incidents/{incident_id}/planned-meta/schedule-triggers/{record_id}", status_code=204)
def delete_schedule_trigger(incident_id: str, record_id: int):
    config = _schedule_trigger_config()
    repo = _repo_for_config(incident_id, config)
    existing = _find_by_compound_id(repo, incident_id, config, record_id)
    if not existing or not repo.soft_delete(existing["_id"]):
        raise HTTPException(status_code=404, detail="Schedule trigger not found")
    if existing.get("schedule_item_id"):
        _audit(incident_id, entity_id=existing["schedule_item_id"], action="schedule_item.reminder_cancelled")


@router.post("/incidents/{incident_id}/planned/quick-assignments/{record_id}/promote")
def promote_quick_assignment(incident_id: str, record_id: int, body: PromotionRequest):
    config = _tool_config("quick-assignments")
    repo = _repo_for_config(incident_id, config)
    doc = _find_by_compound_id(repo, incident_id, config, record_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Quick Assignment not found")
    if doc.get("linked_tasking_id"):
        return _map_doc(doc, config)

    # Atomically claim the promotion before creating the formal task, so two
    # concurrent promote requests for the same Quick Assignment cannot both
    # pass the not-yet-promoted check above and each create a duplicate task.
    claimed = repo.update_one(
        doc["_id"],
        {"promoted_read_only": True},
        extra_filter={"promoted_read_only": {"$ne": True}},
    )
    if not claimed:
        current = repo.find_by_id(doc["_id"])
        return _map_doc(current or doc, config)

    tasks_repo = _repo(incident_id, IncidentCollections.OPERATIONS_TASKS)
    task_int_id = next_int_id(tasks_repo._col)
    task_id = f"{incident_id}-TASK-{task_int_id}"
    now = _utcnow()
    task_doc: Dict[str, Any] = {
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
    tasks_repo.insert_one(task_doc)
    updates = {
        "linked_tasking_id": str(task_int_id),
        "promoted_at": now,
        "promoted_by": body.promoted_by,
        "promoted_read_only": True,
        "lifecycle_state": "Promoted",
        "updated_at": now,
    }
    repo.update_one(doc["_id"], updates)
    saved = repo.find_by_id(doc["_id"])
    return _map_doc(saved, config)
