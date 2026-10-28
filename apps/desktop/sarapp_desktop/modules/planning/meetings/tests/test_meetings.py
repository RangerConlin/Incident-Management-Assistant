from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.planning.meetings.models import ChecklistItem, Meeting, MeetingAttendee, StructuredNote
from modules.planning.meetings.services import MeetingsService
from modules.planning.meetings.seeds import ICS_MEETING_TEMPLATES
from modules.planning.meetings.services import OP_TEMPLATE_SETS


class MemoryMeetingsRepository:
    def __init__(self) -> None:
        self.incident_id = "TEST-123"
        self.templates = {template.slug: template for template in ICS_MEETING_TEMPLATES}
        self.meetings: dict[int, Meeting] = {}
        self.attendees: list[MeetingAttendee] = []
        self.checklist: list[ChecklistItem] = []
        self.notes: list[StructuredNote] = []
        self.planning_logs: list[str] = []

    def list_templates(self):
        return list(self.templates.values())

    def get_template(self, slug: str):
        return self.templates[slug]

    def create_meeting(self, meeting: Meeting) -> Meeting:
        meeting.id = len(self.meetings) + 1
        self.meetings[meeting.id] = meeting
        return meeting

    def get_meeting(self, meeting_id: int) -> Meeting:
        return self.meetings[meeting_id]

    def update_meeting(self, meeting_id: int, patch: dict) -> Meeting:
        meeting = self.meetings[meeting_id]
        for key, value in patch.items():
            setattr(meeting, key, value)
        return meeting

    def list_meetings(self, *, operational_period_id=None, include_canceled=True, ics230_only=False):
        rows = list(self.meetings.values())
        if operational_period_id is not None:
            rows = [row for row in rows if row.operational_period_id == operational_period_id]
        if not include_canceled:
            rows = [row for row in rows if row.status != "canceled"]
        if ics230_only:
            rows = [row for row in rows if row.show_on_ics230]
        return rows

    def add_attendee(self, attendee: MeetingAttendee) -> MeetingAttendee:
        attendee.id = len(self.attendees) + 1
        self.attendees.append(attendee)
        return attendee

    def list_attendees(self, meeting_id: int):
        return [row for row in self.attendees if row.meeting_id == meeting_id]

    def add_checklist_item(self, item: ChecklistItem) -> ChecklistItem:
        item.id = len(self.checklist) + 1
        self.checklist.append(item)
        return item

    def list_checklist_items(self, meeting_id: int):
        return [row for row in self.checklist if row.meeting_id == meeting_id]

    def update_checklist_item(self, item_id: int, patch: dict) -> ChecklistItem:
        item = next(row for row in self.checklist if row.id == item_id)
        for key, value in patch.items():
            setattr(item, key, value)
        return item

    def checklist_progress(self, meeting_id: int):
        rows = [row for row in self.list_checklist_items(meeting_id) if not row.is_not_applicable]
        return sum(row.is_complete for row in rows), len(rows)

    def add_structured_note(self, note: StructuredNote) -> StructuredNote:
        note.id = len(self.notes) + 1
        self.notes.append(note)
        return note

    def list_structured_notes(self, meeting_id: int):
        return [row for row in self.notes if row.meeting_id == meeting_id]

    def route_note_to_planning_log_for_meeting(self, meeting_id: int, note_id: int, *, entered_by=None):
        note = next(row for row in self.notes if row.id == note_id and row.meeting_id == meeting_id)
        if note.routing_status != "routed":
            meeting = self.meetings[meeting_id]
            self.planning_logs.append(f"{meeting.title}: {note.text}")
            note.routing_status = "routed"
            note.routed_log_refs = [f"planning:{note.id}"]
        return note


def make_service(_tmp_path: Path) -> MeetingsService:
    return MeetingsService(MemoryMeetingsRepository())


def test_seed_templates_cover_ahimt_operational_period_set() -> None:
    template_names = {template.name for template in ICS_MEETING_TEMPLATES}
    assert {
        "Objectives Meeting",
        "Strategy Meeting",
        "Command and General Staff Meeting",
        "Planning Preparation Meeting",
        "Tactics Meeting",
        "Logistics Meeting",
        "Air Operations Branch Meeting",
        "Finance/Admin Meeting",
        "Planning Meeting",
        "Public Information Meeting",
        "Intel/Investigations Meeting",
        "IAP Preparation and Approval",
        "Operational Period Briefing",
        "Safety Briefing",
    } <= template_names


def test_create_operational_period_template_set_uses_seeded_schedule() -> None:
    service = MeetingsService(MagicMock())
    service.repository.list_templates.return_value = ICS_MEETING_TEMPLATES
    created_meetings = [object() for _ in OP_TEMPLATE_SETS["AHIMT Planning Cycle"]]
    service.create_meeting_from_template = MagicMock(side_effect=created_meetings)

    result = service.create_operational_period_template_set(
        entries=OP_TEMPLATE_SETS["AHIMT Planning Cycle"],
        operational_period_id=12,
        meeting_date="2026-06-10",
        anchor_time="07:00",
        location="ICP",
        owner="PSC",
    )

    assert result == created_meetings
    assert service.create_meeting_from_template.call_count == len(created_meetings)
    first_call = service.create_meeting_from_template.call_args_list[0]
    last_call = service.create_meeting_from_template.call_args_list[-1]
    assert first_call.args == ("objectives-meeting",)
    assert first_call.kwargs["operational_period_id"] == "12"
    assert first_call.kwargs["meeting_date"] == "2026-06-10"
    assert first_call.kwargs["start_time"] == "07:00"
    names = [call.args[0] for call in service.create_meeting_from_template.call_args_list]
    assert "air-operations-branch" in names
    assert last_call.kwargs["location"] == "ICP"
    assert last_call.kwargs["owner"] == "PSC"


def test_create_meeting_from_template_generates_attendees_and_checklist(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    meeting = service.create_meeting_from_template(
        "planning",
        meeting_date="2026-06-10",
        start_time="09:00",
        owner="PSC",
    )

    assert meeting.id is not None
    attendees = service.repository.list_attendees(meeting.id)
    checklist = service.repository.list_checklist_items(meeting.id)
    assert {a.role for a in attendees} >= {
        "Incident Commander",
        "Planning Section Chief",
        "Operations Section Chief",
    }
    assert {a.requirement_status for a in attendees} >= {"required", "optional"}
    assert {item.group_name for item in checklist} == {"Prep", "Agenda/Content", "Closeout"}
    assert service.repository.checklist_progress(meeting.id) == (0, len(checklist))


def test_checklist_completion_excludes_not_applicable_items(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    meeting = service.create_meeting_from_template("safety-briefing", meeting_date="2026-06-10", start_time="07:30")
    items = service.repository.list_checklist_items(meeting.id or 0)

    service.repository.update_checklist_item(items[0].id or 0, {"is_complete": True})
    service.repository.update_checklist_item(items[1].id or 0, {"is_not_applicable": True})

    assert service.repository.checklist_progress(meeting.id or 0) == (1, len(items) - 1)


def test_ics230_generation_selects_visible_scheduled_meetings(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    visible = service.create_meeting_from_template("tactics", meeting_date="2026-06-10", start_time="10:00")
    hidden = service.create_meeting_from_template("logistics", meeting_date="2026-06-10", start_time="11:00")
    canceled = service.create_meeting_from_template("finance-admin", meeting_date="2026-06-10", start_time="12:00")
    service.repository.update_meeting(hidden.id or 0, {"show_on_ics230": False})
    service.repository.update_meeting(canceled.id or 0, {"status": "canceled"})

    schedule = service.generate_ics230(prepared_by="Planning Section")

    assert [row["meeting_id"] for row in schedule.meetings] == [visible.id]
    assert schedule.prepared_by == "Planning Section"
    assert "Tactics Meeting" in service.render_ics230_text(schedule)


def test_structured_note_routing_is_idempotent_and_links_source(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    meeting = service.create_meeting_from_template("operations-briefing", meeting_date="2026-06-10", start_time="08:00")
    note = service.add_structured_note(
        meeting.id or 0,
        category="decision",
        text="Hold assignments until lightning clears.",
        author="OSC",
        route_ready=True,
    )

    routed = service.route_note_to_log(note.id or 0, meeting_id=meeting.id or 0, entered_by="OSC")
    routed_again = service.route_note_to_log(note.id or 0, meeting_id=meeting.id or 0, entered_by="OSC")

    assert routed.routing_status == "routed"
    assert routed.routed_log_refs == routed_again.routed_log_refs
    assert len(service.repository.planning_logs) == 1
    assert "Operational Period Briefing" in service.repository.planning_logs[0]
    assert "Hold assignments" in service.repository.planning_logs[0]
