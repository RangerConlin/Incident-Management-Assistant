from __future__ import annotations

from typing import Any

from .records import PlannedRecord
from .repository import PlannedToolkitRepository


def list_records(
    tool: str,
    incident_id: str | None = None,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[PlannedRecord]:
    return PlannedToolkitRepository(incident_id).list_records(tool, status=status, search=search)


def create_record(
    tool: str,
    incident_id: str | None = None,
    *,
    title: str,
    summary: str = "",
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str = "",
    location: str = "",
    scheduled_at: str = "",
    due_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> PlannedRecord:
    return PlannedToolkitRepository(incident_id).create_record(
        tool,
        title=title,
        summary=summary,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        location=location,
        scheduled_at=scheduled_at,
        due_at=due_at,
        metadata=metadata,
    )


def update_record(
    tool: str,
    record_id: int,
    patch: dict[str, Any],
    incident_id: str | None = None,
) -> PlannedRecord:
    return PlannedToolkitRepository(incident_id).update_record(tool, record_id, patch)


def delete_record(tool: str, record_id: int, incident_id: str | None = None) -> None:
    PlannedToolkitRepository(incident_id).delete_record(tool, record_id)


def list_schedule_items(incident_id: str | None = None):
    return PlannedToolkitRepository(incident_id).list_schedule_items()


def create_schedule_item(
    incident_id: str | None = None,
    *,
    name: str,
    kind: str = "Milestone",
    starts_at: str = "",
    ends_at: str = "",
    notes: str = "",
):
    return PlannedToolkitRepository(incident_id).create_schedule_item(
        name=name,
        kind=kind,
        starts_at=starts_at,
        ends_at=ends_at,
        notes=notes,
    )
