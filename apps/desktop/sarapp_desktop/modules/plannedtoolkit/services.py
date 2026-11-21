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
    schedule_item_id: str | None = None,
) -> list[PlannedRecord]:
    return PlannedToolkitRepository(incident_id).list_records(
        tool, status=status, search=search, schedule_item_id=schedule_item_id
    )


def create_record(
    tool: str,
    incident_id: str | None = None,
    *,
    title: str,
    summary: str = "",
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str = "",
    assigned_team_id: str = "",
    assigned_person_id: str = "",
    location: str = "",
    scheduled_at: str = "",
    due_at: str = "",
    metadata: dict[str, Any] | None = None,
    **extra: Any,
) -> PlannedRecord:
    return PlannedToolkitRepository(incident_id).create_record(
        tool,
        title=title,
        summary=summary,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        assigned_team_id=assigned_team_id,
        assigned_person_id=assigned_person_id,
        location=location,
        scheduled_at=scheduled_at,
        due_at=due_at,
        metadata=metadata,
        **extra,
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
    time_zone: str = "",
    notes: str = "",
    location: str = "",
    zone: str = "",
    owner: str = "",
    assigned_to: str = "",
    assigned_team_id: str = "",
    assigned_person_id: str = "",
    meeting_id: str = "",
    gis_feature_id: str = "",
    quick_assignment_id: str = "",
    status: str = "",
):
    return PlannedToolkitRepository(incident_id).create_schedule_item(
        name=name,
        kind=kind,
        starts_at=starts_at,
        ends_at=ends_at,
        time_zone=time_zone,
        notes=notes,
        location=location,
        zone=zone,
        owner=owner,
        assigned_to=assigned_to,
        assigned_team_id=assigned_team_id,
        assigned_person_id=assigned_person_id,
        meeting_id=meeting_id,
        gis_feature_id=gis_feature_id,
        quick_assignment_id=quick_assignment_id,
        status=status,
    )


def update_schedule_item(record_id: int, patch: dict[str, Any], incident_id: str | None = None):
    return PlannedToolkitRepository(incident_id).update_schedule_item(record_id, patch)


def delete_schedule_item(record_id: int, incident_id: str | None = None) -> None:
    PlannedToolkitRepository(incident_id).delete_schedule_item(record_id)


def create_quick_assignment_from_schedule_item(record_id: int, incident_id: str | None = None) -> dict[str, Any]:
    return PlannedToolkitRepository(incident_id).create_quick_assignment_from_schedule_item(record_id)


def start_schedule_item(
    record_id: int, incident_id: str | None = None, *, actual_start_at: str | None = None, expected_revision: int | None = None
):
    return PlannedToolkitRepository(incident_id).start_schedule_item(
        record_id, actual_start_at=actual_start_at, expected_revision=expected_revision
    )


def resume_schedule_item(
    record_id: int, incident_id: str | None = None, *, actual_start_at: str | None = None, expected_revision: int | None = None
):
    return PlannedToolkitRepository(incident_id).resume_schedule_item(
        record_id, actual_start_at=actual_start_at, expected_revision=expected_revision
    )


def complete_schedule_item(
    record_id: int, incident_id: str | None = None, *, actual_end_at: str | None = None, expected_revision: int | None = None
):
    return PlannedToolkitRepository(incident_id).complete_schedule_item(
        record_id, actual_end_at=actual_end_at, expected_revision=expected_revision
    )


def delay_schedule_item(
    record_id: int,
    incident_id: str | None = None,
    *,
    delay_reason: str,
    revised_start_at: str | None = None,
    expected_revision: int | None = None,
):
    return PlannedToolkitRepository(incident_id).delay_schedule_item(
        record_id, delay_reason=delay_reason, revised_start_at=revised_start_at, expected_revision=expected_revision
    )


def cancel_schedule_item(
    record_id: int, incident_id: str | None = None, *, cancellation_reason: str, expected_revision: int | None = None
):
    return PlannedToolkitRepository(incident_id).cancel_schedule_item(
        record_id, cancellation_reason=cancellation_reason, expected_revision=expected_revision
    )


def correct_schedule_item(
    record_id: int,
    incident_id: str | None = None,
    *,
    reason: str,
    status: str | None = None,
    actual_start_at: str | None = None,
    actual_end_at: str | None = None,
    expected_revision: int | None = None,
):
    return PlannedToolkitRepository(incident_id).correct_schedule_item(
        record_id, reason=reason, status=status, actual_start_at=actual_start_at,
        actual_end_at=actual_end_at, expected_revision=expected_revision,
    )


def list_schedule_triggers(incident_id: str | None = None, schedule_item_id: str | None = None):
    return PlannedToolkitRepository(incident_id).list_schedule_triggers(schedule_item_id)


def create_schedule_trigger(incident_id: str | None = None, **payload: Any):
    return PlannedToolkitRepository(incident_id).create_schedule_trigger(**payload)


def update_schedule_trigger(
    record_id: int,
    patch: dict[str, Any],
    incident_id: str | None = None,
):
    return PlannedToolkitRepository(incident_id).update_schedule_trigger(record_id, patch)


def delete_schedule_trigger(record_id: int, incident_id: str | None = None) -> None:
    PlannedToolkitRepository(incident_id).delete_schedule_trigger(record_id)


def promote_quick_assignment(
    record_id: int,
    incident_id: str | None = None,
    *,
    promoted_by: str = "",
):
    return PlannedToolkitRepository(incident_id).promote_quick_assignment(
        record_id,
        promoted_by=promoted_by,
    )
