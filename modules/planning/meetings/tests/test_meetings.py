from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from modules.planning.meetings.repository import MeetingsRepository
from modules.planning.meetings.services import MeetingsService
from modules.planning.meetings.seeds import ICS_MEETING_TEMPLATES
from modules.planning.meetings.services import OP_TEMPLATE_SETS


def make_service(tmp_path: Path) -> MeetingsService:
    repo = MeetingsRepository(incident_id="TEST-123", db_path=tmp_path / "incident.db")
    return MeetingsService(repo)


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
        "AHIMT Planning Cycle",
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
    with sqlite3.connect(tmp_path / "incident.db") as conn:
        rows = conn.execute("SELECT text FROM planning_logs").fetchall()
    assert len(rows) == 1
    assert "Operational Period Briefing" in rows[0][0]
    assert "Hold assignments" in rows[0][0]
