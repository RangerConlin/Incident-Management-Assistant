import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .message import Status

DB_DIR = "data/missions"


def _utcnow() -> str:
    return datetime.utcnow().isoformat() + "Z"


def get_db_path(mission_id: int) -> str:
    return os.path.join(DB_DIR, f"{mission_id}.db")


def get_connection(mission_id: int) -> sqlite3.Connection:
    path = get_db_path(mission_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(mission_id: int) -> None:
    conn = get_connection(mission_id)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public_info_messages (
            id INTEGER PRIMARY KEY,
            mission_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            type TEXT NOT NULL,
            audience TEXT NOT NULL,
            status TEXT NOT NULL,
            tags TEXT,
            revision INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER NOT NULL,
            approved_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            published_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public_info_message_edits (
            id INTEGER PRIMARY KEY,
            message_id INTEGER NOT NULL,
            editor_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            change_summary TEXT
        )
        """
    )
    conn.commit()
    conn.close()


class PublicInfoRepository:
    def __init__(self, mission_id: int):
        init_db(mission_id)
        self.mission_id = mission_id

    # Utility functions
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {k: row[k] for k in row.keys()}

    # CRUD
    def create_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = _utcnow()
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO public_info_messages
            (mission_id, title, body, type, audience, status, tags, revision, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                self.mission_id,
                data["title"],
                data["body"],
                data["type"],
                data["audience"],
                Status.Draft.value,
                data.get("tags"),
                data["created_by"],
                now,
                now,
            ),
        )
        message_id = cur.lastrowid
        conn.commit()
        conn.close()
        return self.get_message(message_id)

    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM public_info_messages WHERE id=? AND mission_id=?",
            (message_id, self.mission_id),
        )
        row = cur.fetchone()
        conn.close()
        return self._row_to_dict(row) if row else None

    def list_messages(
        self,
        *,
        status: Optional[str] = None,
        type: Optional[str] = None,
        audience: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[Dict[str, Any]]:
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        clauses: List[str] = ["mission_id = ?"]
        params: List[Any] = [self.mission_id]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if type:
            clauses.append("type = ?")
            params.append(type)
        if audience:
            clauses.append("audience = ?")
            params.append(audience)
        if q:
            clauses.append("(title LIKE ? OR body LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        where = " AND ".join(clauses)
        offset = (page - 1) * page_size
        cur.execute(
            f"SELECT * FROM public_info_messages WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        )
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def update_message(
        self, message_id: int, data: Dict[str, Any], editor_id: int, change_summary: str = "Update"
    ) -> Dict[str, Any]:
        msg = self.get_message(message_id)
        if not msg:
            raise ValueError("Message not found")
        if msg["status"] not in {Status.Draft.value, Status.InReview.value}:
            raise ValueError("Cannot edit message in current status")
        fields: List[str] = []
        values: List[Any] = []
        for key in ["title", "body", "type", "audience", "tags"]:
            if key in data and data[key] is not None:
                fields.append(f"{key}=?")
                values.append(data[key])
        if fields:
            now = _utcnow()
            revision = msg["revision"] + 1
            fields.extend(["revision=?", "updated_at=?"])
            values.extend([revision, now, message_id])
            conn = get_connection(self.mission_id)
            cur = conn.cursor()
            cur.execute(
                f"UPDATE public_info_messages SET {', '.join(fields)} WHERE id=?",
                values,
            )
            conn.commit()
            conn.close()
            self.log_edit(message_id, editor_id, change_summary)
        return self.get_message(message_id)

    # State transitions
    def submit_for_review(self, message_id: int, user_id: int) -> Dict[str, Any]:
        msg = self.get_message(message_id)
        if not msg or msg["status"] != Status.Draft.value:
            raise ValueError("Only draft messages can be submitted")
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        now = _utcnow()
        cur.execute(
            "UPDATE public_info_messages SET status=?, updated_at=? WHERE id=?",
            (Status.InReview.value, now, message_id),
        )
        conn.commit()
        conn.close()
        self.log_edit(message_id, user_id, "Submitted for review")
        return self.get_message(message_id)

    def approve_message(self, message_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        if not set(user.get("roles", [])).intersection({"PIO", "LeadPIO", "IC"}):
            raise PermissionError("User not permitted to approve")
        msg = self.get_message(message_id)
        if not msg or msg["status"] != Status.InReview.value:
            raise ValueError("Only messages in review can be approved")
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        now = _utcnow()
        cur.execute(
            "UPDATE public_info_messages SET status=?, approved_by=?, updated_at=? WHERE id=?",
            (Status.Approved.value, user["id"], now, message_id),
        )
        conn.commit()
        conn.close()
        self.log_edit(message_id, user["id"], "Approved")
        return self.get_message(message_id)

    def publish_message(self, message_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
        if not set(user.get("roles", [])).intersection({"LeadPIO", "IC"}):
            raise PermissionError("User not permitted to publish")
        msg = self.get_message(message_id)
        if not msg or msg["status"] != Status.Approved.value:
            raise ValueError("Only approved messages can be published")
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        now = _utcnow()
        approved_by = msg["approved_by"] or user["id"]
        cur.execute(
            "UPDATE public_info_messages SET status=?, published_at=?, approved_by=?, updated_at=? WHERE id=?",
            (Status.Published.value, now, approved_by, now, message_id),
        )
        conn.commit()
        conn.close()
        self.log_edit(message_id, user["id"], "Published")
        return self.get_message(message_id)

    def archive_message(self, message_id: int, user_id: int) -> Dict[str, Any]:
        msg = self.get_message(message_id)
        if not msg or msg["status"] != Status.Published.value:
            raise ValueError("Only published messages can be archived")
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        now = _utcnow()
        cur.execute(
            "UPDATE public_info_messages SET status=?, updated_at=? WHERE id=?",
            (Status.Archived.value, now, message_id),
        )
        conn.commit()
        conn.close()
        self.log_edit(message_id, user_id, "Archived")
        return self.get_message(message_id)

    def list_history(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, type, audience, published_at, revision, approved_by FROM public_info_messages WHERE mission_id=? AND status=? ORDER BY published_at DESC",
            (self.mission_id, Status.Published.value),
        )
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def log_edit(self, message_id: int, editor_id: int, summary: str) -> None:
        conn = get_connection(self.mission_id)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public_info_message_edits (message_id, editor_id, timestamp, change_summary) VALUES (?, ?, ?, ?)",
            (message_id, editor_id, _utcnow(), summary),
        )
        conn.commit()
        conn.close()
