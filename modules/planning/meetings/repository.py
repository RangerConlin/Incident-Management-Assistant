from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from utils import incident_storage
from utils.state import AppState

from .models import ChecklistItem, Meeting, MeetingAttendee, MeetingTemplate, StructuredNote, utcnow_iso
from .seeds import ICS_MEETING_TEMPLATES


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _incident_db_path(incident_id: str) -> Path:
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        meta = incident_storage.infer_incident_metadata(incident_id)
        paths = incident_storage.get_incident_paths(
            incident_number=meta.get("incident_number") or incident_id,
            incident_name=meta.get("name") or incident_id,
            incident_id=meta.get("incident_id") or incident_id,
        )
        incident_storage.ensure_incident_structure(paths, meta)
    return paths.incident_db


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 4000")
    return conn


class MeetingsRepository:
    def __init__(self, incident_id: str | None = None, db_path: Path | None = None) -> None:
        incident = incident_id or AppState.get_active_incident()
        if not incident and db_path is None:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident or "test-incident")
        self._path = Path(db_path) if db_path else _incident_db_path(self.incident_id)
        with _connect(self._path) as conn:
            self._ensure_schema(conn)
            self.seed_default_templates(conn)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meeting_templates (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                default_duration_minutes INTEGER NOT NULL DEFAULT 60,
                agenda_sections_json TEXT NOT NULL DEFAULT '[]',
                required_attendee_roles_json TEXT NOT NULL DEFAULT '[]',
                optional_attendee_roles_json TEXT NOT NULL DEFAULT '[]',
                prep_checklist_json TEXT NOT NULL DEFAULT '[]',
                agenda_checklist_json TEXT NOT NULL DEFAULT '[]',
                closeout_checklist_json TEXT NOT NULL DEFAULT '[]',
                appears_on_ics230_default INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY,
                incident_id TEXT NOT NULL,
                operational_period_id TEXT,
                template_id TEXT,
                title TEXT NOT NULL,
                meeting_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT,
                virtual_link TEXT,
                owner TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                show_on_ics230 INTEGER NOT NULL DEFAULT 1,
                freeform_notes TEXT,
                notes_log_routing_status TEXT NOT NULL DEFAULT 'not routed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meeting_attendees (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                attendee_type TEXT NOT NULL DEFAULT 'role',
                role TEXT,
                requirement_status TEXT NOT NULL DEFAULT 'required',
                attendance_status TEXT NOT NULL DEFAULT 'invited',
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS meeting_checklist_items (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                text TEXT NOT NULL,
                assigned_to TEXT,
                is_complete INTEGER NOT NULL DEFAULT 0,
                is_not_applicable INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS meeting_structured_notes (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                text TEXT NOT NULL,
                author TEXT,
                timestamp TEXT NOT NULL,
                routing_status TEXT NOT NULL DEFAULT 'draft',
                routed_log_refs_json TEXT NOT NULL DEFAULT '[]',
                routed_at TEXT,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_meetings_incident_date ON meetings(incident_id, meeting_date, start_time);
            CREATE INDEX IF NOT EXISTS idx_meeting_notes_routing ON meeting_structured_notes(routing_status);
            """
        )
        conn.commit()

    def seed_default_templates(self, conn: sqlite3.Connection | None = None) -> None:
        owns_conn = conn is None
        conn = conn or _connect(self._path)
        try:
            for template in ICS_MEETING_TEMPLATES:
                self._upsert_template(conn, template)
            conn.commit()
        finally:
            if owns_conn:
                conn.close()

    def _upsert_template(self, conn: sqlite3.Connection, template: MeetingTemplate) -> None:
        conn.execute(
            """
            INSERT INTO meeting_templates (
                slug, name, default_duration_minutes, agenda_sections_json,
                required_attendee_roles_json, optional_attendee_roles_json,
                prep_checklist_json, agenda_checklist_json, closeout_checklist_json,
                appears_on_ics230_default, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                default_duration_minutes=excluded.default_duration_minutes,
                agenda_sections_json=excluded.agenda_sections_json,
                required_attendee_roles_json=excluded.required_attendee_roles_json,
                optional_attendee_roles_json=excluded.optional_attendee_roles_json,
                prep_checklist_json=excluded.prep_checklist_json,
                agenda_checklist_json=excluded.agenda_checklist_json,
                closeout_checklist_json=excluded.closeout_checklist_json,
                appears_on_ics230_default=excluded.appears_on_ics230_default,
                active=excluded.active
            """,
            (
                template.slug,
                template.name,
                int(template.default_duration_minutes),
                json.dumps(template.agenda_sections),
                json.dumps(template.required_attendee_roles),
                json.dumps(template.optional_attendee_roles),
                json.dumps(template.prep_checklist_items),
                json.dumps(template.agenda_checklist_items),
                json.dumps(template.closeout_checklist_items),
                1 if template.appears_on_ics230_default else 0,
                1 if template.active else 0,
            ),
        )

    def list_templates(self, *, active_only: bool = True) -> list[MeetingTemplate]:
        sql = "SELECT * FROM meeting_templates"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY name COLLATE NOCASE"
        with _connect(self._path) as conn:
            rows = conn.execute(sql).fetchall()
        return [self._template_from_row(row) for row in rows]

    def get_template(self, slug: str) -> MeetingTemplate:
        with _connect(self._path) as conn:
            row = conn.execute("SELECT * FROM meeting_templates WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise ValueError(f"Meeting template not found: {slug}")
        return self._template_from_row(row)

    def save_template(self, template: MeetingTemplate) -> MeetingTemplate:
        if not template.slug:
            template.slug = template.name.lower().replace("/", "-").replace(" ", "-")
        with _connect(self._path) as conn:
            self._upsert_template(conn, template)
            conn.commit()
        return self.get_template(template.slug)

    def create_meeting(self, meeting: Meeting) -> Meeting:
        now = utcnow_iso()
        meeting.created_at = meeting.created_at or now
        meeting.updated_at = now
        payload = asdict(meeting)
        payload.pop("id", None)
        payload["show_on_ics230"] = 1 if meeting.show_on_ics230 else 0
        columns = ",".join(payload.keys())
        placeholders = ",".join(["?"] * len(payload))
        with _connect(self._path) as conn:
            cur = conn.execute(
                f"INSERT INTO meetings ({columns}) VALUES ({placeholders})",
                [payload[k] for k in payload.keys()],
            )
            conn.commit()
            meeting.id = int(cur.lastrowid)
        return self.get_meeting(meeting.id)

    def update_meeting(self, meeting_id: int, patch: dict[str, Any]) -> Meeting:
        if not patch:
            return self.get_meeting(meeting_id)
        normalized = dict(patch)
        if "show_on_ics230" in normalized:
            normalized["show_on_ics230"] = 1 if normalized["show_on_ics230"] else 0
        normalized["updated_at"] = utcnow_iso()
        assignments = ",".join([f"{key}=?" for key in normalized.keys()])
        values = list(normalized.values()) + [int(meeting_id)]
        with _connect(self._path) as conn:
            conn.execute(f"UPDATE meetings SET {assignments} WHERE id=?", values)
            conn.commit()
        return self.get_meeting(meeting_id)

    def get_meeting(self, meeting_id: int) -> Meeting:
        with _connect(self._path) as conn:
            row = conn.execute("SELECT * FROM meetings WHERE id=?", (int(meeting_id),)).fetchone()
        if not row:
            raise ValueError(f"Meeting not found: {meeting_id}")
        return self._meeting_from_row(row)

    def list_meetings(
        self,
        *,
        operational_period_id: str | None = None,
        include_canceled: bool = True,
        ics230_only: bool = False,
    ) -> list[Meeting]:
        clauses = ["incident_id = ?"]
        params: list[Any] = [self.incident_id]
        if operational_period_id is not None:
            clauses.append("operational_period_id = ?")
            params.append(operational_period_id)
        if not include_canceled:
            clauses.append("status <> 'canceled'")
        if ics230_only:
            clauses.append("show_on_ics230 = 1")
            clauses.append("status IN ('scheduled', 'ready', 'completed')")
        sql = "SELECT * FROM meetings WHERE " + " AND ".join(clauses)
        sql += " ORDER BY meeting_date, start_time, title COLLATE NOCASE"
        with _connect(self._path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._meeting_from_row(row) for row in rows]

    def add_attendee(self, attendee: MeetingAttendee) -> MeetingAttendee:
        payload = asdict(attendee)
        payload.pop("id", None)
        with _connect(self._path) as conn:
            cur = conn.execute(
                """
                INSERT INTO meeting_attendees
                    (meeting_id, display_name, attendee_type, role, requirement_status, attendance_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attendee.meeting_id,
                    attendee.display_name,
                    attendee.attendee_type,
                    attendee.role,
                    attendee.requirement_status,
                    attendee.attendance_status,
                ),
            )
            conn.commit()
            attendee.id = int(cur.lastrowid)
        return attendee

    def list_attendees(self, meeting_id: int) -> list[MeetingAttendee]:
        with _connect(self._path) as conn:
            rows = conn.execute(
                "SELECT * FROM meeting_attendees WHERE meeting_id=? ORDER BY requirement_status DESC, display_name",
                (int(meeting_id),),
            ).fetchall()
        return [self._attendee_from_row(row) for row in rows]

    def add_checklist_item(self, item: ChecklistItem) -> ChecklistItem:
        with _connect(self._path) as conn:
            cur = conn.execute(
                """
                INSERT INTO meeting_checklist_items
                    (meeting_id, group_name, text, assigned_to, is_complete, is_not_applicable, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.meeting_id,
                    item.group_name,
                    item.text,
                    item.assigned_to,
                    1 if item.is_complete else 0,
                    1 if item.is_not_applicable else 0,
                    item.sort_order,
                ),
            )
            conn.commit()
            item.id = int(cur.lastrowid)
        return item

    def list_checklist_items(self, meeting_id: int) -> list[ChecklistItem]:
        with _connect(self._path) as conn:
            rows = conn.execute(
                "SELECT * FROM meeting_checklist_items WHERE meeting_id=? ORDER BY group_name, sort_order, id",
                (int(meeting_id),),
            ).fetchall()
        return [self._checklist_from_row(row) for row in rows]

    def update_checklist_item(self, item_id: int, patch: dict[str, Any]) -> ChecklistItem:
        normalized = dict(patch)
        for key in ("is_complete", "is_not_applicable"):
            if key in normalized:
                normalized[key] = 1 if normalized[key] else 0
        assignments = ",".join([f"{key}=?" for key in normalized.keys()])
        values = list(normalized.values()) + [int(item_id)]
        with _connect(self._path) as conn:
            conn.execute(f"UPDATE meeting_checklist_items SET {assignments} WHERE id=?", values)
            row = conn.execute("SELECT * FROM meeting_checklist_items WHERE id=?", (int(item_id),)).fetchone()
            conn.commit()
        if not row:
            raise ValueError(f"Checklist item not found: {item_id}")
        return self._checklist_from_row(row)

    def add_structured_note(self, note: StructuredNote) -> StructuredNote:
        with _connect(self._path) as conn:
            cur = conn.execute(
                """
                INSERT INTO meeting_structured_notes
                    (meeting_id, category, text, author, timestamp, routing_status, routed_log_refs_json, routed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.meeting_id,
                    note.category,
                    note.text,
                    note.author,
                    note.timestamp,
                    note.routing_status,
                    json.dumps(note.routed_log_refs),
                    note.routed_at,
                ),
            )
            conn.commit()
            note.id = int(cur.lastrowid)
        return self.get_structured_note(note.id)

    def get_structured_note(self, note_id: int) -> StructuredNote:
        with _connect(self._path) as conn:
            row = conn.execute("SELECT * FROM meeting_structured_notes WHERE id=?", (int(note_id),)).fetchone()
        if not row:
            raise ValueError(f"Structured note not found: {note_id}")
        return self._note_from_row(row)

    def list_structured_notes(self, meeting_id: int) -> list[StructuredNote]:
        with _connect(self._path) as conn:
            rows = conn.execute(
                "SELECT * FROM meeting_structured_notes WHERE meeting_id=? ORDER BY timestamp, id",
                (int(meeting_id),),
            ).fetchall()
        return [self._note_from_row(row) for row in rows]

    def mark_note_routed(self, note_id: int, refs: list[str], status: str = "routed") -> StructuredNote:
        routed_at = utcnow_iso()
        with _connect(self._path) as conn:
            conn.execute(
                """
                UPDATE meeting_structured_notes
                SET routing_status=?, routed_log_refs_json=?, routed_at=?
                WHERE id=?
                """,
                (status, json.dumps(refs), routed_at, int(note_id)),
            )
            conn.commit()
        return self.get_structured_note(note_id)

    def route_note_to_planning_log(self, note_id: int, *, entered_by: str | int | None = None) -> StructuredNote:
        note = self.get_structured_note(note_id)
        if note.routing_status == "routed" and note.routed_log_refs:
            return note
        meeting = self.get_meeting(note.meeting_id)
        text = f"[Meeting: {meeting.title}] {note.category}: {note.text}"
        with _connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS planning_logs (
                    id INTEGER PRIMARY KEY,
                    incident_id TEXT,
                    text TEXT,
                    timestamp TEXT,
                    entered_by TEXT
                )
                """
            )
            cur = conn.execute(
                "INSERT INTO planning_logs (incident_id, text, timestamp, entered_by) VALUES (?, ?, ?, ?)",
                (self.incident_id, text, note.timestamp, entered_by or note.author or ""),
            )
            log_id = int(cur.lastrowid)
            conn.commit()
        return self.mark_note_routed(note_id, [f"planning_logs:{log_id}"])

    def checklist_progress(self, meeting_id: int) -> tuple[int, int]:
        items = self.list_checklist_items(meeting_id)
        applicable = [item for item in items if not item.is_not_applicable]
        complete = [item for item in applicable if item.is_complete]
        return len(complete), len(applicable)

    def _template_from_row(self, row: sqlite3.Row) -> MeetingTemplate:
        return MeetingTemplate(
            slug=row["slug"],
            name=row["name"],
            default_duration_minutes=int(row["default_duration_minutes"] or 60),
            agenda_sections=list(_json_loads(row["agenda_sections_json"], [])),
            required_attendee_roles=list(_json_loads(row["required_attendee_roles_json"], [])),
            optional_attendee_roles=list(_json_loads(row["optional_attendee_roles_json"], [])),
            prep_checklist_items=list(_json_loads(row["prep_checklist_json"], [])),
            agenda_checklist_items=list(_json_loads(row["agenda_checklist_json"], [])),
            closeout_checklist_items=list(_json_loads(row["closeout_checklist_json"], [])),
            appears_on_ics230_default=bool(row["appears_on_ics230_default"]),
            active=bool(row["active"]),
        )

    def _meeting_from_row(self, row: sqlite3.Row) -> Meeting:
        return Meeting(
            id=row["id"],
            incident_id=row["incident_id"],
            operational_period_id=row["operational_period_id"],
            template_id=row["template_id"],
            title=row["title"],
            meeting_date=row["meeting_date"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            location=row["location"] or "",
            virtual_link=row["virtual_link"] or "",
            owner=row["owner"] or "",
            status=row["status"] or "draft",
            show_on_ics230=bool(row["show_on_ics230"]),
            freeform_notes=row["freeform_notes"] or "",
            notes_log_routing_status=row["notes_log_routing_status"] or "not routed",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _attendee_from_row(self, row: sqlite3.Row) -> MeetingAttendee:
        return MeetingAttendee(
            id=row["id"],
            meeting_id=row["meeting_id"],
            display_name=row["display_name"],
            attendee_type=row["attendee_type"],
            role=row["role"] or "",
            requirement_status=row["requirement_status"],
            attendance_status=row["attendance_status"],
        )

    def _checklist_from_row(self, row: sqlite3.Row) -> ChecklistItem:
        return ChecklistItem(
            id=row["id"],
            meeting_id=row["meeting_id"],
            group_name=row["group_name"],
            text=row["text"],
            assigned_to=row["assigned_to"] or "",
            is_complete=bool(row["is_complete"]),
            is_not_applicable=bool(row["is_not_applicable"]),
            sort_order=row["sort_order"],
        )

    def _note_from_row(self, row: sqlite3.Row) -> StructuredNote:
        return StructuredNote(
            id=row["id"],
            meeting_id=row["meeting_id"],
            category=row["category"],
            text=row["text"],
            author=row["author"] or "",
            timestamp=row["timestamp"],
            routing_status=row["routing_status"],
            routed_log_refs=list(_json_loads(row["routed_log_refs_json"], [])),
            routed_at=row["routed_at"],
        )


__all__ = ["MeetingsRepository"]
