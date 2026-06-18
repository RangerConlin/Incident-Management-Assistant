from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class PlannedToolDefinition:
    key: str
    label: str
    title_label: str
    summary_label: str
    default_status: str
    default_priority: str = ""


TOOLS: dict[str, PlannedToolDefinition] = {
    "promotions": PlannedToolDefinition(
        key="promotions",
        label="External Messaging",
        title_label="Campaign",
        summary_label="Message",
        default_status="Draft",
    ),
    "vendors": PlannedToolDefinition(
        key="vendors",
        label="Vendors & Permits",
        title_label="Vendor",
        summary_label="Notes",
        default_status="Pending",
    ),
    "permits": PlannedToolDefinition(
        key="permits",
        label="Permits",
        title_label="Permit",
        summary_label="Notes",
        default_status="Pending",
    ),
    "safety-reports": PlannedToolDefinition(
        key="safety-reports",
        label="Public Safety",
        title_label="Report",
        summary_label="Details",
        default_status="Open",
        default_priority="Medium",
    ),
    "tasks": PlannedToolDefinition(
        key="tasks",
        label="Quick Assignments",
        title_label="Quick Assignment",
        summary_label="Assignment",
        default_status="Planned",
        default_priority="Medium",
    ),
    "quick-assignments": PlannedToolDefinition(
        key="quick-assignments",
        label="Quick Assignments",
        title_label="Quick Assignment",
        summary_label="Assignment",
        default_status="Planned",
        default_priority="Medium",
    ),
    "health-inspections": PlannedToolDefinition(
        key="health-inspections",
        label="Health & Sanitation",
        title_label="Inspection",
        summary_label="Findings",
        default_status="Scheduled",
    ),
}


@dataclass(frozen=True)
class PlannedRecord:
    id: int | None = None
    record_id: str = ""
    incident_id: str = ""
    tool: str = ""
    title: str = ""
    summary: str = ""
    status: str = ""
    priority: str = ""
    assigned_to: str = ""
    assigned_team_id: str = ""
    assigned_person_id: str = ""
    location: str = ""
    zone: str = ""
    scheduled_at: str = ""
    due_at: str = ""
    recurring: bool = False
    recurrence_rule: str = ""
    recurrence_start_at: str = ""
    recurrence_end_at: str = ""
    missed_occurrence_behavior: str = ""
    template_id: str = ""
    generated_from_template_id: str = ""
    lifecycle_state: str = ""
    active_at: str = ""
    triggered_at: str = ""
    source_type: str = ""
    source_id: str = ""
    source_label: str = ""
    source_tool: str = ""
    linked_tasking_id: str = ""
    promoted_at: str = ""
    promoted_by: str = ""
    promoted_read_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def replace(self, **changes: Any) -> "PlannedRecord":
        return replace(self, **changes)


@dataclass(frozen=True)
class ScheduledItem:
    id: int | None = None
    record_id: str = ""
    incident_id: str = ""
    name: str = ""
    kind: str = ""
    starts_at: str = ""
    ends_at: str = ""
    location: str = ""
    zone: str = ""
    owner: str = ""
    status: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class ScheduleTrigger:
    id: int | None = None
    trigger_id: str = ""
    incident_id: str = ""
    schedule_item_id: str = ""
    trigger_type: str = "notification"
    label: str = ""
    offset_minutes: int | None = None
    trigger_at: str = ""
    relative_to: str = "start"
    enabled: bool = True
    audience_role: str = ""
    audience_user_id: str = ""
    notification_channel: str = ""
    requires_acknowledgement: bool = False
    message_template: str = ""
    link_to_schedule_item: bool = True
    quick_assignment_template_id: str = ""
    title: str = ""
    summary: str = ""
    assigned_to: str = ""
    assigned_team_id: str = ""
    assigned_person_id: str = ""
    location: str = ""
    zone: str = ""
    priority: str = ""
    recurring: bool = False
    recurrence_rule: str = ""
    missed_occurrence_behavior: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class PlannedNotification:
    id: int | None = None
    notification_id: str = ""
    incident_id: str = ""
    title: str = ""
    message: str = ""
    severity: str = ""
    audience_role: str = ""
    audience_user_id: str = ""
    notification_channel: str = ""
    location: str = ""
    zone: str = ""
    scheduled_at: str = ""
    triggered_at: str = ""
    acknowledged_at: str = ""
    acknowledged_by: str = ""
    dismissed_at: str = ""
    source_type: str = ""
    source_id: str = ""
    source_label: str = ""
    created_at: str = ""
    updated_at: str = ""


def record_from_dict(data: dict[str, Any]) -> PlannedRecord:
    return PlannedRecord(
        id=data.get("id"),
        record_id=str(data.get("record_id") or ""),
        incident_id=str(data.get("incident_id") or ""),
        tool=str(data.get("tool") or ""),
        title=str(data.get("title") or ""),
        summary=str(data.get("summary") or ""),
        status=str(data.get("status") or ""),
        priority=str(data.get("priority") or ""),
        assigned_to=str(data.get("assigned_to") or ""),
        assigned_team_id=str(data.get("assigned_team_id") or ""),
        assigned_person_id=str(data.get("assigned_person_id") or ""),
        location=str(data.get("location") or ""),
        zone=str(data.get("zone") or ""),
        scheduled_at=str(data.get("scheduled_at") or ""),
        due_at=str(data.get("due_at") or ""),
        recurring=bool(data.get("recurring", False)),
        recurrence_rule=str(data.get("recurrence_rule") or ""),
        recurrence_start_at=str(data.get("recurrence_start_at") or ""),
        recurrence_end_at=str(data.get("recurrence_end_at") or ""),
        missed_occurrence_behavior=str(data.get("missed_occurrence_behavior") or ""),
        template_id=str(data.get("template_id") or ""),
        generated_from_template_id=str(data.get("generated_from_template_id") or ""),
        lifecycle_state=str(data.get("lifecycle_state") or ""),
        active_at=str(data.get("active_at") or ""),
        triggered_at=str(data.get("triggered_at") or ""),
        source_type=str(data.get("source_type") or ""),
        source_id=str(data.get("source_id") or ""),
        source_label=str(data.get("source_label") or ""),
        source_tool=str(data.get("source_tool") or ""),
        linked_tasking_id=str(data.get("linked_tasking_id") or ""),
        promoted_at=str(data.get("promoted_at") or ""),
        promoted_by=str(data.get("promoted_by") or ""),
        promoted_read_only=bool(data.get("promoted_read_only", False)),
        metadata=dict(data.get("metadata") or {}),
        created_at=str(data.get("created_at") or ""),
        updated_at=str(data.get("updated_at") or ""),
    )


def schedule_from_dict(data: dict[str, Any]) -> ScheduledItem:
    return ScheduledItem(
        id=data.get("id"),
        record_id=str(data.get("record_id") or ""),
        incident_id=str(data.get("incident_id") or ""),
        name=str(data.get("name") or ""),
        kind=str(data.get("kind") or ""),
        starts_at=str(data.get("starts_at") or ""),
        ends_at=str(data.get("ends_at") or ""),
        location=str(data.get("location") or ""),
        zone=str(data.get("zone") or ""),
        owner=str(data.get("owner") or ""),
        status=str(data.get("status") or ""),
        tags=list(data.get("tags") or []),
        notes=str(data.get("notes") or ""),
        created_at=str(data.get("created_at") or ""),
        updated_at=str(data.get("updated_at") or ""),
    )


def trigger_from_dict(data: dict[str, Any]) -> ScheduleTrigger:
    return ScheduleTrigger(
        id=data.get("id"),
        trigger_id=str(data.get("trigger_id") or ""),
        incident_id=str(data.get("incident_id") or ""),
        schedule_item_id=str(data.get("schedule_item_id") or ""),
        trigger_type=str(data.get("trigger_type") or "notification"),
        label=str(data.get("label") or ""),
        offset_minutes=data.get("offset_minutes"),
        trigger_at=str(data.get("trigger_at") or ""),
        relative_to=str(data.get("relative_to") or "start"),
        enabled=bool(data.get("enabled", True)),
        audience_role=str(data.get("audience_role") or ""),
        audience_user_id=str(data.get("audience_user_id") or ""),
        notification_channel=str(data.get("notification_channel") or ""),
        requires_acknowledgement=bool(data.get("requires_acknowledgement", False)),
        message_template=str(data.get("message_template") or ""),
        link_to_schedule_item=bool(data.get("link_to_schedule_item", True)),
        quick_assignment_template_id=str(data.get("quick_assignment_template_id") or ""),
        title=str(data.get("title") or ""),
        summary=str(data.get("summary") or ""),
        assigned_to=str(data.get("assigned_to") or ""),
        assigned_team_id=str(data.get("assigned_team_id") or ""),
        assigned_person_id=str(data.get("assigned_person_id") or ""),
        location=str(data.get("location") or ""),
        zone=str(data.get("zone") or ""),
        priority=str(data.get("priority") or ""),
        recurring=bool(data.get("recurring", False)),
        recurrence_rule=str(data.get("recurrence_rule") or ""),
        missed_occurrence_behavior=str(data.get("missed_occurrence_behavior") or ""),
        created_at=str(data.get("created_at") or ""),
        updated_at=str(data.get("updated_at") or ""),
    )


def notification_from_dict(data: dict[str, Any]) -> PlannedNotification:
    return PlannedNotification(
        id=data.get("id"),
        notification_id=str(data.get("notification_id") or ""),
        incident_id=str(data.get("incident_id") or ""),
        title=str(data.get("title") or ""),
        message=str(data.get("message") or ""),
        severity=str(data.get("severity") or ""),
        audience_role=str(data.get("audience_role") or ""),
        audience_user_id=str(data.get("audience_user_id") or ""),
        notification_channel=str(data.get("notification_channel") or ""),
        location=str(data.get("location") or ""),
        zone=str(data.get("zone") or ""),
        scheduled_at=str(data.get("scheduled_at") or ""),
        triggered_at=str(data.get("triggered_at") or ""),
        acknowledged_at=str(data.get("acknowledged_at") or ""),
        acknowledged_by=str(data.get("acknowledged_by") or ""),
        dismissed_at=str(data.get("dismissed_at") or ""),
        source_type=str(data.get("source_type") or ""),
        source_id=str(data.get("source_id") or ""),
        source_label=str(data.get("source_label") or ""),
        created_at=str(data.get("created_at") or ""),
        updated_at=str(data.get("updated_at") or ""),
    )
