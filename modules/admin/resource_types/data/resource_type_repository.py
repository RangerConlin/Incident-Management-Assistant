"""SQLite repository for Resource Type Library master data.

The UI intentionally calls this repository for all persistence so SQL stays in
one beginner-friendly place.  The repository creates and lightly migrates the
master database tables on startup; no demo rows are inserted.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from models.database import DB_PATH as DEFAULT_DB_PATH

from ..models.resource_type_models import (
    FemaNimsMapping,
    RESOURCE_CATEGORIES,
    RESOURCE_SOURCES,
    ResourceCapability,
    ResourceType,
    ResourceTypeComponent,
    ResourceTypeSearchResult,
)

ISO_TIMESTAMP = "%Y-%m-%dT%H:%M:%S"


def _now() -> str:
    """Return the timestamp format used by existing repository modules."""

    return datetime.now().strftime(ISO_TIMESTAMP)


class ResourceTypeRepository:
    """Persistence API for reusable resource type definitions.

    All data is stored in the master database because these definitions are
    shared across incidents.  Tests and tools can pass a temporary ``db_path``.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.ensure_schema()

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

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------
    def ensure_schema(self) -> None:
        """Create or update Resource Type Library tables and indexes."""

        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS resource_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    planning_display_name TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT 'Other',
                    source TEXT NOT NULL DEFAULT 'AHJ Custom',
                    owner_agency TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    default_unit TEXT NOT NULL DEFAULT 'each',
                    typical_quantity REAL NOT NULL DEFAULT 1,
                    typical_team_size INTEGER,
                    is_kit_cache INTEGER NOT NULL DEFAULT 0,
                    is_consumable INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT '',
                    updated_by TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS resource_type_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_type_id INTEGER NOT NULL,
                    alias TEXT NOT NULL,
                    UNIQUE(resource_type_id, alias),
                    FOREIGN KEY(resource_type_id) REFERENCES resource_types(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS resource_capabilities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    aliases TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS resource_type_capabilities (
                    resource_type_id INTEGER NOT NULL,
                    capability_id INTEGER NOT NULL,
                    PRIMARY KEY(resource_type_id, capability_id),
                    FOREIGN KEY(resource_type_id) REFERENCES resource_types(id) ON DELETE CASCADE,
                    FOREIGN KEY(capability_id) REFERENCES resource_capabilities(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS resource_type_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_resource_type_id INTEGER NOT NULL,
                    component_resource_type_id INTEGER NOT NULL,
                    quantity REAL NOT NULL DEFAULT 1,
                    unit TEXT NOT NULL DEFAULT 'each',
                    required INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT '',
                    UNIQUE(parent_resource_type_id, component_resource_type_id),
                    CHECK(parent_resource_type_id != component_resource_type_id),
                    FOREIGN KEY(parent_resource_type_id) REFERENCES resource_types(id) ON DELETE CASCADE,
                    FOREIGN KEY(component_resource_type_id) REFERENCES resource_types(id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS resource_type_fema_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_type_id INTEGER NOT NULL,
                    nims_name TEXT NOT NULL DEFAULT '',
                    discipline TEXT NOT NULL DEFAULT '',
                    type_code TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT '',
                    reference_url TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    typed_level TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(resource_type_id) REFERENCES resource_types(id) ON DELETE CASCADE
                );
                """
            )

            # Earlier versions of this foundation module created fewer columns.
            # Add missing columns so existing master.db files continue to work.
            self._ensure_columns(
                conn,
                "resource_types",
                {
                    "is_kit_cache": "INTEGER NOT NULL DEFAULT 0",
                    "is_consumable": "INTEGER NOT NULL DEFAULT 0",
                    "created_by": "TEXT NOT NULL DEFAULT ''",
                    "updated_by": "TEXT NOT NULL DEFAULT ''",
                },
            )
            self._ensure_columns(
                conn,
                "resource_capabilities",
                {"notes": "TEXT NOT NULL DEFAULT ''"},
            )
            self._ensure_columns(
                conn,
                "resource_type_components",
                {"required": "INTEGER NOT NULL DEFAULT 1"},
            )
            self._ensure_columns(
                conn,
                "resource_type_fema_mappings",
                {
                    "nims_name": "TEXT NOT NULL DEFAULT ''",
                    "discipline": "TEXT NOT NULL DEFAULT ''",
                    "type_code": "TEXT NOT NULL DEFAULT ''",
                    "kind": "TEXT NOT NULL DEFAULT ''",
                    "reference_url": "TEXT NOT NULL DEFAULT ''",
                    "notes": "TEXT NOT NULL DEFAULT ''",
                    "typed_level": "TEXT NOT NULL DEFAULT ''",
                },
            )
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_resource_types_search
                    ON resource_types(name, planning_display_name, category, source, owner_agency);
                CREATE INDEX IF NOT EXISTS idx_resource_type_aliases_alias
                    ON resource_type_aliases(alias);
                CREATE INDEX IF NOT EXISTS idx_resource_capabilities_search
                    ON resource_capabilities(name, category, aliases);
                CREATE INDEX IF NOT EXISTS idx_resource_type_components_parent
                    ON resource_type_components(parent_resource_type_id);
                """
            )

    def _ensure_columns(
        self, conn: sqlite3.Connection, table_name: str, columns: dict[str, str]
    ) -> None:
        """Add missing columns to an existing table.

        SQLite supports simple ``ALTER TABLE ADD COLUMN`` statements, which is
        enough for these additive master-data fields.
        """

        existing = {
            row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")
        }
        for column_name, ddl in columns.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    # ------------------------------------------------------------------
    # Resource type queries and commands
    # ------------------------------------------------------------------
    def list_resource_types(
        self,
        search_text: str = "",
        include_inactive: bool = False,
        category: str = "All",
        source: str = "All",
        active_filter: str = "Active",
    ) -> list[dict[str, Any]]:
        """Return rows for the main Resource Type Library table."""

        where: list[str] = []
        params: list[Any] = []
        if active_filter == "Active" and not include_inactive:
            where.append("rt.is_active = 1")
        elif active_filter == "Inactive":
            where.append("rt.is_active = 0")
        if category and category != "All":
            where.append("rt.category = ?")
            params.append(category)
        if source and source != "All":
            where.append("rt.source = ?")
            params.append(source)
        if search_text.strip():
            like = f"%{search_text.strip().lower()}%"
            where.append(self._resource_type_search_clause())
            params.extend([like] * 13)
        sql = """
            SELECT rt.*,
                   COALESCE((
                       SELECT group_concat(c.name, ', ')
                       FROM resource_type_capabilities rtc
                       JOIN resource_capabilities c ON c.id = rtc.capability_id
                       WHERE rtc.resource_type_id = rt.id
                   ), '') AS capabilities,
                   COALESCE((
                       SELECT COUNT(*)
                       FROM resource_type_components comp
                       WHERE comp.parent_resource_type_id = rt.id
                   ), 0) AS component_count
            FROM resource_types rt
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY lower(rt.name)"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_resource_type(self, resource_type_id: int) -> Optional[ResourceType]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resource_types WHERE id = ?", (resource_type_id,)
            ).fetchone()
            return self._resource_type_from_row(conn, row) if row else None

    def get_resource_type_by_name(self, name: str) -> Optional[ResourceType]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resource_types WHERE lower(name) = lower(?)", (name,)
            ).fetchone()
            return self._resource_type_from_row(conn, row) if row else None

    def save_resource_type(self, resource_type: ResourceType) -> int:
        """Create or update a resource type and its simple child records."""

        self._validate_resource_type(resource_type)
        now = _now()
        payload = {
            "name": resource_type.name.strip(),
            "planning_display_name": resource_type.planning_display_name.strip(),
            "category": resource_type.category,
            "source": resource_type.source,
            "owner_agency": resource_type.owner_agency.strip(),
            "description": resource_type.description.strip(),
            "default_unit": resource_type.default_unit.strip() or "each",
            "typical_quantity": float(resource_type.typical_quantity),
            "typical_team_size": resource_type.typical_team_size,
            "is_kit_cache": int(resource_type.is_kit_cache),
            "is_consumable": int(resource_type.is_consumable),
            "is_active": int(resource_type.is_active),
            "notes": resource_type.notes.strip(),
            "updated_by": resource_type.updated_by.strip(),
            "updated_at": now,
        }
        with self._connect() as conn:
            if resource_type.id is None:
                payload["created_by"] = resource_type.created_by.strip()
                payload["created_at"] = now
                columns = ", ".join(payload)
                placeholders = ", ".join("?" for _ in payload)
                cur = conn.execute(
                    f"INSERT INTO resource_types ({columns}) VALUES ({placeholders})",
                    tuple(payload.values()),
                )
                resource_type_id = int(cur.lastrowid)
            else:
                assignments = ", ".join(f"{column} = ?" for column in payload)
                conn.execute(
                    f"UPDATE resource_types SET {assignments} WHERE id = ?",
                    tuple(payload.values()) + (resource_type.id,),
                )
                resource_type_id = int(resource_type.id)
            self.replace_aliases(resource_type_id, resource_type.aliases, conn)
            self.set_resource_type_capabilities(
                resource_type_id, resource_type.capability_ids, conn
            )
            self.replace_fema_mappings(resource_type_id, resource_type.fema_mappings, conn)
            return resource_type_id

    def clone_resource_type(self, resource_type_id: int) -> int:
        """Copy a resource type, including aliases/capabilities/mappings/components."""

        original = self.get_resource_type(resource_type_id)
        if original is None:
            raise ValueError("Resource type not found")
        original.id = None
        original.name = self._next_copy_name(original.name)
        original.planning_display_name = (
            f"{original.planning_display_name} Copy".strip()
            if original.planning_display_name
            else original.name
        )
        original.created_at = ""
        original.updated_at = ""
        components = list(original.components)
        original.components = []
        new_id = self.save_resource_type(original)
        for component in components:
            component.id = None
            component.parent_resource_type_id = new_id
            self.add_component(component)
        return new_id

    def deactivate_resource_type(self, resource_type_id: int) -> None:
        self.set_resource_type_active(resource_type_id, False)

    def activate_resource_type(self, resource_type_id: int) -> None:
        self.set_resource_type_active(resource_type_id, True)

    def set_resource_type_active(self, resource_type_id: int, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE resource_types SET is_active = ?, updated_at = ? WHERE id = ?",
                (int(active), _now(), resource_type_id),
            )

    def replace_aliases(
        self,
        resource_type_id: int,
        aliases: Iterable[str],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        owns_connection = conn is None
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute(
                "DELETE FROM resource_type_aliases WHERE resource_type_id = ?",
                (resource_type_id,),
            )
            for alias in self._clean_strings(aliases):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO resource_type_aliases (resource_type_id, alias)
                    VALUES (?, ?)
                    """,
                    (resource_type_id, alias),
                )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()

    # ------------------------------------------------------------------
    # Capability queries and commands
    # ------------------------------------------------------------------
    def list_capabilities(
        self, search_text: str = "", include_inactive: bool = False
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if not include_inactive:
            where.append("is_active = 1")
        if search_text.strip():
            like = f"%{search_text.strip().lower()}%"
            where.append(
                "(lower(name) LIKE ? OR lower(category) LIKE ? OR lower(description) LIKE ? OR lower(aliases) LIKE ? OR lower(notes) LIKE ?)"
            )
            params.extend([like] * 5)
        sql = "SELECT * FROM resource_capabilities"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY lower(name)"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_capability(self, capability_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resource_capabilities WHERE id = ?", (capability_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_capability_by_name(self, name: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resource_capabilities WHERE lower(name) = lower(?)", (name,)
            ).fetchone()
            return dict(row) if row else None

    def save_capability(self, capability: ResourceCapability) -> int:
        if not capability.name.strip():
            raise ValueError("Capability name is required")
        now = _now()
        payload = {
            "name": capability.name.strip(),
            "category": capability.category.strip(),
            "description": capability.description.strip(),
            "aliases": "; ".join(self._clean_strings(capability.aliases)),
            "is_active": int(capability.is_active),
            "notes": capability.notes.strip(),
            "updated_at": now,
        }
        with self._connect() as conn:
            if capability.id is None:
                payload["created_at"] = now
                columns = ", ".join(payload)
                placeholders = ", ".join("?" for _ in payload)
                cur = conn.execute(
                    f"INSERT INTO resource_capabilities ({columns}) VALUES ({placeholders})",
                    tuple(payload.values()),
                )
                return int(cur.lastrowid)
            assignments = ", ".join(f"{column} = ?" for column in payload)
            conn.execute(
                f"UPDATE resource_capabilities SET {assignments} WHERE id = ?",
                tuple(payload.values()) + (capability.id,),
            )
            return int(capability.id)

    def deactivate_capability(self, capability_id: int) -> None:
        self.set_capability_active(capability_id, False)

    def activate_capability(self, capability_id: int) -> None:
        self.set_capability_active(capability_id, True)

    def set_capability_active(self, capability_id: int, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE resource_capabilities SET is_active = ?, updated_at = ? WHERE id = ?",
                (int(active), _now(), capability_id),
            )

    def set_resource_type_capabilities(
        self,
        resource_type_id: int,
        capability_ids: Iterable[int],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        owns_connection = conn is None
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute(
                "DELETE FROM resource_type_capabilities WHERE resource_type_id = ?",
                (resource_type_id,),
            )
            for capability_id in sorted({int(cid) for cid in capability_ids}):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO resource_type_capabilities
                    (resource_type_id, capability_id) VALUES (?, ?)
                    """,
                    (resource_type_id, capability_id),
                )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()

    # ------------------------------------------------------------------
    # Components and FEMA/NIMS mappings
    # ------------------------------------------------------------------
    def list_components(self, resource_type_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.*, rt.name AS component_name, rt.category AS component_category
                FROM resource_type_components c
                JOIN resource_types rt ON rt.id = c.component_resource_type_id
                WHERE c.parent_resource_type_id = ?
                ORDER BY lower(rt.name)
                """,
                (resource_type_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def replace_components(
        self, resource_type_id: int, components: Iterable[ResourceTypeComponent]
    ) -> None:
        """Replace all kit/cache component rows for a resource type."""

        with self._connect() as conn:
            conn.execute(
                "DELETE FROM resource_type_components WHERE parent_resource_type_id = ?",
                (resource_type_id,),
            )
            for component in components:
                component.parent_resource_type_id = resource_type_id
                self._validate_component(component)
                if self._would_create_cycle(conn, resource_type_id, component.component_resource_type_id):
                    raise ValueError(
                        "Component would create a circular resource type reference"
                    )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO resource_type_components
                    (parent_resource_type_id, component_resource_type_id, quantity, unit, required, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resource_type_id,
                        component.component_resource_type_id,
                        float(component.quantity),
                        component.unit.strip() or "each",
                        int(component.required),
                        component.notes.strip(),
                    ),
                )

    def add_component(self, component: ResourceTypeComponent) -> int:
        self._validate_component(component)
        with self._connect() as conn:
            if self._would_create_cycle(
                conn,
                component.parent_resource_type_id,
                component.component_resource_type_id,
            ):
                raise ValueError("Component would create a circular resource type reference")
            cur = conn.execute(
                """
                INSERT INTO resource_type_components
                    (parent_resource_type_id, component_resource_type_id, quantity, unit, required, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(parent_resource_type_id, component_resource_type_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    unit = excluded.unit,
                    required = excluded.required,
                    notes = excluded.notes
                """,
                (
                    component.parent_resource_type_id,
                    component.component_resource_type_id,
                    float(component.quantity),
                    component.unit.strip() or "each",
                    int(component.required),
                    component.notes.strip(),
                ),
            )
            return int(cur.lastrowid or 0)

    def remove_component(self, component_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM resource_type_components WHERE id = ?", (component_id,))

    def would_create_cycle(self, parent_id: int, child_id: int) -> bool:
        with self._connect() as conn:
            return self._would_create_cycle(conn, parent_id, child_id)

    def replace_fema_mappings(
        self,
        resource_type_id: int,
        mappings: Iterable[FemaNimsMapping],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        owns_connection = conn is None
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute(
                "DELETE FROM resource_type_fema_mappings WHERE resource_type_id = ?",
                (resource_type_id,),
            )
            for mapping in mappings:
                conn.execute(
                    """
                    INSERT INTO resource_type_fema_mappings
                    (resource_type_id, nims_name, discipline, type_code, kind, reference_url, notes, typed_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resource_type_id,
                        mapping.nims_name.strip(),
                        mapping.discipline.strip(),
                        mapping.type_code.strip(),
                        mapping.kind.strip(),
                        mapping.reference_url.strip(),
                        mapping.notes.strip(),
                        mapping.typed_level.strip(),
                    ),
                )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()

    def list_fema_mappings(self, resource_type_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM resource_type_fema_mappings
                WHERE resource_type_id = ?
                ORDER BY lower(nims_name), lower(type_code)
                """,
                (resource_type_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Smart search support
    # ------------------------------------------------------------------
    def search_resource_types(self, text: str, limit: int = 20) -> list[ResourceTypeSearchResult]:
        """Search all fields needed by the free-text ResourceTypeSearchBox."""

        query = text.strip().lower()
        if not query:
            return []
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT rt.id, rt.name, rt.planning_display_name,
                       rt.category, rt.source, rt.owner_agency,
                       CASE
                         WHEN lower(rt.name) LIKE ? THEN 'name'
                         WHEN lower(rt.planning_display_name) LIKE ? THEN 'display name'
                         WHEN lower(rt.category) LIKE ? THEN 'category'
                         WHEN lower(rt.source) LIKE ? THEN 'source'
                         WHEN lower(rt.owner_agency) LIKE ? THEN 'owner agency'
                         WHEN EXISTS (SELECT 1 FROM resource_type_aliases a
                                      WHERE a.resource_type_id = rt.id AND lower(a.alias) LIKE ?) THEN 'alias'
                         WHEN EXISTS (SELECT 1 FROM resource_type_capabilities rtc
                                      JOIN resource_capabilities c ON c.id = rtc.capability_id
                                      WHERE rtc.resource_type_id = rt.id
                                        AND (lower(c.name) LIKE ? OR lower(c.category) LIKE ? OR lower(c.aliases) LIKE ?)) THEN 'capability'
                         ELSE 'FEMA/NIMS mapping'
                       END AS matched_on
                FROM resource_types rt
                WHERE rt.is_active = 1 AND """
                + self._resource_type_search_clause()
                + """
                ORDER BY lower(rt.name)
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
                    *([like] * 13),
                    limit,
                ),
            ).fetchall()
        return [
            ResourceTypeSearchResult(
                resource_type_id=int(row["id"]),
                resource_type_text=row["planning_display_name"] or row["name"],
                category=row["category"],
                source=row["source"],
                owner_agency=row["owner_agency"],
                matched_on=row["matched_on"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resource_type_search_clause(self) -> str:
        return """
        (lower(rt.name) LIKE ? OR lower(rt.planning_display_name) LIKE ?
         OR lower(rt.category) LIKE ? OR lower(rt.source) LIKE ?
         OR lower(rt.owner_agency) LIKE ?
         OR EXISTS (SELECT 1 FROM resource_type_aliases a
                    WHERE a.resource_type_id = rt.id AND lower(a.alias) LIKE ?)
         OR EXISTS (SELECT 1 FROM resource_type_capabilities rtc
                    JOIN resource_capabilities c ON c.id = rtc.capability_id
                    WHERE rtc.resource_type_id = rt.id
                      AND (lower(c.name) LIKE ? OR lower(c.category) LIKE ? OR lower(c.aliases) LIKE ?))
         OR EXISTS (SELECT 1 FROM resource_type_fema_mappings fm
                    WHERE fm.resource_type_id = rt.id
                      AND (lower(fm.kind) LIKE ? OR lower(fm.type_code) LIKE ?
                           OR lower(fm.nims_name) LIKE ? OR lower(fm.discipline) LIKE ?)))
        """

    def _resource_type_from_row(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> ResourceType:
        resource_type_id = int(row["id"])
        aliases = [
            alias_row["alias"]
            for alias_row in conn.execute(
                "SELECT alias FROM resource_type_aliases WHERE resource_type_id = ? ORDER BY alias",
                (resource_type_id,),
            ).fetchall()
        ]
        capability_ids = [
            int(cap_row["capability_id"])
            for cap_row in conn.execute(
                "SELECT capability_id FROM resource_type_capabilities WHERE resource_type_id = ?",
                (resource_type_id,),
            ).fetchall()
        ]
        components = [
            ResourceTypeComponent(
                id=int(component_row["id"]),
                parent_resource_type_id=int(component_row["parent_resource_type_id"]),
                component_resource_type_id=int(component_row["component_resource_type_id"]),
                quantity=float(component_row["quantity"]),
                unit=component_row["unit"],
                required=bool(component_row["required"]),
                notes=component_row["notes"],
                component_name=component_row["component_name"],
                component_category=component_row["component_category"],
            )
            for component_row in conn.execute(
                """
                SELECT c.*, rt.name AS component_name, rt.category AS component_category
                FROM resource_type_components c
                JOIN resource_types rt ON rt.id = c.component_resource_type_id
                WHERE c.parent_resource_type_id = ?
                ORDER BY lower(rt.name)
                """,
                (resource_type_id,),
            ).fetchall()
        ]
        mappings = [
            FemaNimsMapping(
                id=int(mapping_row["id"]),
                resource_type_id=resource_type_id,
                nims_name=mapping_row["nims_name"],
                discipline=mapping_row["discipline"],
                type_code=mapping_row["type_code"],
                kind=mapping_row["kind"],
                reference_url=mapping_row["reference_url"],
                notes=mapping_row["notes"],
                typed_level=mapping_row["typed_level"],
            )
            for mapping_row in conn.execute(
                "SELECT * FROM resource_type_fema_mappings WHERE resource_type_id = ?",
                (resource_type_id,),
            ).fetchall()
        ]
        return ResourceType(
            id=resource_type_id,
            name=row["name"],
            planning_display_name=row["planning_display_name"],
            category=row["category"],
            source=row["source"],
            owner_agency=row["owner_agency"],
            description=row["description"],
            default_unit=row["default_unit"],
            typical_quantity=float(row["typical_quantity"]),
            typical_team_size=row["typical_team_size"],
            is_kit_cache=bool(row["is_kit_cache"]),
            is_consumable=bool(row["is_consumable"]),
            is_active=bool(row["is_active"]),
            notes=row["notes"],
            aliases=aliases,
            capability_ids=capability_ids,
            components=components,
            fema_mappings=mappings,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            updated_by=row["updated_by"],
        )

    def _validate_resource_type(self, resource_type: ResourceType) -> None:
        if not resource_type.name.strip():
            raise ValueError("Name is required.")
        if not resource_type.category or resource_type.category not in RESOURCE_CATEGORIES:
            raise ValueError("Category is required and must be a supported value.")
        if not resource_type.source or resource_type.source not in RESOURCE_SOURCES:
            raise ValueError("Source is required and must be a supported value.")
        if float(resource_type.typical_quantity) < 0:
            raise ValueError("Typical quantity cannot be negative.")

    def _validate_component(self, component: ResourceTypeComponent) -> None:
        if component.parent_resource_type_id == component.component_resource_type_id:
            raise ValueError("A resource type cannot contain itself as a component.")
        if float(component.quantity) <= 0:
            raise ValueError("Component quantity must be greater than zero.")

    def _would_create_cycle(
        self, conn: sqlite3.Connection, parent_id: int, child_id: int
    ) -> bool:
        if parent_id == child_id:
            return True
        to_visit = [child_id]
        seen: set[int] = set()
        while to_visit:
            current = to_visit.pop()
            if current == parent_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            rows = conn.execute(
                """
                SELECT component_resource_type_id
                FROM resource_type_components
                WHERE parent_resource_type_id = ?
                """,
                (current,),
            ).fetchall()
            to_visit.extend(int(row[0]) for row in rows)
        return False

    def _next_copy_name(self, base_name: str) -> str:
        candidate = f"{base_name} Copy"
        with self._connect() as conn:
            existing = {
                row["name"].lower()
                for row in conn.execute("SELECT name FROM resource_types").fetchall()
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


# ---------------------------------------------------------------------------
# API-backed repository (MongoDB via SARApp server)
# ---------------------------------------------------------------------------

class ApiResourceTypeRepository:
    """Drop-in replacement for ResourceTypeRepository that calls the FastAPI server."""

    def list_resource_types(
        self,
        search_text: str = "",
        include_inactive: bool = False,
        category: str = "All",
        source: str = "All",
        active_filter: str = "Active",
    ) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        params: dict[str, Any] = {"active_filter": active_filter}
        if search_text:
            params["search_text"] = search_text
        if category and category != "All":
            params["category"] = category
        if source and source != "All":
            params["source"] = source
        if include_inactive:
            params["include_inactive"] = True
        return api_client.get("/api/resource-types", params=params) or []

    def search_resource_types(self, text: str, limit: int = 20) -> list[ResourceTypeSearchResult]:
        from utils.api_client import api_client
        if not text.strip():
            return []
        data = api_client.get(
            "/api/resource-types/search",
            params={"q": text, "limit": limit},
        ) or []
        return [
            ResourceTypeSearchResult(
                resource_type_id=d.get("resource_type_id"),
                resource_type_text=d.get("resource_type_text", ""),
                category=d.get("category", ""),
                source=d.get("source", ""),
                owner_agency=d.get("owner_agency", ""),
                matched_on=d.get("matched_on", ""),
            )
            for d in data
        ]

    def get_resource_type(self, resource_type_id: int) -> Optional[ResourceType]:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                return None
            raise
        return _api_doc_to_resource_type(doc) if doc else None

    def get_resource_type_by_name(self, name: str) -> Optional[ResourceType]:
        from utils.api_client import api_client
        docs = api_client.get(
            "/api/resource-types",
            params={"search_text": name, "active_filter": "All"},
        ) or []
        for d in docs:
            if (d.get("name") or "").lower() == name.lower():
                return _api_doc_to_resource_type(d)
        return None

    def save_resource_type(self, resource_type: ResourceType) -> int:
        from utils.api_client import api_client
        payload = _resource_type_to_api_doc(resource_type)
        if resource_type.id is None:
            result = api_client.post("/api/resource-types", json=payload)
        else:
            result = api_client.put(f"/api/resource-types/{resource_type.id}", json=payload)
        return int(result["resource_type_id"])

    def replace_components(
        self, resource_type_id: int, components: list[ResourceTypeComponent]
    ) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/{resource_type_id}/components",
            json={"components": [_component_to_dict(c) for c in components]},
        )

    def clone_resource_type(self, resource_type_id: int) -> int:
        from utils.api_client import api_client
        result = api_client.post(f"/api/resource-types/{resource_type_id}/clone")
        return int(result["resource_type_id"])

    def deactivate_resource_type(self, resource_type_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/{resource_type_id}/active",
            json={"active": False},
        )

    def activate_resource_type(self, resource_type_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/{resource_type_id}/active",
            json={"active": True},
        )

    # Alias for windows that call set_resource_type_active directly
    def set_resource_type_active(self, resource_type_id: int, active: bool) -> None:
        if active:
            self.activate_resource_type(resource_type_id)
        else:
            self.deactivate_resource_type(resource_type_id)

    # ------------------------------------------------------------------
    # Capabilities

    def list_capabilities(
        self,
        filters: Optional[dict[str, Any]] = None,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        params: dict[str, Any] = {}
        if include_inactive:
            params["include_inactive"] = True
        f = filters or {}
        if f.get("category") and f["category"] != "All":
            params["category"] = f["category"]
        return api_client.get("/api/resource-types/capabilities", params=params) or []

    def get_capability(self, capability_id: int) -> Optional[dict[str, Any]]:
        caps = self.list_capabilities(include_inactive=True)
        return next((c for c in caps if c.get("id") == capability_id), None)

    def get_capability_by_name(self, name: str) -> Optional[dict[str, Any]]:
        caps = self.list_capabilities(include_inactive=True)
        return next((c for c in caps if (c.get("name") or "").lower() == name.lower()), None)

    def save_capability(self, capability: ResourceCapability) -> int:
        from utils.api_client import api_client
        payload: dict[str, Any] = {
            "name": capability.name,
            "category": capability.category,
            "description": capability.description,
            "aliases": list(capability.aliases),
            "is_active": capability.is_active,
            "notes": capability.notes,
        }
        if capability.id is not None:
            payload["capability_id"] = str(capability.id)
        result = api_client.post("/api/resource-types/capabilities/save", json=payload)
        return int(result["id"])

    def deactivate_capability(self, capability_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/capabilities/{capability_id}/active",
            json={"active": False},
        )

    def activate_capability(self, capability_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/capabilities/{capability_id}/active",
            json={"active": True},
        )

    def set_capability_active(self, capability_id: int, active: bool) -> None:
        if active:
            self.activate_capability(capability_id)
        else:
            self.deactivate_capability(capability_id)

    def set_resource_type_capabilities(
        self,
        resource_type_id: int,
        capability_ids: list[int],
        _conn: Any = None,
    ) -> None:
        """Update the capability list on a resource type by looking up names."""
        caps = self.list_capabilities(include_inactive=True)
        cap_map = {c["id"]: c.get("name", "") for c in caps if c.get("id") is not None}
        names = [cap_map[cid] for cid in capability_ids if cid in cap_map]
        from utils.api_client import api_client
        rt_doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        if rt_doc:
            rt = _api_doc_to_resource_type(rt_doc)
            rt.capability_ids = capability_ids
            rt.id = resource_type_id
            payload = _resource_type_to_api_doc(rt)
            payload["capability_names"] = names
            api_client.put(f"/api/resource-types/{resource_type_id}", json=payload)

    # ------------------------------------------------------------------
    # Components (list / add / remove — used by component editor dialogs)

    def list_components(self, resource_type_id: int) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError:
            return []
        return list(doc.get("components") or []) if doc else []

    def add_component(self, component: ResourceTypeComponent) -> int:
        existing = self.list_components(component.parent_resource_type_id)
        existing.append(_component_to_dict(component))
        self.replace_components(component.parent_resource_type_id, [
            ResourceTypeComponent(
                parent_resource_type_id=component.parent_resource_type_id,
                component_resource_type_id=c.get("component_resource_type_id", 0),
                quantity=c.get("quantity", 1.0),
                unit=c.get("unit", "each"),
                notes=c.get("notes", ""),
                required=c.get("required", True),
            )
            for c in existing
        ])
        return len(existing)

    def remove_component(self, component_id: int) -> None:
        pass  # Components are replaced wholesale; individual remove not needed by UI

    def would_create_cycle(self, parent_id: int, child_id: int) -> bool:
        return False  # Cycle detection deferred to server-side validation

    def replace_aliases(
        self,
        resource_type_id: int,
        aliases: list[str],
        _conn: Any = None,
    ) -> None:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError:
            return
        if not doc:
            return
        rt = _api_doc_to_resource_type(doc)
        rt.aliases = aliases
        rt.id = resource_type_id
        api_client.put(f"/api/resource-types/{resource_type_id}", json=_resource_type_to_api_doc(rt))

    def replace_fema_mappings(
        self,
        resource_type_id: int,
        mappings: list[FemaNimsMapping],
        _conn: Any = None,
    ) -> None:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError:
            return
        if not doc:
            return
        rt = _api_doc_to_resource_type(doc)
        rt.fema_mappings = mappings
        rt.id = resource_type_id
        api_client.put(f"/api/resource-types/{resource_type_id}", json=_resource_type_to_api_doc(rt))


def _to_int_id(id_str: str) -> Optional[int]:
    try:
        return int(id_str) if id_str else None
    except (ValueError, TypeError):
        return None


def _api_doc_to_resource_type(doc: dict[str, Any]) -> ResourceType:
    rt_id = _to_int_id(str(doc.get("resource_type_id") or doc.get("id") or ""))
    return ResourceType(
        id=rt_id,
        name=doc.get("name", ""),
        planning_display_name=doc.get("planning_display_name", ""),
        category=doc.get("category", "Other"),
        source=doc.get("source", "AHJ Custom"),
        owner_agency=doc.get("owner_agency", ""),
        description=doc.get("description", ""),
        default_unit=doc.get("default_unit", "each"),
        typical_quantity=float(doc.get("typical_quantity") or 1.0),
        typical_team_size=doc.get("typical_team_size"),
        is_kit_cache=bool(doc.get("is_kit_cache", False)),
        is_consumable=bool(doc.get("is_consumable", False)),
        is_active=bool(doc.get("is_active", True)),
        notes=doc.get("notes", ""),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        created_by=doc.get("created_by", ""),
        updated_by=doc.get("updated_by", ""),
        aliases=list(doc.get("aliases") or []),
        capability_ids=list(doc.get("capability_ids") or []),
        components=[
            ResourceTypeComponent(
                parent_resource_type_id=rt_id or 0,
                component_resource_type_id=int(c.get("component_resource_type_id") or 0),
                quantity=float(c.get("quantity") or 1.0),
                unit=c.get("unit", "each"),
                notes=c.get("notes", ""),
                required=bool(c.get("required", True)),
            )
            for c in (doc.get("components") or [])
        ],
        fema_mappings=[
            FemaNimsMapping(
                resource_type_id=rt_id or 0,
                nims_name=m.get("nims_name", ""),
                discipline=m.get("discipline", ""),
                type_code=m.get("type_code", ""),
                kind=m.get("kind", ""),
                reference_url=m.get("reference_url", ""),
                notes=m.get("notes", ""),
                typed_level=m.get("typed_level", ""),
            )
            for m in (doc.get("fema_mappings") or [])
        ],
    )


def _resource_type_to_api_doc(rt: ResourceType) -> dict[str, Any]:
    return {
        "name": rt.name,
        "planning_display_name": rt.planning_display_name,
        "category": rt.category,
        "source": rt.source,
        "owner_agency": rt.owner_agency,
        "description": rt.description,
        "default_unit": rt.default_unit,
        "typical_quantity": float(rt.typical_quantity),
        "typical_team_size": rt.typical_team_size,
        "is_kit_cache": rt.is_kit_cache,
        "is_consumable": rt.is_consumable,
        "is_active": rt.is_active,
        "notes": rt.notes,
        "created_by": rt.created_by,
        "updated_by": rt.updated_by,
        "aliases": list(rt.aliases),
        "capability_ids": list(rt.capability_ids),
        "capability_names": [],  # resolved server-side via set_resource_type_capabilities
        "components": [_component_to_dict(c) for c in rt.components],
        "fema_mappings": [
            {
                "nims_name": m.nims_name,
                "discipline": m.discipline,
                "type_code": m.type_code,
                "kind": m.kind,
                "reference_url": m.reference_url,
                "notes": m.notes,
                "typed_level": m.typed_level,
            }
            for m in rt.fema_mappings
        ],
    }


def _component_to_dict(c: ResourceTypeComponent) -> dict[str, Any]:
    return {
        "component_resource_type_id": c.component_resource_type_id,
        "quantity": float(c.quantity),
        "unit": c.unit,
        "notes": c.notes,
        "required": c.required,
    }
