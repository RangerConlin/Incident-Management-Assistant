from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from utils import incident_storage

from .models import ICS230Schedule, Meeting, MeetingAttendee, StructuredNote, utcnow_iso
from .repository import MeetingsRepository


class MeetingsService:
    def __init__(self, repository: MeetingsRepository) -> None:
        self.repository = repository

    def create_meeting_from_template(
        self,
        template_slug: str,
        *,
        meeting_date: str,
        start_time: str,
        title: str | None = None,
        operational_period_id: str | None = None,
        location: str = "",
        virtual_link: str = "",
        owner: str = "",
        status: str = "scheduled",
    ) -> Meeting:
        template = self.repository.get_template(template_slug)
        start_dt = datetime.fromisoformat(f"{meeting_date}T{start_time}")
        end_time = (start_dt + timedelta(minutes=template.default_duration_minutes)).time().isoformat(timespec="minutes")
        meeting = self.repository.create_meeting(
            Meeting(
                incident_id=self.repository.incident_id,
                operational_period_id=operational_period_id,
                template_id=template.slug,
                title=title or template.name,
                meeting_date=meeting_date,
                start_time=start_time,
                end_time=end_time,
                location=location,
                virtual_link=virtual_link,
                owner=owner,
                status=status,
                show_on_ics230=template.appears_on_ics230_default,
            )
        )
        if meeting.id is None:
            raise RuntimeError("Meeting was created without an id")
        for role in template.required_attendee_roles:
            self.repository.add_attendee(
                MeetingAttendee(
                    meeting_id=meeting.id,
                    display_name=role,
                    role=role,
                    requirement_status="required",
                    attendance_status="invited",
                )
            )
        for role in template.optional_attendee_roles:
            self.repository.add_attendee(
                MeetingAttendee(
                    meeting_id=meeting.id,
                    display_name=role,
                    role=role,
                    requirement_status="optional",
                    attendance_status="invited",
                )
            )
        order = 0
        for group, items in (
            ("Prep", template.prep_checklist_items),
            ("Agenda/Content", template.agenda_checklist_items),
            ("Closeout", template.closeout_checklist_items),
        ):
            for text in items:
                order += 1
                from .models import ChecklistItem

                self.repository.add_checklist_item(
                    ChecklistItem(
                        meeting_id=meeting.id,
                        group_name=group,
                        text=text,
                        sort_order=order,
                    )
                )
        return self.repository.get_meeting(meeting.id)

    def add_structured_note(
        self,
        meeting_id: int,
        *,
        category: str,
        text: str,
        author: str = "",
        route_ready: bool = False,
    ) -> StructuredNote:
        status = "ready" if route_ready else "draft"
        note = self.repository.add_structured_note(
            StructuredNote(
                meeting_id=meeting_id,
                category=category,
                text=text,
                author=author,
                routing_status=status,
            )
        )
        if route_ready:
            self.repository.update_meeting(meeting_id, {"notes_log_routing_status": "ready"})
        return note

    def route_note_to_log(self, note_id: int, *, entered_by: str | int | None = None) -> StructuredNote:
        note = self.repository.route_note_to_planning_log(note_id, entered_by=entered_by)
        notes = self.repository.list_structured_notes(note.meeting_id)
        status = "routed" if all(n.routing_status == "routed" for n in notes) else "partial"
        self.repository.update_meeting(note.meeting_id, {"notes_log_routing_status": status})
        return note

    def generate_ics230(
        self,
        *,
        operational_period_id: str | None = None,
        prepared_by: str = "",
        incident_name: str | None = None,
    ) -> ICS230Schedule:
        meetings = self.repository.list_meetings(
            operational_period_id=operational_period_id,
            include_canceled=False,
            ics230_only=True,
        )
        rows: list[dict[str, Any]] = []
        for meeting in meetings:
            if meeting.id is None:
                continue
            attendees = self.repository.list_attendees(meeting.id)
            rows.append(
                {
                    "date": meeting.meeting_date,
                    "time": f"{meeting.start_time}-{meeting.end_time}",
                    "name": meeting.title,
                    "purpose": meeting.title,
                    "location": meeting.virtual_link or meeting.location,
                    "participants": ", ".join(a.display_name for a in attendees),
                    "status": meeting.status,
                    "meeting_id": meeting.id,
                }
            )
        return ICS230Schedule(
            incident_id=self.repository.incident_id,
            incident_name=incident_name or self._incident_display_name(),
            operational_period=operational_period_id,
            prepared_by=prepared_by,
            prepared_at=utcnow_iso(),
            meetings=rows,
        )

    def render_ics230_text(self, schedule: ICS230Schedule) -> str:
        lines = [
            "ICS-230 Meeting Schedule",
            f"Incident/Event: {schedule.incident_name}",
            f"Operational Period: {schedule.operational_period or ''}",
            f"Prepared By: {schedule.prepared_by}",
            f"Date/Time Prepared: {schedule.prepared_at}",
            "",
            "Date | Time | Meeting Name/Purpose | Location | Attendees/Participants",
        ]
        for row in schedule.meetings:
            lines.append(
                f"{row['date']} | {row['time']} | {row['name']} | {row['location']} | {row['participants']}"
            )
        return "\n".join(lines)

    def _incident_display_name(self) -> str:
        paths = incident_storage.resolve_incident_paths_by_identifier(self.repository.incident_id)
        if paths:
            manifest = incident_storage.read_incident_manifest(paths.manifest) or {}
            return str(manifest.get("name") or manifest.get("incident_number") or self.repository.incident_id)
        return self.repository.incident_id


__all__ = ["MeetingsService"]
