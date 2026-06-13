"""SQLite repository for Hazard Type Library master data."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from models.database import DB_PATH as DEFAULT_DB_PATH

from ..models.hazard_type_models import (
    HAZARD_CATEGORIES,
    HAZARD_LIKELIHOODS,
    HAZARD_RISK_LEVELS,
    HAZARD_SEVERITIES,
    HAZARD_SOURCES,
    HazardMitigation,
    HazardPpeItem,
    HazardReference,
    HazardType,
    HazardTypeResourceDefault,
    HazardTypeSearchResult,
)

ISO_TIMESTAMP = "%Y-%m-%dT%H:%M:%S"


def _now() -> str:
    return datetime.now().strftime(ISO_TIMESTAMP)


class HazardTypeRepository:
    """Persistence API for reusable hazard type definitions."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.initialize_schema()

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Create or lightly migrate Hazard Type Library tables."""

        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS hazard_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT 'Other',
                    source TEXT NOT NULL DEFAULT 'AHJ Custom',
                    owner_agency TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    default_risk_level TEXT NOT NULL DEFAULT 'Unknown',
                    default_likelihood TEXT NOT NULL DEFAULT 'Unknown',
                    default_severity TEXT NOT NULL DEFAULT 'Unknown',
                    default_control_measure TEXT NOT NULL DEFAULT '',
                    default_ppe TEXT NOT NULL DEFAULT '',
                    default_safety_message TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT '',
                    updated_by TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS hazard_type_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hazard_type_id INTEGER NOT NULL,
                    alias TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(hazard_type_id, alias),
                    FOREIGN KEY(hazard_type_id) REFERENCES hazard_types(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS hazard_mitigations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hazard_type_id INTEGER NOT NULL,
                    mitigation_text TEXT NOT NULL,
                    mitigation_category TEXT NOT NULL DEFAULT '',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(hazard_type_id) REFERENCES hazard_types(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS hazard_ppe (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hazard_type_id INTEGER NOT NULL,
                    ppe_text TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(hazard_type_id) REFERENCES hazard_types(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS hazard_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hazard_type_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url_or_path TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(hazard_type_id) REFERENCES hazard_types(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS hazard_type_resource_defaults (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hazard_type_id INTEGER NOT NULL,
                    resource_type_id INTEGER NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(hazard_type_id, resource_type_id),
                    FOREIGN KEY(hazard_type_id) REFERENCES hazard_types(id) ON DELETE CASCADE
                );
                """
            )
            self._ensure_columns(
                conn,
                "hazard_types",
                {
                    "created_by": "TEXT NOT NULL DEFAULT ''",
                    "updated_by": "TEXT NOT NULL DEFAULT ''",
                    "display_name": "TEXT NOT NULL DEFAULT ''",
                    "default_likelihood": "TEXT NOT NULL DEFAULT 'Unknown'",
                    "default_severity": "TEXT NOT NULL DEFAULT 'Unknown'",
                    "default_control_measure": "TEXT NOT NULL DEFAULT ''",
                    "default_ppe": "TEXT NOT NULL DEFAULT ''",
                    "default_safety_message": "TEXT NOT NULL DEFAULT ''",
                },
            )
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_hazard_types_search
                    ON hazard_types(name, display_name, category, source, owner_agency, default_risk_level);
                CREATE INDEX IF NOT EXISTS idx_hazard_type_aliases_alias
                    ON hazard_type_aliases(alias);
                CREATE INDEX IF NOT EXISTS idx_hazard_mitigations_hazard
                    ON hazard_mitigations(hazard_type_id, sort_order);
                CREATE INDEX IF NOT EXISTS idx_hazard_ppe_hazard
                    ON hazard_ppe(hazard_type_id, sort_order);
                CREATE INDEX IF NOT EXISTS idx_hazard_references_hazard
                    ON hazard_references(hazard_type_id);
                CREATE INDEX IF NOT EXISTS idx_hazard_resource_defaults_hazard
                    ON hazard_type_resource_defaults(hazard_type_id, resource_type_id);
                """
            )

    def _ensure_columns(
        self, conn: sqlite3.Connection, table_name: str, columns: dict[str, str]
    ) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
        for column_name, ddl in columns.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def list_hazard_types(self, filters: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """Return rows for the main Hazard Type Library table."""

        filters = filters or {}
        where: list[str] = []
        params: list[Any] = []

        search_text = str(filters.get("search_text") or "").strip()
        include_inactive = bool(filters.get("include_inactive"))
        category = str(filters.get("category") or "All")
        source = str(filters.get("source") or "All")
        risk_level = str(filters.get("risk_level") or "All")
        active_filter = str(filters.get("active_filter") or "Active")

        if active_filter == "Active" and not include_inactive:
            where.append("ht.is_active = 1")
        elif active_filter == "Inactive":
            where.append("ht.is_active = 0")
        if category and category != "All":
            where.append("ht.category = ?")
            params.append(category)
        if source and source != "All":
            where.append("ht.source = ?")
            params.append(source)
        if risk_level and risk_level != "All":
            where.append("ht.default_risk_level = ?")
            params.append(risk_level)
        if search_text:
            like = f"%{search_text.lower()}%"
            where.append(self._search_clause())
            params.extend([like] * 13)

        sql = """
            SELECT ht.*,
                   COALESCE((
                       SELECT COUNT(*) FROM hazard_mitigations hm WHERE hm.hazard_type_id = ht.id
                   ), 0) AS mitigation_count,
                   COALESCE((
                       SELECT group_concat(hp.ppe_text, ', ')
                       FROM (
                           SELECT ppe_text
                           FROM hazard_ppe
                           WHERE hazard_type_id = ht.id
                           ORDER BY sort_order, lower(ppe_text)
                           LIMIT 3
                       ) hp
                   ), '') AS ppe_preview
            FROM hazard_types ht
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY lower(ht.name)"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def search_hazard_types(
        self, query: str, include_inactive: bool = False, limit: int = 20
    ) -> list[HazardTypeSearchResult]:
        """Search all fields used by the smart hazard search widget."""

        text = query.strip().lower()
        if not text:
            return []
        like = f"%{text}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ht.id, ht.name, ht.display_name, ht.category, ht.source, ht.default_risk_level,
                       CASE
                         WHEN lower(ht.name) LIKE ? THEN 'name'
                         WHEN lower(ht.display_name) LIKE ? THEN 'display name'
                         WHEN lower(ht.category) LIKE ? THEN 'category'
                         WHEN lower(ht.source) LIKE ? THEN 'source'
                         WHEN lower(ht.description) LIKE ? THEN 'description'
                         WHEN lower(ht.default_safety_message) LIKE ? THEN 'safety message'
                         WHEN lower(ht.notes) LIKE ? THEN 'notes'
                         WHEN EXISTS (
                             SELECT 1 FROM hazard_type_aliases a
                             WHERE a.hazard_type_id = ht.id AND lower(a.alias) LIKE ?
                         ) THEN 'alias'
                         WHEN EXISTS (
                             SELECT 1 FROM hazard_mitigations m
                             WHERE m.hazard_type_id = ht.id
                               AND (lower(m.mitigation_text) LIKE ? OR lower(m.mitigation_category) LIKE ?)
                         ) THEN 'mitigation'
                         ELSE 'PPE'
                       END AS matched_on
                FROM hazard_types ht
                WHERE """
                + ("1=1" if include_inactive else "ht.is_active = 1")
                + " AND "
                + self._search_clause()
                + """
                ORDER BY lower(ht.name)
                LIMIT ?
                """,
                (
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    like,
                    *([like] * 13),
                    limit,
                ),
            ).fetchall()
        return [
            HazardTypeSearchResult(
                hazard_type_id=int(row["id"]),
                hazard_type_text=row["display_name"] or row["name"],
                category=row["category"],
                default_risk_level=row["default_risk_level"],
                source=row["source"],
                matched_on=row["matched_on"],
            )
            for row in rows
        ]

    def get_hazard_type(self, hazard_type_id: int) -> Optional[HazardType]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM hazard_types WHERE id = ?",
                (hazard_type_id,),
            ).fetchone()
            return self._hazard_type_from_row(conn, row) if row else None

    def create_hazard_type(self, data: HazardType | dict[str, Any]) -> int:
        return self._save_hazard_type(data, None)

    def update_hazard_type(self, hazard_type_id: int, data: HazardType | dict[str, Any]) -> int:
        return self._save_hazard_type(data, hazard_type_id)

    def clone_hazard_type(self, hazard_type_id: int) -> int:
        """Copy a hazard type and all related child rows."""

        original = self.get_hazard_type(hazard_type_id)
        if original is None:
            raise ValueError("Hazard type not found")
        original.id = None
        original.name = self._next_copy_name(original.name)
        original.display_name = (
            f"{original.display_name} Copy".strip() if original.display_name else original.name
        )
        original.created_at = ""
        original.updated_at = ""
        original.created_by = ""
        original.updated_by = ""
        for child in original.mitigations:
            child.id = None
            child.hazard_type_id = 0
        for child in original.ppe_items:
            child.id = None
            child.hazard_type_id = 0
        for child in original.references:
            child.id = None
            child.hazard_type_id = 0
        for child in original.resource_defaults:
            child.id = None
            child.hazard_type_id = 0
        return self.create_hazard_type(original)

    def deactivate_hazard_type(self, hazard_type_id: int) -> None:
        self._set_hazard_type_active(hazard_type_id, False)

    def reactivate_hazard_type(self, hazard_type_id: int) -> None:
        self._set_hazard_type_active(hazard_type_id, True)

    def _set_hazard_type_active(self, hazard_type_id: int, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE hazard_types SET is_active = ?, updated_at = ? WHERE id = ?",
                (int(active), _now(), hazard_type_id),
            )

    def list_aliases(self, hazard_type_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM hazard_type_aliases
                WHERE hazard_type_id = ?
                ORDER BY lower(alias)
                """,
                (hazard_type_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_alias(self, hazard_type_id: int, alias: str) -> int:
        cleaned = alias.strip()
        if not cleaned:
            raise ValueError("Alias cannot be empty.")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO hazard_type_aliases (hazard_type_id, alias, created_at)
                VALUES (?, ?, ?)
                """,
                (hazard_type_id, cleaned, _now()),
            )
            return int(cur.lastrowid or 0)

    def remove_alias(self, alias_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM hazard_type_aliases WHERE id = ?", (alias_id,))

    def list_mitigations(self, hazard_type_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM hazard_mitigations
                WHERE hazard_type_id = ?
                ORDER BY sort_order, lower(mitigation_text), id
                """,
                (hazard_type_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_mitigation(
        self,
        hazard_type_id: int,
        mitigation_text: str,
        mitigation_category: str | None = None,
        is_default: bool = False,
        sort_order: int | None = None,
    ) -> int:
        cleaned = mitigation_text.strip()
        if not cleaned:
            raise ValueError("Mitigation text cannot be empty.")
        now = _now()
        with self._connect() as conn:
            order_value = sort_order if sort_order is not None else self._next_sort_order(
                conn, "hazard_mitigations", hazard_type_id
            )
            cur = conn.execute(
                """
                INSERT INTO hazard_mitigations
                (hazard_type_id, mitigation_text, mitigation_category, is_default, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hazard_type_id,
                    cleaned,
                    (mitigation_category or "").strip(),
                    int(is_default),
                    int(order_value),
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_mitigation(self, mitigation_id: int, data: dict[str, Any]) -> None:
        self._update_child_row(
            "hazard_mitigations",
            mitigation_id,
            {
                "mitigation_text": str(data.get("mitigation_text", "")).strip(),
                "mitigation_category": str(data.get("mitigation_category", "")).strip(),
                "is_default": int(bool(data.get("is_default"))),
                "sort_order": int(data.get("sort_order", 0)),
                "updated_at": _now(),
            },
            required_field="mitigation_text",
            required_label="Mitigation text",
        )

    def remove_mitigation(self, mitigation_id: int) -> None:
        self._remove_child_row("hazard_mitigations", mitigation_id)

    def list_ppe(self, hazard_type_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM hazard_ppe
                WHERE hazard_type_id = ?
                ORDER BY sort_order, lower(ppe_text), id
                """,
                (hazard_type_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_ppe(
        self,
        hazard_type_id: int,
        ppe_text: str,
        is_default: bool = False,
        sort_order: int | None = None,
    ) -> int:
        cleaned = ppe_text.strip()
        if not cleaned:
            raise ValueError("PPE text cannot be empty.")
        now = _now()
        with self._connect() as conn:
            order_value = sort_order if sort_order is not None else self._next_sort_order(
                conn, "hazard_ppe", hazard_type_id
            )
            cur = conn.execute(
                """
                INSERT INTO hazard_ppe
                (hazard_type_id, ppe_text, is_default, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (hazard_type_id, cleaned, int(is_default), int(order_value), now, now),
            )
            return int(cur.lastrowid)

    def update_ppe(self, ppe_id: int, data: dict[str, Any]) -> None:
        self._update_child_row(
            "hazard_ppe",
            ppe_id,
            {
                "ppe_text": str(data.get("ppe_text", "")).strip(),
                "is_default": int(bool(data.get("is_default"))),
                "sort_order": int(data.get("sort_order", 0)),
                "updated_at": _now(),
            },
            required_field="ppe_text",
            required_label="PPE text",
        )

    def remove_ppe(self, ppe_id: int) -> None:
        self._remove_child_row("hazard_ppe", ppe_id)

    def list_references(self, hazard_type_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM hazard_references
                WHERE hazard_type_id = ?
                ORDER BY lower(title), id
                """,
                (hazard_type_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_reference(
        self,
        hazard_type_id: int,
        title: str,
        url_or_path: str | None = None,
        notes: str | None = None,
    ) -> int:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Reference title cannot be empty.")
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO hazard_references
                (hazard_type_id, title, url_or_path, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    hazard_type_id,
                    cleaned,
                    (url_or_path or "").strip(),
                    (notes or "").strip(),
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_reference(self, reference_id: int, data: dict[str, Any]) -> None:
        self._update_child_row(
            "hazard_references",
            reference_id,
            {
                "title": str(data.get("title", "")).strip(),
                "url_or_path": str(data.get("url_or_path", "")).strip(),
                "notes": str(data.get("notes", "")).strip(),
                "updated_at": _now(),
            },
            required_field="title",
            required_label="Reference title",
        )

    def remove_reference(self, reference_id: int) -> None:
        self._remove_child_row("hazard_references", reference_id)

    def list_resource_defaults(self, hazard_type_id: int) -> list[dict[str, Any]]:
        resource_types_available = self._resource_types_table_exists()
        with self._connect() as conn:
            if resource_types_available:
                rows = conn.execute(
                    """
                    SELECT d.*,
                           COALESCE(rt.name, CAST(d.resource_type_id AS TEXT)) AS resource_type_name,
                           COALESCE(rt.category, '') AS resource_type_category
                    FROM hazard_type_resource_defaults d
                    LEFT JOIN resource_types rt ON rt.id = d.resource_type_id
                    WHERE d.hazard_type_id = ?
                    ORDER BY lower(resource_type_name), d.id
                    """,
                    (hazard_type_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT d.*,
                           CAST(d.resource_type_id AS TEXT) AS resource_type_name,
                           '' AS resource_type_category
                    FROM hazard_type_resource_defaults d
                    WHERE d.hazard_type_id = ?
                    ORDER BY d.resource_type_id, d.id
                    """,
                    (hazard_type_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    def add_resource_default(
        self, hazard_type_id: int, resource_type_id: int, notes: str | None = None
    ) -> int:
        if int(resource_type_id) <= 0:
            raise ValueError("Resource type ID must be a positive number.")
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR REPLACE INTO hazard_type_resource_defaults
                (id, hazard_type_id, resource_type_id, notes, created_at, updated_at)
                VALUES (
                    COALESCE(
                        (SELECT id FROM hazard_type_resource_defaults
                         WHERE hazard_type_id = ? AND resource_type_id = ?),
                        NULL
                    ),
                    ?, ?, ?,
                    COALESCE(
                        (SELECT created_at FROM hazard_type_resource_defaults
                         WHERE hazard_type_id = ? AND resource_type_id = ?),
                        ?
                    ),
                    ?
                )
                """,
                (
                    hazard_type_id,
                    resource_type_id,
                    hazard_type_id,
                    resource_type_id,
                    (notes or "").strip(),
                    hazard_type_id,
                    resource_type_id,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid or 0)

    def remove_resource_default(self, default_id: int) -> None:
        self._remove_child_row("hazard_type_resource_defaults", default_id)

    def get_default_hazards_for_resource_type(self, resource_type_id: int) -> list[HazardType]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ht.*
                FROM hazard_type_resource_defaults d
                JOIN hazard_types ht ON ht.id = d.hazard_type_id
                WHERE d.resource_type_id = ? AND ht.is_active = 1
                ORDER BY lower(ht.name)
                """,
                (resource_type_id,),
            ).fetchall()
            return [self._hazard_type_from_row(conn, row) for row in rows]

    def _save_hazard_type(self, data: HazardType | dict[str, Any], hazard_type_id: int | None) -> int:
        hazard = self._coerce_hazard_type(data, hazard_type_id)
        self._validate_hazard_type(hazard)
        now = _now()
        payload = {
            "name": hazard.name.strip(),
            "display_name": hazard.display_name.strip(),
            "category": hazard.category,
            "source": hazard.source,
            "owner_agency": hazard.owner_agency.strip(),
            "description": hazard.description.strip(),
            "default_risk_level": hazard.default_risk_level,
            "default_likelihood": hazard.default_likelihood,
            "default_severity": hazard.default_severity,
            "default_control_measure": hazard.default_control_measure.strip(),
            "default_ppe": hazard.default_ppe.strip(),
            "default_safety_message": hazard.default_safety_message.strip(),
            "is_active": int(hazard.is_active),
            "notes": hazard.notes.strip(),
            "updated_by": hazard.updated_by.strip(),
            "updated_at": now,
        }
        with self._connect() as conn:
            if hazard.id is None:
                payload["created_by"] = hazard.created_by.strip()
                payload["created_at"] = now
                columns = ", ".join(payload)
                placeholders = ", ".join("?" for _ in payload)
                cur = conn.execute(
                    f"INSERT INTO hazard_types ({columns}) VALUES ({placeholders})",
                    tuple(payload.values()),
                )
                saved_id = int(cur.lastrowid)
            else:
                assignments = ", ".join(f"{column} = ?" for column in payload)
                conn.execute(
                    f"UPDATE hazard_types SET {assignments} WHERE id = ?",
                    tuple(payload.values()) + (hazard.id,),
                )
                saved_id = int(hazard.id)
            self._replace_aliases(conn, saved_id, hazard.aliases)
            self._replace_mitigations(conn, saved_id, hazard.mitigations)
            self._replace_ppe(conn, saved_id, hazard.ppe_items)
            self._replace_references(conn, saved_id, hazard.references)
            self._replace_resource_defaults(conn, saved_id, hazard.resource_defaults)
            return saved_id

    def _replace_aliases(
        self, conn: sqlite3.Connection, hazard_type_id: int, aliases: Iterable[str]
    ) -> None:
        conn.execute("DELETE FROM hazard_type_aliases WHERE hazard_type_id = ?", (hazard_type_id,))
        for alias in self._clean_strings(aliases):
            conn.execute(
                """
                INSERT INTO hazard_type_aliases (hazard_type_id, alias, created_at)
                VALUES (?, ?, ?)
                """,
                (hazard_type_id, alias, _now()),
            )

    def _replace_mitigations(
        self,
        conn: sqlite3.Connection,
        hazard_type_id: int,
        mitigations: Iterable[HazardMitigation],
    ) -> None:
        conn.execute("DELETE FROM hazard_mitigations WHERE hazard_type_id = ?", (hazard_type_id,))
        for index, mitigation in enumerate(mitigations):
            text = mitigation.mitigation_text.strip()
            if not text:
                continue
            now = _now()
            conn.execute(
                """
                INSERT INTO hazard_mitigations
                (hazard_type_id, mitigation_text, mitigation_category, is_default, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hazard_type_id,
                    text,
                    mitigation.mitigation_category.strip(),
                    int(mitigation.is_default),
                    int(mitigation.sort_order if mitigation.sort_order is not None else index),
                    now,
                    now,
                ),
            )

    def _replace_ppe(
        self,
        conn: sqlite3.Connection,
        hazard_type_id: int,
        ppe_items: Iterable[HazardPpeItem],
    ) -> None:
        conn.execute("DELETE FROM hazard_ppe WHERE hazard_type_id = ?", (hazard_type_id,))
        for index, ppe_item in enumerate(ppe_items):
            text = ppe_item.ppe_text.strip()
            if not text:
                continue
            now = _now()
            conn.execute(
                """
                INSERT INTO hazard_ppe
                (hazard_type_id, ppe_text, is_default, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    hazard_type_id,
                    text,
                    int(ppe_item.is_default),
                    int(ppe_item.sort_order if ppe_item.sort_order is not None else index),
                    now,
                    now,
                ),
            )

    def _replace_references(
        self,
        conn: sqlite3.Connection,
        hazard_type_id: int,
        references: Iterable[HazardReference],
    ) -> None:
        conn.execute("DELETE FROM hazard_references WHERE hazard_type_id = ?", (hazard_type_id,))
        for reference in references:
            title = reference.title.strip()
            if not title:
                continue
            now = _now()
            conn.execute(
                """
                INSERT INTO hazard_references
                (hazard_type_id, title, url_or_path, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    hazard_type_id,
                    title,
                    reference.url_or_path.strip(),
                    reference.notes.strip(),
                    now,
                    now,
                ),
            )

    def _replace_resource_defaults(
        self,
        conn: sqlite3.Connection,
        hazard_type_id: int,
        defaults: Iterable[HazardTypeResourceDefault],
    ) -> None:
        conn.execute(
            "DELETE FROM hazard_type_resource_defaults WHERE hazard_type_id = ?",
            (hazard_type_id,),
        )
        for default in defaults:
            if int(default.resource_type_id or 0) <= 0:
                continue
            now = _now()
            conn.execute(
                """
                INSERT OR IGNORE INTO hazard_type_resource_defaults
                (hazard_type_id, resource_type_id, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    hazard_type_id,
                    int(default.resource_type_id),
                    default.notes.strip(),
                    now,
                    now,
                ),
            )

    def _update_child_row(
        self,
        table_name: str,
        row_id: int,
        payload: dict[str, Any],
        *,
        required_field: str,
        required_label: str,
    ) -> None:
        if not str(payload.get(required_field, "")).strip():
            raise ValueError(f"{required_label} cannot be empty.")
        assignments = ", ".join(f"{column} = ?" for column in payload)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {table_name} SET {assignments} WHERE id = ?",
                tuple(payload.values()) + (row_id,),
            )

    def _remove_child_row(self, table_name: str, row_id: int) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))

    def _next_sort_order(
        self, conn: sqlite3.Connection, table_name: str, hazard_type_id: int
    ) -> int:
        row = conn.execute(
            f"SELECT COALESCE(MAX(sort_order), -1) AS max_sort_order FROM {table_name} WHERE hazard_type_id = ?",
            (hazard_type_id,),
        ).fetchone()
        return int(row["max_sort_order"]) + 1

    def _search_clause(self) -> str:
        return """
        (
            lower(ht.name) LIKE ?
            OR lower(ht.display_name) LIKE ?
            OR lower(ht.category) LIKE ?
            OR lower(ht.source) LIKE ?
            OR lower(ht.description) LIKE ?
            OR lower(ht.default_safety_message) LIKE ?
            OR lower(ht.notes) LIKE ?
            OR EXISTS (
                SELECT 1 FROM hazard_type_aliases a
                WHERE a.hazard_type_id = ht.id AND lower(a.alias) LIKE ?
            )
            OR EXISTS (
                SELECT 1 FROM hazard_mitigations m
                WHERE m.hazard_type_id = ht.id
                  AND (lower(m.mitigation_text) LIKE ? OR lower(m.mitigation_category) LIKE ?)
            )
            OR EXISTS (
                SELECT 1 FROM hazard_ppe p
                WHERE p.hazard_type_id = ht.id AND lower(p.ppe_text) LIKE ?
            )
            OR lower(ht.default_control_measure) LIKE ?
            OR lower(ht.default_ppe) LIKE ?
        )
        """

    def _hazard_type_from_row(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> HazardType:
        hazard_type_id = int(row["id"])
        aliases = [
            alias_row["alias"]
            for alias_row in conn.execute(
                "SELECT alias FROM hazard_type_aliases WHERE hazard_type_id = ? ORDER BY lower(alias)",
                (hazard_type_id,),
            ).fetchall()
        ]
        mitigations = [
            HazardMitigation(
                id=int(mitigation_row["id"]),
                hazard_type_id=hazard_type_id,
                mitigation_text=mitigation_row["mitigation_text"],
                mitigation_category=mitigation_row["mitigation_category"],
                is_default=bool(mitigation_row["is_default"]),
                sort_order=int(mitigation_row["sort_order"]),
                created_at=mitigation_row["created_at"],
                updated_at=mitigation_row["updated_at"],
            )
            for mitigation_row in conn.execute(
                """
                SELECT * FROM hazard_mitigations
                WHERE hazard_type_id = ?
                ORDER BY sort_order, lower(mitigation_text), id
                """,
                (hazard_type_id,),
            ).fetchall()
        ]
        ppe_items = [
            HazardPpeItem(
                id=int(ppe_row["id"]),
                hazard_type_id=hazard_type_id,
                ppe_text=ppe_row["ppe_text"],
                is_default=bool(ppe_row["is_default"]),
                sort_order=int(ppe_row["sort_order"]),
                created_at=ppe_row["created_at"],
                updated_at=ppe_row["updated_at"],
            )
            for ppe_row in conn.execute(
                """
                SELECT * FROM hazard_ppe
                WHERE hazard_type_id = ?
                ORDER BY sort_order, lower(ppe_text), id
                """,
                (hazard_type_id,),
            ).fetchall()
        ]
        references = [
            HazardReference(
                id=int(reference_row["id"]),
                hazard_type_id=hazard_type_id,
                title=reference_row["title"],
                url_or_path=reference_row["url_or_path"],
                notes=reference_row["notes"],
                created_at=reference_row["created_at"],
                updated_at=reference_row["updated_at"],
            )
            for reference_row in conn.execute(
                """
                SELECT * FROM hazard_references
                WHERE hazard_type_id = ?
                ORDER BY lower(title), id
                """,
                (hazard_type_id,),
            ).fetchall()
        ]
        resource_defaults = [
            HazardTypeResourceDefault(
                id=int(default_row["id"]),
                hazard_type_id=hazard_type_id,
                resource_type_id=int(default_row["resource_type_id"]),
                notes=default_row["notes"],
                resource_type_name=default_row["resource_type_name"],
                resource_type_category=default_row["resource_type_category"],
                created_at=default_row["created_at"],
                updated_at=default_row["updated_at"],
            )
            for default_row in self.list_resource_defaults(hazard_type_id)
        ]
        return HazardType(
            id=hazard_type_id,
            name=row["name"],
            display_name=row["display_name"],
            category=row["category"],
            source=row["source"],
            owner_agency=row["owner_agency"],
            description=row["description"],
            default_risk_level=row["default_risk_level"],
            default_likelihood=row["default_likelihood"],
            default_severity=row["default_severity"],
            default_control_measure=row["default_control_measure"],
            default_ppe=row["default_ppe"],
            default_safety_message=row["default_safety_message"],
            is_active=bool(row["is_active"]),
            notes=row["notes"],
            aliases=aliases,
            mitigations=mitigations,
            ppe_items=ppe_items,
            references=references,
            resource_defaults=resource_defaults,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"],
        )

    def _coerce_hazard_type(
        self, data: HazardType | dict[str, Any], hazard_type_id: int | None
    ) -> HazardType:
        if isinstance(data, HazardType):
            if hazard_type_id is not None:
                data.id = hazard_type_id
            return data
        return HazardType(
            id=hazard_type_id,
            name=str(data.get("name", "")),
            display_name=str(data.get("display_name", "")),
            category=str(data.get("category", "Other")),
            source=str(data.get("source", "AHJ Custom")),
            owner_agency=str(data.get("owner_agency", "")),
            description=str(data.get("description", "")),
            default_risk_level=str(data.get("default_risk_level", "Unknown")),
            default_likelihood=str(data.get("default_likelihood", "Unknown")),
            default_severity=str(data.get("default_severity", "Unknown")),
            default_control_measure=str(data.get("default_control_measure", "")),
            default_ppe=str(data.get("default_ppe", "")),
            default_safety_message=str(data.get("default_safety_message", "")),
            is_active=bool(data.get("is_active", True)),
            notes=str(data.get("notes", "")),
            aliases=list(data.get("aliases", [])),
            mitigations=list(data.get("mitigations", [])),
            ppe_items=list(data.get("ppe_items", [])),
            references=list(data.get("references", [])),
            resource_defaults=list(data.get("resource_defaults", [])),
            created_by=str(data.get("created_by", "")),
            updated_by=str(data.get("updated_by", "")),
        )

    def _validate_hazard_type(self, hazard_type: HazardType) -> None:
        if not hazard_type.name.strip():
            raise ValueError("Name is required.")
        if hazard_type.category not in HAZARD_CATEGORIES:
            raise ValueError("Category is required and must be a supported value.")
        if hazard_type.source not in HAZARD_SOURCES:
            raise ValueError("Source is required and must be a supported value.")
        if hazard_type.default_risk_level not in HAZARD_RISK_LEVELS:
            raise ValueError("Default risk level must be a supported value.")
        if hazard_type.default_likelihood not in HAZARD_LIKELIHOODS:
            raise ValueError("Default likelihood must be a supported value.")
        if hazard_type.default_severity not in HAZARD_SEVERITIES:
            raise ValueError("Default severity must be a supported value.")

    def _resource_types_table_exists(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'resource_types'"
            ).fetchone()
            return row is not None

    def _next_copy_name(self, base_name: str) -> str:
        candidate = f"{base_name} Copy"
        with self._connect() as conn:
            existing = {
                row["name"].lower()
                for row in conn.execute("SELECT name FROM hazard_types").fetchall()
            }
        if candidate.lower() not in existing:
            return candidate
        suffix = 2
        while f"{candidate} {suffix}".lower() in existing:
            suffix += 1
        return f"{candidate} {suffix}"

    @staticmethod
    def _clean_strings(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for value in values:
            item = value.strip()
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                cleaned.append(item)
        return cleaned
