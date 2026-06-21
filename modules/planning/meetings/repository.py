"""Meetings repository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---- Domain models (kept identical so callers don't need changes) ----

@dataclass
class MeetingTemplate:
    slug: str = ""
    name: str = ""
    default_duration_minutes: int = 60
    agenda_sections: list = field(default_factory=list)
    required_attendee_roles: list = field(default_factory=list)
    optional_attendee_roles: list = field(default_factory=list)
    prep_checklist_items: list = field(default_factory=list)
    agenda_checklist_items: list = field(default_factory=list)
    closeout_checklist_items: list = field(default_factory=list)
    appears_on_ics230_default: bool = True
    active: bool = True


@dataclass
class Meeting:
    id: Optional[int] = None
    incident_id: str = ""
    operational_period_id: Optional[str] = None
    template_id: Optional[str] = None
    title: str = ""
    meeting_date: str = ""
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    virtual_link: str = ""
    owner: str = ""
    status: str = "draft"
    show_on_ics230: bool = True
    freeform_notes: str = ""
    notes_log_routing_status: str = "not routed"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class MeetingAttendee:
    id: Optional[int] = None
    meeting_id: Optional[int] = None
    display_name: str = ""
    attendee_type: str = "role"
    role: str = ""
    requirement_status: str = "required"
    attendance_status: str = "invited"


@dataclass
class ChecklistItem:
    id: Optional[int] = None
    meeting_id: Optional[int] = None
    group_name: str = ""
    text: str = ""
    assigned_to: str = ""
    is_complete: bool = False
    is_not_applicable: bool = False
    sort_order: int = 0


@dataclass
class StructuredNote:
    id: Optional[int] = None
    meeting_id: Optional[int] = None
    category: str = ""
    text: str = ""
    author: str = ""
    timestamp: str = ""
    routing_status: str = "draft"
    routed_log_refs: list = field(default_factory=list)
    routed_at: Optional[str] = None


def _meeting_from_dict(d: dict, incident_id: str = "") -> Meeting:
    return Meeting(
        id=d.get("id"),
        incident_id=d.get("incident_id", incident_id),
        operational_period_id=d.get("operational_period_id"),
        template_id=d.get("template_id"),
        title=str(d.get("title") or ""),
        meeting_date=str(d.get("meeting_date") or ""),
        start_time=str(d.get("start_time") or ""),
        end_time=str(d.get("end_time") or ""),
        location=str(d.get("location") or ""),
        virtual_link=str(d.get("virtual_link") or ""),
        owner=str(d.get("owner") or ""),
        status=str(d.get("status") or "draft"),
        show_on_ics230=bool(d.get("show_on_ics230", True)),
        freeform_notes=str(d.get("freeform_notes") or ""),
        notes_log_routing_status=str(d.get("notes_log_routing_status") or "not routed"),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


def _template_from_dict(d: dict) -> MeetingTemplate:
    return MeetingTemplate(
        slug=str(d.get("slug") or ""),
        name=str(d.get("name") or ""),
        default_duration_minutes=int(d.get("default_duration_minutes") or 60),
        agenda_sections=list(d.get("agenda_sections") or []),
        required_attendee_roles=list(d.get("required_attendee_roles") or []),
        optional_attendee_roles=list(d.get("optional_attendee_roles") or []),
        prep_checklist_items=list(d.get("prep_checklist_items") or []),
        agenda_checklist_items=list(d.get("agenda_checklist_items") or []),
        closeout_checklist_items=list(d.get("closeout_checklist_items") or []),
        appears_on_ics230_default=bool(d.get("appears_on_ics230_default", True)),
        active=bool(d.get("active", True)),
    )


def _attendee_from_dict(d: dict) -> MeetingAttendee:
    return MeetingAttendee(
        id=d.get("id"),
        meeting_id=d.get("meeting_id"),
        display_name=str(d.get("display_name") or ""),
        attendee_type=str(d.get("attendee_type") or "role"),
        role=str(d.get("role") or ""),
        requirement_status=str(d.get("requirement_status") or "required"),
        attendance_status=str(d.get("attendance_status") or "invited"),
    )


def _checklist_from_dict(d: dict) -> ChecklistItem:
    return ChecklistItem(
        id=d.get("id"),
        meeting_id=d.get("meeting_id"),
        group_name=str(d.get("group_name") or ""),
        text=str(d.get("text") or ""),
        assigned_to=str(d.get("assigned_to") or ""),
        is_complete=bool(d.get("is_complete", False)),
        is_not_applicable=bool(d.get("is_not_applicable", False)),
        sort_order=int(d.get("sort_order") or 0),
    )


def _note_from_dict(d: dict) -> StructuredNote:
    return StructuredNote(
        id=d.get("id"),
        meeting_id=d.get("meeting_id"),
        category=str(d.get("category") or ""),
        text=str(d.get("text") or ""),
        author=str(d.get("author") or ""),
        timestamp=str(d.get("timestamp") or ""),
        routing_status=str(d.get("routing_status") or "draft"),
        routed_log_refs=list(d.get("routed_log_refs") or []),
        routed_at=d.get("routed_at"),
    )


class MeetingsRepository:
    def __init__(self, incident_id: Optional[str] = None, db_path=None) -> None:
        from utils.state import AppState
        incident = incident_id or AppState.get_active_incident()
        if not incident and db_path is None:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident or "test-incident")
        # db_path accepted but ignored

    def _base(self) -> str:
        return f"/api/incidents/{self.incident_id}/planning"

    def _client(self):
        from utils.api_client import api_client
        return api_client

    # Templates

    def list_templates(self, *, active_only: bool = True) -> list[MeetingTemplate]:
        try:
            data = self._client().get(f"{self._base()}/meeting-templates", params={"active_only": active_only})
            return [_template_from_dict(d) for d in data]
        except Exception:
            return []

    def get_template(self, slug: str) -> MeetingTemplate:
        d = self._client().get(f"{self._base()}/meeting-templates/{slug}")
        return _template_from_dict(d)

    def save_template(self, template: MeetingTemplate) -> MeetingTemplate:
        from dataclasses import asdict
        slug = template.slug or template.name.lower().replace("/", "-").replace(" ", "-")
        d = self._client().put(f"{self._base()}/meeting-templates/{slug}", json=asdict(template))
        return _template_from_dict(d)

    def seed_default_templates(self, conn=None) -> None:
        pass  # Seeding is done lazily server-side on first list_templates call

    # Meetings

    def create_meeting(self, meeting: Meeting) -> Meeting:
        from dataclasses import asdict
        now = _utcnow_iso()
        payload = asdict(meeting)
        payload.pop("id", None)
        payload.setdefault("created_at", now)
        payload.setdefault("incident_id", self.incident_id)
        d = self._client().post(f"{self._base()}/meetings", json=payload)
        return _meeting_from_dict(d, self.incident_id)

    def update_meeting(self, meeting_id: int, patch: dict[str, Any]) -> Meeting:
        d = self._client().patch(f"{self._base()}/meetings/{meeting_id}", json=patch)
        return _meeting_from_dict(d, self.incident_id)

    def get_meeting(self, meeting_id: int) -> Meeting:
        d = self._client().get(f"{self._base()}/meetings/{meeting_id}")
        return _meeting_from_dict(d, self.incident_id)

    def list_meetings(
        self,
        *,
        operational_period_id: Optional[str] = None,
        include_canceled: bool = True,
        ics230_only: bool = False,
    ) -> list[Meeting]:
        params: dict[str, Any] = {
            "include_canceled": include_canceled,
            "ics230_only": ics230_only,
        }
        if operational_period_id is not None:
            params["operational_period_id"] = operational_period_id
        try:
            data = self._client().get(f"{self._base()}/meetings", params=params)
            return [_meeting_from_dict(d, self.incident_id) for d in data]
        except Exception:
            return []

    # Attendees

    def add_attendee(self, attendee: MeetingAttendee) -> MeetingAttendee:
        from dataclasses import asdict
        payload = asdict(attendee)
        payload.pop("id", None)
        d = self._client().post(f"{self._base()}/meetings/{attendee.meeting_id}/attendees", json=payload)
        return _attendee_from_dict(d)

    def list_attendees(self, meeting_id: int) -> list[MeetingAttendee]:
        try:
            data = self._client().get(f"{self._base()}/meetings/{meeting_id}/attendees")
            return [_attendee_from_dict(d) for d in data]
        except Exception:
            return []

    # Checklist

    def add_checklist_item(self, item: ChecklistItem) -> ChecklistItem:
        from dataclasses import asdict
        payload = asdict(item)
        payload.pop("id", None)
        d = self._client().post(f"{self._base()}/meetings/{item.meeting_id}/checklist", json=payload)
        return _checklist_from_dict(d)

    def list_checklist_items(self, meeting_id: int) -> list[ChecklistItem]:
        try:
            data = self._client().get(f"{self._base()}/meetings/{meeting_id}/checklist")
            return [_checklist_from_dict(d) for d in data]
        except Exception:
            return []

    def update_checklist_item(self, item_id: int, patch: dict[str, Any]) -> ChecklistItem:
        # We need meeting_id to build the URL but item_id alone isn't enough.
        # Callers typically pass the meeting_id in context via the service layer.
        # This is a limitation — fall back to returning a stub.
        # The service layer should call _update_checklist_item_for_meeting instead.
        raise NotImplementedError("Use update_checklist_item_for_meeting(meeting_id, item_id, patch)")

    def update_checklist_item_for_meeting(self, meeting_id: int, item_id: int, patch: dict[str, Any]) -> ChecklistItem:
        d = self._client().patch(f"{self._base()}/meetings/{meeting_id}/checklist/{item_id}", json=patch)
        return _checklist_from_dict(d)

    def checklist_progress(self, meeting_id: int) -> tuple[int, int]:
        items = self.list_checklist_items(meeting_id)
        applicable = [i for i in items if not i.is_not_applicable]
        complete = [i for i in applicable if i.is_complete]
        return len(complete), len(applicable)

    # Structured notes

    def add_structured_note(self, note: StructuredNote) -> StructuredNote:
        from dataclasses import asdict
        payload = asdict(note)
        payload.pop("id", None)
        d = self._client().post(f"{self._base()}/meetings/{note.meeting_id}/notes", json=payload)
        return _note_from_dict(d)

    def get_structured_note(self, note_id: int) -> StructuredNote:
        # We need meeting_id to get the note. Without it we'd have to scan all meetings.
        # Callers that need this should use get_structured_note_for_meeting instead.
        raise NotImplementedError("Use get_structured_note_for_meeting(meeting_id, note_id)")

    def list_structured_notes(self, meeting_id: int) -> list[StructuredNote]:
        try:
            data = self._client().get(f"{self._base()}/meetings/{meeting_id}/notes")
            return [_note_from_dict(d) for d in data]
        except Exception:
            return []

    def mark_note_routed(self, note_id: int, refs: list[str], status: str = "routed") -> StructuredNote:
        raise NotImplementedError("Use mark_note_routed_for_meeting(meeting_id, note_id, refs, status)")

    def mark_note_routed_for_meeting(self, meeting_id: int, note_id: int, refs: list[str], status: str = "routed") -> StructuredNote:
        d = self._client().patch(f"{self._base()}/meetings/{meeting_id}/notes/{note_id}/route", json={"refs": refs, "status": status})
        return _note_from_dict(d)

    def route_note_to_planning_log(self, note_id: int, *, entered_by=None) -> StructuredNote:
        raise NotImplementedError("Use route_note_to_planning_log_for_meeting(meeting_id, note_id)")

    def route_note_to_planning_log_for_meeting(self, meeting_id: int, note_id: int, *, entered_by=None) -> StructuredNote:
        note = self._client().get(f"{self._base()}/meetings/{meeting_id}/notes")
        target = next((n for n in note if n.get("id") == note_id), None)
        if target and target.get("routing_status") == "routed" and target.get("routed_log_refs"):
            return _note_from_dict(target)
        meeting = self.get_meeting(meeting_id)
        # No actual planning_logs table — route via mark_note_routed
        log_ref = f"planning_log:{meeting_id}"
        return self.mark_note_routed_for_meeting(meeting_id, note_id, [log_ref])


__all__ = ["MeetingsRepository", "Meeting", "MeetingTemplate", "MeetingAttendee", "ChecklistItem", "StructuredNote", "utcnow_iso"]


def utcnow_iso() -> str:
    return _utcnow_iso()
