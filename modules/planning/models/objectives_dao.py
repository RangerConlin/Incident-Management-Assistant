"""SQLite access layer for planning objective templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional


logger = logging.getLogger(__name__)


PRIORITY_VALUES = ("Low", "Normal", "High", "Urgent")


@dataclass(slots=True)
class ObjectiveTemplate:
    """Dataclass mirroring the objective_templates schema."""

    id: Optional[int] = None
    code: Optional[str] = None
    title: str = ""
    description: str = ""
    default_section: Optional[str] = None
    priority: str = "Normal"
    active: bool = True
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)


class ObjectivesDAO:
    """Data-access object for managing objective templates and tags."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    # ------------------------------------------------------------------
    # Connection helpers
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ------------------------------------------------------------------
    # Schema management
    def ensure_schema(self) -> None:
        """Create the necessary tables and ensure required columns exist."""

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS objective_templates (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT UNIQUE,
                  title TEXT NOT NULL,
                  description TEXT NOT NULL,
                  default_section TEXT,
                  priority TEXT NOT NULL DEFAULT 'Normal',
                  active INTEGER NOT NULL DEFAULT 1,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS objective_tags (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS objective_template_tags (
                  template_id INTEGER NOT NULL REFERENCES objective_templates(id) ON DELETE CASCADE,
                  tag_id INTEGER NOT NULL REFERENCES objective_tags(id) ON DELETE CASCADE,
                  PRIMARY KEY (template_id, tag_id)
                )
                """
            )

            # Ensure columns exist for templates in case of migrations
            expected_columns = {
                "code": "TEXT",
                "title": "TEXT",
                "description": "TEXT",
                "default_section": "TEXT",
                "priority": "TEXT NOT NULL DEFAULT 'Normal'",
                "active": "INTEGER NOT NULL DEFAULT 1",
                "created_at": "TEXT NOT NULL",
                "updated_at": "TEXT NOT NULL",
            }

            cursor.execute("PRAGMA table_info(objective_templates)")
            present_columns = {row[1] for row in cursor.fetchall()}
            for column, ddl in expected_columns.items():
                if column not in present_columns:
                    logger.info("Adding column %s to objective_templates", column)
                    cursor.execute(
                        f"ALTER TABLE objective_templates ADD COLUMN {column} {ddl}"
                    )

    # ------------------------------------------------------------------
    # Helpers
    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _row_to_template(self, row: sqlite3.Row, tags: Iterable[str]) -> ObjectiveTemplate:
        return ObjectiveTemplate(
            id=row["id"],
            code=row["code"],
            title=row["title"],
            description=row["description"],
            default_section=row["default_section"],
            priority=row["priority"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tags=list(tags),
        )

    def _ensure_tag(self, conn: sqlite3.Connection, name: str) -> int:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        cur = conn.execute(
            "INSERT INTO objective_tags (name) VALUES (?) ON CONFLICT(name) DO NOTHING",
            (normalized,),
        )
        if cur.lastrowid:
            return int(cur.lastrowid)
        cur = conn.execute("SELECT id FROM objective_tags WHERE name = ?", (normalized,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"Failed to upsert tag '{normalized}'")
        return int(row["id"])

    # ------------------------------------------------------------------
    # Template CRUD
    def list_templates(
        self,
        search: Optional[str] = None,
        include_archived: bool = False,
        tag_filter: Optional[List[str]] = None,
    ) -> List[ObjectiveTemplate]:
        """Return templates applying optional search/tag filters."""

        query = [
            "SELECT t.*, IFNULL(GROUP_CONCAT(g.name, '\u001f'), '') AS tag_names",
            "FROM objective_templates AS t",
            "LEFT JOIN objective_template_tags AS tt ON tt.template_id = t.id",
            "LEFT JOIN objective_tags AS g ON g.id = tt.tag_id",
        ]
        params: list[object] = []
        conditions: list[str] = []

        if search:
            like = f"%{search.strip()}%"
            conditions.append(
                "(t.title LIKE ? OR t.description LIKE ? OR t.code LIKE ?)"
            )
            params.extend([like, like, like])

        if not include_archived:
            conditions.append("t.active = 1")

        if tag_filter:
            filtered = [tag.strip() for tag in tag_filter if tag.strip()]
            if filtered:
                placeholders = ",".join("?" for _ in filtered)
                conditions.append(
                    f"t.id IN (SELECT tt2.template_id FROM objective_template_tags AS tt2 "
                    f"JOIN objective_tags AS g2 ON g2.id = tt2.tag_id "
                    f"WHERE g2.name IN ({placeholders}) GROUP BY tt2.template_id "
                    f"HAVING COUNT(DISTINCT g2.name) = ? )"
                )
                params.extend(filtered)
                params.append(len(set(filtered)))

        if conditions:
            query.append("WHERE " + " AND ".join(conditions))
        query.append("GROUP BY t.id ORDER BY t.updated_at DESC, t.id DESC")

        with self._connect() as conn:
            cursor = conn.execute("\n".join(query), params)
            rows = cursor.fetchall()

        templates: list[ObjectiveTemplate] = []
        for row in rows:
            tag_names = []
            if row["tag_names"]:
                tag_names = [
                    name for name in row["tag_names"].split("\u001f") if name.strip()
                ]
            templates.append(self._row_to_template(row, tag_names))
        return templates

    def get_template(self, template_id: int) -> Optional[ObjectiveTemplate]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM objective_templates WHERE id = ?", (template_id,)
            ).fetchone()
            if row is None:
                return None
            tags_cursor = conn.execute(
                "SELECT g.name FROM objective_tags AS g "
                "JOIN objective_template_tags AS tt ON tt.tag_id = g.id "
                "WHERE tt.template_id = ? ORDER BY g.name",
                (template_id,),
            )
            tags = [tag_row[0] for tag_row in tags_cursor.fetchall()]
        return self._row_to_template(row, tags)

    def create_template(self, template: ObjectiveTemplate) -> int:
        timestamp = self._utc_timestamp()
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO objective_templates (
                        code, title, description, default_section, priority,
                        active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template.code,
                        template.title,
                        template.description,
                        template.default_section,
                        template.priority,
                        1 if template.active else 0,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:  # pragma: no cover - UI feedback
                raise ValueError("Objective code must be unique.") from exc

            new_id = int(cursor.lastrowid)
            if template.tags:
                self.replace_template_tags(new_id, template.tags)
        return new_id

    def update_template(self, template: ObjectiveTemplate) -> None:
        if template.id is None:
            raise ValueError("Template id is required for update")
        timestamp = self._utc_timestamp()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    UPDATE objective_templates
                    SET code = ?,
                        title = ?,
                        description = ?,
                        default_section = ?,
                        priority = ?,
                        active = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        template.code,
                        template.title,
                        template.description,
                        template.default_section,
                        template.priority,
                        1 if template.active else 0,
                        timestamp,
                        template.id,
                    ),
                )
            except sqlite3.IntegrityError as exc:  # pragma: no cover - UI feedback
                raise ValueError("Objective code must be unique.") from exc

            if template.tags is not None:
                self.replace_template_tags(template.id, template.tags)

    def set_active(self, template_id: int, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE objective_templates SET active = ?, updated_at = ? WHERE id = ?",
                (1 if active else 0, self._utc_timestamp(), template_id),
            )

    # ------------------------------------------------------------------
    # Tags
    def list_tags(self) -> List[str]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM objective_tags ORDER BY name COLLATE NOCASE"
            )
            return [row[0] for row in cursor.fetchall()]

    def upsert_tag(self, name: str) -> int:
        with self._connect() as conn:
            return self._ensure_tag(conn, name)

    def replace_template_tags(self, template_id: int, tags: Iterable[str]) -> None:
        unique_tags = []
        seen = set()
        for tag in tags:
            normalized = tag.strip()
            if not normalized or normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            unique_tags.append(normalized)

        with self._connect() as conn:
            conn.execute(
                "DELETE FROM objective_template_tags WHERE template_id = ?",
                (template_id,),
            )
            for tag_name in unique_tags:
                tag_id = self._ensure_tag(conn, tag_name)
                conn.execute(
                    "INSERT OR IGNORE INTO objective_template_tags (template_id, tag_id) VALUES (?, ?)",
                    (template_id, tag_id),
                )

    def delete_template(self, template_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM objective_templates WHERE id = ?", (template_id,))


__all__ = [
    "ObjectiveTemplate",
    "ObjectivesDAO",
    "PRIORITY_VALUES",
]

