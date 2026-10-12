from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


MEETING_STATUSES = {"draft", "scheduled", "ready", "completed", "canceled"}
NOTE_CATEGORIES = {
    "comment",
    "decision",
    "action item",
    "issue/risk",
    "resource request",
    "safety item",
    "assignment",
    "notable event",
    "follow-up",
}
CHECKLIST_GROUPS = ("Prep", "Agenda/Content", "Closeout")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class MeetingTemplate:
    name: str
    default_duration_minutes: int = 60
    agenda_sections: list[str] = field(default_factory=list)
    required_attendee_roles: list[str] = field(default_factory=list)
    optional_attendee_roles: list[str] = field(default_factory=list)
    prep_checklist_items: list[str] = field(default_factory=list)
    agenda_checklist_items: list[str] = field(default_factory=list)
    closeout_checklist_items: list[str] = field(default_factory=list)
    appears_on_ics230_default: bool = True
    slug: str = ""
    active: bool = True


@dataclass(slots=True)
class Meeting:
    title: str
    incident_id: str
    meeting_date: str
    start_time: str
    end_time: str
    template_id: str | None = None
    operational_period_id: str | None = None
    location: str = ""
    virtual_link: str = ""
    owner: str = ""
    status: str = "draft"
    show_on_ics230: bool = True
    freeform_notes: str = ""
    notes_log_routing_status: str = "not routed"
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    id: int | None = None


@dataclass(slots=True)
class MeetingAttendee:
    meeting_id: int
    attendee_name: str
    attendee_type: str = "role"
    role: str = ""
    requirement_status: str = "required"
    attendance_status: str = "invited"
    id: int | None = None


@dataclass(slots=True)
class ChecklistItem:
    meeting_id: int
    group_name: str
    text: str
    assigned_to: str = ""
    is_complete: bool = False
    is_not_applicable: bool = False
    sort_order: int = 0
    id: int | None = None


@dataclass(slots=True)
class StructuredNote:
    meeting_id: int
    category: str
    text: str
    author: str = ""
    timestamp: str = field(default_factory=utcnow_iso)
    routing_status: str = "draft"
    routed_log_refs: list[str] = field(default_factory=list)
    routed_at: str | None = None
    id: int | None = None


@dataclass(slots=True)
class MeetingDetail:
    meeting: Meeting
    attendees: list[MeetingAttendee]
    checklist: list[ChecklistItem]
    notes: list[StructuredNote]


@dataclass(slots=True)
class ICS230Schedule:
    incident_id: str
    incident_name: str
    operational_period: str | None
    prepared_by: str
    prepared_at: str
    meetings: list[dict[str, Any]]


__all__ = [
    "CHECKLIST_GROUPS",
    "MEETING_STATUSES",
    "NOTE_CATEGORIES",
    "ChecklistItem",
    "ICS230Schedule",
    "Meeting",
    "MeetingAttendee",
    "MeetingDetail",
    "MeetingTemplate",
    "StructuredNote",
    "utcnow_iso",
]
