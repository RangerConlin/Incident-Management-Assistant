"""SQLite repository for Public Information records.

The repository owns schema creation and small CRUD helpers. It keeps records in
incident-specific databases so the UI can work now while later migrations can
formalize these tables.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

from modules.public_information.models.records import utc_now

DATA_DIR = Path("data") / "incidents"


class PublicInformationRepository:
    """Data access layer for Public Information module tables."""

    def __init__(self, incident_id: Optional[str] = None, db_path: Optional[Path] = None):
        self.incident_id = str(incident_id or "unassigned")
        self.db_path = Path(db_path) if db_path else DATA_DIR / f"{self.incident_id}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS pio_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                subtitle TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'Press Release',
                audience TEXT NOT NULL DEFAULT 'Public',
                priority TEXT NOT NULL DEFAULT 'Normal',
                status TEXT NOT NULL DEFAULT 'Draft',
                dateline TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                quote_block TEXT NOT NULL DEFAULT '',
                safety_instructions TEXT NOT NULL DEFAULT '',
                next_update_statement TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                published_at TEXT NOT NULL DEFAULT '',
                related_incident_id TEXT NOT NULL DEFAULT '',
                related_operational_period_id TEXT NOT NULL DEFAULT '',
                template_id INTEGER,
                source_media_log_id INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_message_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                template_id INTEGER,
                revision_number INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                reviewer_id TEXT NOT NULL DEFAULT '',
                reviewer_name TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_media_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL DEFAULT '',
                outlet_agency TEXT NOT NULL DEFAULT '',
                contact_name TEXT NOT NULL DEFAULT '',
                contact_info TEXT NOT NULL DEFAULT '',
                topic TEXT NOT NULL DEFAULT '',
                deadline TEXT NOT NULL DEFAULT '',
                assigned_to TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'New',
                related_message_id INTEGER,
                follow_up_needed INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_misinformation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT NOT NULL DEFAULT 'Low',
                claim_rumor TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                first_seen TEXT NOT NULL DEFAULT '',
                last_seen TEXT NOT NULL DEFAULT '',
                reported_by TEXT NOT NULL DEFAULT '',
                operational_impact TEXT NOT NULL DEFAULT 'None',
                status TEXT NOT NULL DEFAULT 'New',
                assigned_to TEXT NOT NULL DEFAULT '',
                linked_response TEXT NOT NULL DEFAULT '',
                last_update TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'Unknown',
                source_reliability TEXT NOT NULL DEFAULT '',
                verification_notes TEXT NOT NULL DEFAULT '',
                related_confirmed_facts TEXT NOT NULL DEFAULT '',
                response_decision TEXT NOT NULL DEFAULT 'Monitor Only',
                approval_status TEXT NOT NULL DEFAULT '',
                distribution_channels TEXT NOT NULL DEFAULT '',
                attachments_note TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_misinformation_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                event_time TEXT NOT NULL,
                event_text TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_talking_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'Approved to Say',
                body TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Draft',
                created_by TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL DEFAULT '',
                template_type TEXT NOT NULL DEFAULT 'Press Release',
                agency_name TEXT NOT NULL DEFAULT '',
                header_text TEXT NOT NULL DEFAULT '',
                footer_text TEXT NOT NULL DEFAULT '',
                contact_block TEXT NOT NULL DEFAULT '',
                logo_path TEXT NOT NULL DEFAULT '',
                release_label TEXT NOT NULL DEFAULT '',
                default_classification_label TEXT NOT NULL DEFAULT '',
                default_font_name TEXT NOT NULL DEFAULT '',
                default_footer_disclaimer TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_template_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                template_snapshot TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_distribution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                channel TEXT NOT NULL DEFAULT 'Press Release Email',
                distributed_at TEXT NOT NULL DEFAULT '',
                distributed_by TEXT NOT NULL DEFAULT '',
                audience TEXT NOT NULL DEFAULT 'Public',
                recipient_outlet TEXT NOT NULL DEFAULT '',
                confirmation_notes TEXT NOT NULL DEFAULT '',
                attachment_export_path TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pio_generated_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                template_id INTEGER,
                template_version INTEGER,
                export_path TEXT NOT NULL DEFAULT '',
                generated_at TEXT NOT NULL,
                generated_by TEXT NOT NULL DEFAULT ''
            )
            """,
        ]
        with self.connect() as conn:
            for statement in statements:
                conn.execute(statement)
            conn.commit()

    def _row(self, query: str, params: Iterable[Any] = ()) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            return dict(row) if row else None

    def _rows(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]

    def list_messages(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pio_messages ORDER BY updated_at DESC, id DESC")

    def get_message(self, message_id: int) -> Optional[dict[str, Any]]:
        return self._row("SELECT * FROM pio_messages WHERE id = ?", (message_id,))

    def save_message(self, data: dict[str, Any], user: str = "") -> dict[str, Any]:
        now = utc_now()
        values = dict(data)
        values.setdefault("created_at", now)
        values["updated_at"] = now
        values.setdefault("related_incident_id", self.incident_id)
        columns = [
            "title", "subtitle", "type", "audience", "priority", "status", "dateline", "body",
            "quote_block", "safety_instructions", "next_update_statement", "created_by", "approved_by",
            "created_at", "updated_at", "published_at", "related_incident_id",
            "related_operational_period_id", "template_id", "source_media_log_id",
        ]
        if values.get("id"):
            assignments = ", ".join(f"{col} = ?" for col in columns if col != "created_at")
            params = [values.get(col, "") for col in columns if col != "created_at"] + [values["id"]]
            with self.connect() as conn:
                conn.execute(f"UPDATE pio_messages SET {assignments} WHERE id = ?", params)
                conn.commit()
            message_id = int(values["id"])
        else:
            params = [values.get(col, "") for col in columns]
            placeholders = ", ".join("?" for _ in columns)
            with self.connect() as conn:
                cur = conn.execute(
                    f"INSERT INTO pio_messages ({', '.join(columns)}) VALUES ({placeholders})", params
                )
                message_id = int(cur.lastrowid)
                conn.commit()
        self.add_revision(message_id, values, user)
        return self.get_message(message_id) or {}

    def add_revision(self, message_id: int, data: dict[str, Any], user: str = "") -> None:
        count = self._row("SELECT COUNT(*) AS total FROM pio_message_revisions WHERE message_id = ?", (message_id,))
        revision = int((count or {}).get("total", 0)) + 1
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pio_message_revisions
                (message_id, title, body, template_id, revision_number, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, data.get("title", ""), data.get("body", ""), data.get("template_id"), revision, utc_now(), user),
            )
            conn.commit()

    def set_message_status(self, message_id: int, status: str, user: str = "", comment: str = "") -> dict[str, Any]:
        now = utc_now()
        published_at = now if status == "Published" else (self.get_message(message_id) or {}).get("published_at", "")
        approved_by = user if status == "Approved" else (self.get_message(message_id) or {}).get("approved_by", "")
        with self.connect() as conn:
            conn.execute(
                "UPDATE pio_messages SET status = ?, updated_at = ?, published_at = ?, approved_by = ? WHERE id = ?",
                (status, now, published_at, approved_by, message_id),
            )
            conn.execute(
                "INSERT INTO pio_approvals (message_id, reviewer_id, reviewer_name, action, comment, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, user, user, status, comment, now),
            )
            conn.commit()
        return self.get_message(message_id) or {}

    def list_approvals(self, message_id: int) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pio_approvals WHERE message_id = ? ORDER BY timestamp", (message_id,))

    def list_templates(self, active_only: bool = False) -> list[dict[str, Any]]:
        if active_only:
            return self._rows("SELECT * FROM pio_templates WHERE is_active = 1 ORDER BY template_name")
        return self._rows("SELECT * FROM pio_templates ORDER BY template_name")

    def get_template(self, template_id: int) -> Optional[dict[str, Any]]:
        return self._row("SELECT * FROM pio_templates WHERE id = ?", (template_id,))

    def save_template(self, data: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        values = dict(data)
        values.setdefault("created_at", now)
        values["updated_at"] = now
        columns = [
            "template_name", "template_type", "agency_name", "header_text", "footer_text", "contact_block",
            "logo_path", "release_label", "default_classification_label", "default_font_name",
            "default_footer_disclaimer", "is_active", "created_at", "updated_at", "version",
        ]
        if values.get("id"):
            assignments = ", ".join(f"{col} = ?" for col in columns if col != "created_at")
            params = [values.get(col, "") for col in columns if col != "created_at"] + [values["id"]]
            with self.connect() as conn:
                conn.execute(f"UPDATE pio_templates SET {assignments} WHERE id = ?", params)
                conn.commit()
            template_id = int(values["id"])
        else:
            params = [values.get(col, "") for col in columns]
            with self.connect() as conn:
                cur = conn.execute(
                    f"INSERT INTO pio_templates ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    params,
                )
                template_id = int(cur.lastrowid)
                conn.commit()
        return self.get_template(template_id) or {}

    def create_response_draft_from_media(self, media_id: int, user: str = "") -> dict[str, Any]:
        media = self._row("SELECT * FROM pio_media_log WHERE id = ?", (media_id,)) or {}
        message = self.save_message(
            {
                "title": media.get("topic", ""),
                "type": "Holding Statement",
                "audience": "Media",
                "priority": "Normal",
                "status": "Draft",
                "created_by": user,
                "source_media_log_id": media_id,
                "related_incident_id": self.incident_id,
            },
            user,
        )
        with self.connect() as conn:
            conn.execute("UPDATE pio_media_log SET related_message_id = ? WHERE id = ?", (message.get("id"), media_id))
            conn.commit()
        return message

    def save_record(self, table: str, data: dict[str, Any], timestamp_field: Optional[str] = None) -> dict[str, Any]:
        values = dict(data)
        if timestamp_field:
            values[timestamp_field] = utc_now()
        if values.get("id"):
            record_id = int(values.pop("id"))
            assignments = ", ".join(f"{key} = ?" for key in values)
            with self.connect() as conn:
                conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", [*values.values(), record_id])
                conn.commit()
        else:
            columns = list(values.keys())
            with self.connect() as conn:
                cur = conn.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    list(values.values()),
                )
                record_id = int(cur.lastrowid)
                conn.commit()
        return self._row(f"SELECT * FROM {table} WHERE id = ?", (record_id,)) or {}

    def list_records(self, table: str, order_by: str = "id DESC") -> list[dict[str, Any]]:
        return self._rows(f"SELECT * FROM {table} ORDER BY {order_by}")

    def add_misinformation_timeline(self, item_id: int, event_text: str, user: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO pio_misinformation_timeline (item_id, event_time, event_text, created_by) VALUES (?, ?, ?, ?)",
                (item_id, utc_now(), event_text, user),
            )
            conn.commit()

    def list_misinformation_timeline(self, item_id: int) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pio_misinformation_timeline WHERE item_id = ? ORDER BY event_time", (item_id,))

    def summary_counts(self) -> dict[str, int | str]:
        with self.connect() as conn:
            scalar = lambda sql, params=(): conn.execute(sql, params).fetchone()[0]
            return {
                "Pending Approvals": scalar("SELECT COUNT(*) FROM pio_messages WHERE status = 'Submitted for Review'"),
                "Draft Messages": scalar("SELECT COUNT(*) FROM pio_messages WHERE status = 'Draft'"),
                "Published / Released Messages": scalar("SELECT COUNT(*) FROM pio_messages WHERE status = 'Published'"),
                "Media Follow-Ups": scalar("SELECT COUNT(*) FROM pio_media_log WHERE follow_up_needed = 1 OR status = 'Follow-Up Needed'"),
                "Active Misinformation Items": scalar("SELECT COUNT(*) FROM pio_misinformation_items WHERE status NOT IN ('Corrected', 'Closed')"),
                "Next Briefing / Next Update": "Not scheduled",
            }
