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
        label="Tasking & Assignments",
        title_label="Task",
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
    location: str = ""
    scheduled_at: str = ""
    due_at: str = ""
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
    notes: str = ""
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
        location=str(data.get("location") or ""),
        scheduled_at=str(data.get("scheduled_at") or ""),
        due_at=str(data.get("due_at") or ""),
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
        notes=str(data.get("notes") or ""),
        created_at=str(data.get("created_at") or ""),
        updated_at=str(data.get("updated_at") or ""),
    )
