"""Master-data repository for Units and Organizations.

This module owns schema creation and CRUD operations for:
- organizations and nested hierarchy
- organization types
- rank structures and template duplication
- rank entries and organization overrides

All persistence is against ``master.db`` only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Any, Callable, Iterable

from utils.context import master_db


@dataclass(slots=True)
class DeleteResult:
    """Outcome details when attempting to delete an organization."""

    deleted: bool
    message: str


class UnitsOrganizationsRepository:
    """SQLite repository for the Units and Organizations master-data editor."""

    def __init__(self, conn_factory: Callable[[], sqlite3.Connection] = master_db) -> None:
        self._conn_factory = conn_factory
        self.ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = self._conn_factory()
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def ensure_schema(self) -> None:
        """Create required tables and indexes when missing."""
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organization_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rank_structures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    organization_type_id INTEGER,
                    based_on_rank_structure_id INTEGER,
                    is_template INTEGER NOT NULL DEFAULT 1,
                    is_system_template INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (organization_type_id) REFERENCES organization_types(id),
                    FOREIGN KEY (based_on_rank_structure_id) REFERENCES rank_structures(id)
                );

                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    short_name TEXT DEFAULT '',
                    parent_organization_id INTEGER,
                    organization_type_id INTEGER NOT NULL,
                    default_rank_structure_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT DEFAULT '',
                    external_id TEXT,
                    callsign_prefix TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (parent_organization_id) REFERENCES organizations(id) ON DELETE RESTRICT,
                    FOREIGN KEY (organization_type_id) REFERENCES organization_types(id),
                    FOREIGN KEY (default_rank_structure_id) REFERENCES rank_structures(id)
                );

                CREATE TABLE IF NOT EXISTS ranks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rank_structure_id INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    rank_code TEXT NOT NULL,
                    rank_name TEXT NOT NULL,
                    short_display TEXT DEFAULT '',
                    grade_code TEXT,
                    insignia_path TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (rank_structure_id) REFERENCES rank_structures(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS organization_rank_structure_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL,
                    rank_structure_id INTEGER NOT NULL,
                    override_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY (rank_structure_id) REFERENCES rank_structures(id)
                );

                CREATE TABLE IF NOT EXISTS organization_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER,
                    action TEXT NOT NULL,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rank_structure_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rank_structure_id INTEGER,
                    action TEXT NOT NULL,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_org_parent ON organizations(parent_organization_id);
                CREATE INDEX IF NOT EXISTS idx_org_sort ON organizations(sort_order, name);
                CREATE INDEX IF NOT EXISTS idx_org_active ON organizations(is_active);
                CREATE INDEX IF NOT EXISTS idx_rank_struct_sort ON rank_structures(sort_order, name);
                """
            )

            # --- Legacy schema migrations ---
            # Ensure ranks.rank_structure_id exists before creating index.
            cols = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute("PRAGMA table_info('ranks')").fetchall()}
            if 'rank_structure_id' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN rank_structure_id INTEGER")
                # Best-effort backfill from older column names if present
                legacy_cols = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute("PRAGMA table_info('ranks')").fetchall()}
                if 'structure_id' in legacy_cols:
                    conn.execute("UPDATE ranks SET rank_structure_id = structure_id WHERE rank_structure_id IS NULL")
                elif 'rank_structure' in legacy_cols:
                    conn.execute("UPDATE ranks SET rank_structure_id = rank_structure WHERE rank_structure_id IS NULL")

            # Ensure sort_order exists for ranks index
            cols = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute("PRAGMA table_info('ranks')").fetchall()}
            if 'sort_order' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ranks_structure_sort ON ranks(rank_structure_id, sort_order)")

            # Backfill additional columns used by templates for older DBs
            cols = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute("PRAGMA table_info('ranks')").fetchall()}
            if 'rank_code' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN rank_code TEXT DEFAULT ''")
            if 'rank_name' not in cols:
                # Some older schemas may have 'name' — keep it, but add 'rank_name'
                conn.execute("ALTER TABLE ranks ADD COLUMN rank_name TEXT DEFAULT ''")
                # best-effort populate from legacy column names
                legacy_cols = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in conn.execute("PRAGMA table_info('ranks')").fetchall()}
                if 'name' in legacy_cols:
                    conn.execute("UPDATE ranks SET rank_name = COALESCE(rank_name, name)")
            if 'short_display' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN short_display TEXT DEFAULT ''")
            if 'grade_code' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN grade_code TEXT")
            if 'insignia_path' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN insignia_path TEXT")
            if 'is_active' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            if 'created_at' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN created_at TEXT DEFAULT ''")
            if 'updated_at' not in cols:
                conn.execute("ALTER TABLE ranks ADD COLUMN updated_at TEXT DEFAULT ''")
            now = self._now()
            conn.execute(
                """
                INSERT INTO organization_types (name, description, is_active, sort_order, created_at, updated_at)
                SELECT 'General', 'Default organization type', 1, 0, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM organization_types)
                """,
                (now, now),
            )

            # ------------------------------------------------------------------
            # Seed common organization types (idempotent by unique name)
            # ------------------------------------------------------------------
            # Use the organization types requested by the user/team
            seed_types: list[tuple[str, str, int]] = [
                ("Air Agency", "Aviation-focused public safety or regulatory agency", 10),
                ("Ground SAR", "Ground search and rescue organizations", 20),
                ("Law Enforcement", "Police, sheriff, or patrol agencies", 30),
                ("Fire/Rescue", "Fire service and rescue organizations", 40),
                ("EMS", "Emergency medical services organizations", 50),
                ("Government", "General government organizations", 60),
                ("Volunteer Organization", "Volunteer-run organizations", 70),
                ("NGO", "Non-governmental organizations", 80),
                ("Federal", "Federal/national level organizations", 90),
                ("State", "State or provincial organizations", 100),
                ("County", "County or regional organizations", 110),
                ("Municipal", "City or municipal organizations", 120),
                ("Military", "Military organizations", 130),
                ("Private Contractor", "Private companies/contractors", 140),
                ("Amateur Radio", "Amateur radio/ARES/RACES groups", 150),
                ("Aviation Support", "Air support/aviation assistance units", 160),
                ("Communications Unit", "Radio/comms units and shops", 170),
                ("Other", "Other/uncategorized organizations", 180),
            ]
            for name, desc, sort in seed_types:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO organization_types (name, description, is_active, sort_order, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    (name, desc, sort, now, now),
                )

            # Helper to look up an organization_type_id by name
            def _org_type_id(type_name: str) -> int | None:
                row = conn.execute(
                    "SELECT id FROM organization_types WHERE name = ?",
                    (type_name,),
                ).fetchone()
                return int(row["id"]) if row else None

            # ------------------------------------------------------------------
            # Seed rank structure templates for common org types.
            # Each template insert is guarded to avoid duplicates by name when
            # marked as a system template.
            # ------------------------------------------------------------------
            def _ensure_rank_template(
                name: str,
                description: str,
                organization_type_name: str | None,
                ranks: list[tuple[int, str, str, str]],
                sort_order: int = 0,
            ) -> None:
                ot_id = _org_type_id(organization_type_name) if organization_type_name else None
                # Insert the rank structure if a system template with this name does not yet exist
                conn.execute(
                    """
                    INSERT INTO rank_structures (
                        name, description, organization_type_id, based_on_rank_structure_id,
                        is_template, is_system_template, is_active, sort_order, created_at, updated_at
                    )
                    SELECT ?, ?, ?, NULL, 1, 1, 1, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM rank_structures WHERE name = ? AND is_system_template = 1
                    )
                    """,
                    (name, description, ot_id, sort_order, now, now, name),
                )

                row = conn.execute(
                    "SELECT id FROM rank_structures WHERE name = ? AND is_system_template = 1",
                    (name,),
                ).fetchone()
                if not row:
                    return
                rs_id = int(row["id"])

                # Only seed ranks if none exist for this structure yet
                existing = conn.execute(
                    "SELECT COUNT(1) AS c FROM ranks WHERE rank_structure_id = ?",
                    (rs_id,),
                ).fetchone()["c"]
                if int(existing) == 0:
                    for order, code, title, short_disp in ranks:
                        conn.execute(
                            """
                            INSERT INTO ranks (
                                rank_structure_id, sort_order, rank_code, rank_name, short_display,
                                grade_code, insignia_path, is_active, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, 1, ?, ?)
                            """,
                            (rs_id, order, code, title, short_disp, now, now),
                        )

            # Fire Department
            _ensure_rank_template(
                name="Fire Department (Standard)",
                description="Common municipal fire service rank progression",
                organization_type_name="Fire Department",
                sort_order=10,
                ranks=[
                    (0, "FF", "Firefighter", "FF"),
                    (1, "ENG", "Engineer / Driver", "ENG"),
                    (2, "LT", "Lieutenant", "LT"),
                    (3, "CPT", "Captain", "CPT"),
                    (4, "BC", "Battalion Chief", "BC"),
                    (5, "DC", "Division Chief", "DC"),
                    (6, "AC", "Assistant Chief", "AC"),
                    (7, "DCH", "Deputy Chief", "D/Chief"),
                    (8, "CH", "Fire Chief", "Chief"),
                ],
            )

            # Law Enforcement
            _ensure_rank_template(
                name="Law Enforcement (Standard)",
                description="Typical police/sheriff rank progression",
                organization_type_name="Law Enforcement",
                sort_order=20,
                ranks=[
                    (0, "PO", "Police Officer", "Officer"),
                    (1, "SPO", "Senior Police Officer", "Sr Ofc"),
                    (2, "CPL", "Corporal", "Cpl"),
                    (3, "SGT", "Sergeant", "Sgt"),
                    (4, "LT", "Lieutenant", "Lt"),
                    (5, "CPT", "Captain", "Capt"),
                    (6, "MAJ", "Major / Commander", "Maj"),
                    (7, "DCH", "Deputy Chief", "D/Chief"),
                    (8, "CH", "Chief of Police", "Chief"),
                ],
            )

            # EMS
            _ensure_rank_template(
                name="EMS (Standard)",
                description="Common EMS rank progression",
                organization_type_name="EMS",
                sort_order=30,
                ranks=[
                    (0, "EMT", "EMT", "EMT"),
                    (1, "AEMT", "Advanced EMT", "AEMT"),
                    (2, "PM", "Paramedic", "Medic"),
                    (3, "FTO", "Field Training Officer", "FTO"),
                    (4, "SUP", "Supervisor", "Supv"),
                    (5, "CPT", "Captain", "Capt"),
                    (6, "BC", "Battalion Chief", "BC"),
                    (7, "CH", "Chief", "Chief"),
                ],
            )

            # Search and Rescue
            _ensure_rank_template(
                name="Search and Rescue (Standard)",
                description="Typical SAR team role progression",
                organization_type_name="Search and Rescue",
                sort_order=40,
                ranks=[
                    (0, "MEM", "Member", "Member"),
                    (1, "SMEM", "Senior Member", "Sr Mbr"),
                    (2, "TL", "Team Leader", "TL"),
                    (3, "OPL", "Operations Leader", "Ops Lead"),
                    (4, "PLN", "Planning Lead", "Plans"),
                    (5, "LOG", "Logistics Lead", "Log"),
                    (6, "SC", "Section Chief", "Sec Chief"),
                    (7, "IC", "Incident Commander", "IC"),
                ],
            )

            # Volunteer / NGO
            _ensure_rank_template(
                name="Volunteer / NGO (Standard)",
                description="Generic volunteer/NGO leadership progression",
                organization_type_name="Volunteer / NGO",
                sort_order=70,
                ranks=[
                    (0, "VOL", "Volunteer", "Vol"),
                    (1, "LV", "Lead Volunteer", "Lead Vol"),
                    (2, "TL", "Team Leader", "TL"),
                    (3, "COOR", "Coordinator", "Coord"),
                    (4, "MGR", "Manager", "Mgr"),
                    (5, "DIR", "Director", "Dir"),
                ],
            )

    # ---- Lookup helpers -------------------------------------------------------
    def list_organization_types(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM organization_types"
        params: list[Any] = []
        if not include_inactive:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY sort_order ASC, name COLLATE NOCASE ASC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def list_rank_structures(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        sql = (
            "SELECT rs.*, ot.name AS organization_type_name "
            "FROM rank_structures rs "
            "LEFT JOIN organization_types ot ON ot.id = rs.organization_type_id"
        )
        if not include_inactive:
            sql += " WHERE rs.is_active = 1"
        sql += " ORDER BY rs.sort_order ASC, rs.name COLLATE NOCASE ASC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def list_organizations(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        sql = (
            "SELECT o.*, p.name AS parent_name, ot.name AS organization_type_name, "
            "rs.name AS rank_structure_name "
            "FROM organizations o "
            "LEFT JOIN organizations p ON p.id = o.parent_organization_id "
            "LEFT JOIN organization_types ot ON ot.id = o.organization_type_id "
            "LEFT JOIN rank_structures rs ON rs.id = o.default_rank_structure_id"
        )
        if not include_inactive:
            sql += " WHERE o.is_active = 1"
        sql += " ORDER BY o.sort_order ASC, o.name COLLATE NOCASE ASC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def get_organization(self, organization_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (int(organization_id),)).fetchone()
            return dict(row) if row else None

    # ---- Organization type CRUD ----------------------------------------------
    def create_organization_type(self, payload: dict[str, Any]) -> int:
        now = self._now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO organization_types (
                    name, description, is_active, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    (payload.get("name") or "").strip(),
                    (payload.get("description") or "").strip(),
                    int(payload.get("is_active", 1)),
                    int(payload.get("sort_order", 0)),
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_organization_type(self, type_id: int, payload: dict[str, Any]) -> None:
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE organization_types
                SET name = ?, description = ?, is_active = ?, sort_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    (payload.get("name") or "").strip(),
                    (payload.get("description") or "").strip(),
                    int(payload.get("is_active", 1)),
                    int(payload.get("sort_order", 0)),
                    now,
                    int(type_id),
                ),
            )

    # ---- Rank structure CRUD --------------------------------------------------
    def create_rank_structure(self, payload: dict[str, Any]) -> int:
        now = self._now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO rank_structures (
                    name, description, organization_type_id, based_on_rank_structure_id,
                    is_template, is_system_template, is_active, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (payload.get("name") or "").strip(),
                    (payload.get("description") or "").strip(),
                    payload.get("organization_type_id"),
                    payload.get("based_on_rank_structure_id"),
                    int(payload.get("is_template", 1)),
                    int(payload.get("is_system_template", 0)),
                    int(payload.get("is_active", 1)),
                    int(payload.get("sort_order", 0)),
                    now,
                    now,
                ),
            )
            rank_structure_id = int(cur.lastrowid)

            for rank in payload.get("ranks", []):
                conn.execute(
                    """
                    INSERT INTO ranks (
                        rank_structure_id, sort_order, rank_code, rank_name, short_display,
                        grade_code, insignia_path, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rank_structure_id,
                        int(rank.get("sort_order", 0)),
                        (rank.get("rank_code") or "").strip(),
                        (rank.get("rank_name") or "").strip(),
                        (rank.get("short_display") or "").strip(),
                        (rank.get("grade_code") or None),
                        (rank.get("insignia_path") or None),
                        int(rank.get("is_active", 1)),
                        now,
                        now,
                    ),
                )

            self._write_rank_audit(conn, rank_structure_id, "create", None, None, payload.get("name"))
            return rank_structure_id

    def update_rank_structure(self, rank_structure_id: int, payload: dict[str, Any]) -> None:
        now = self._now()
        with self._conn() as conn:
            current = conn.execute("SELECT * FROM rank_structures WHERE id = ?", (int(rank_structure_id),)).fetchone()
            if not current:
                raise ValueError("Rank structure not found")
            conn.execute(
                """
                UPDATE rank_structures
                SET name = ?, description = ?, organization_type_id = ?, is_template = ?,
                    is_system_template = ?, is_active = ?, sort_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    (payload.get("name") or "").strip(),
                    (payload.get("description") or "").strip(),
                    payload.get("organization_type_id"),
                    int(payload.get("is_template", 1)),
                    int(payload.get("is_system_template", 0)),
                    int(payload.get("is_active", 1)),
                    int(payload.get("sort_order", 0)),
                    now,
                    int(rank_structure_id),
                ),
            )
            self._write_rank_audit(conn, int(rank_structure_id), "update", "name", current["name"], payload.get("name"))

    # ---- Rank rows CRUD ------------------------------------------------------
    def list_ranks(self, rank_structure_id: int) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ranks
                WHERE rank_structure_id = ?
                ORDER BY sort_order ASC, rank_name COLLATE NOCASE ASC
                """,
                (int(rank_structure_id),),
            ).fetchall()
            return [dict(r) for r in rows]

    def replace_ranks(self, rank_structure_id: int, ranks: Iterable[dict[str, object]]) -> None:
        now = self._now()
        with self._conn() as conn:
            conn.execute("DELETE FROM ranks WHERE rank_structure_id = ?", (int(rank_structure_id),))
            inserted = 0
            for idx, rank in enumerate(ranks):
                conn.execute(
                    """
                    INSERT INTO ranks (
                        rank_structure_id, sort_order, rank_code, rank_name, short_display,
                        grade_code, insignia_path, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(rank_structure_id),
                        int(rank.get("sort_order", idx)),
                        str(rank.get("rank_code", "")).strip(),
                        str(rank.get("rank_name", "")).strip(),
                        str(rank.get("short_display", "")).strip(),
                        (rank.get("grade_code") or None),
                        (rank.get("insignia_path") or None),
                        int(rank.get("is_active", 1)),
                        now,
                        now,
                    ),
                )
                inserted += 1
            self._write_rank_audit(conn, int(rank_structure_id), "replace_ranks", None, None, f"{inserted} rows")

    def duplicate_rank_structure(
        self,
        source_rank_structure_id: int,
        *,
        new_name: str,
        is_template: bool,
        organization_type_id: int | None = None,
    ) -> int:
        """Create a full rank structure copy including ordered rank rows."""
        now = self._now()
        with self._conn() as conn:
            source = conn.execute(
                "SELECT * FROM rank_structures WHERE id = ?", (int(source_rank_structure_id),)
            ).fetchone()
            if not source:
                raise ValueError("Source rank structure not found")

            cur = conn.execute(
                """
                INSERT INTO rank_structures (
                    name, description, organization_type_id, based_on_rank_structure_id,
                    is_template, is_system_template, is_active, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?, ?)
                """,
                (
                    new_name.strip(),
                    source["description"],
                    organization_type_id,
                    int(source_rank_structure_id),
                    int(is_template),
                    int(source["sort_order"]),
                    now,
                    now,
                ),
            )
            new_id = int(cur.lastrowid)

            rows = conn.execute(
                "SELECT * FROM ranks WHERE rank_structure_id = ? ORDER BY sort_order, rank_name COLLATE NOCASE",
                (int(source_rank_structure_id),),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO ranks (
                        rank_structure_id, sort_order, rank_code, rank_name, short_display,
                        grade_code, insignia_path, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id,
                        row["sort_order"],
                        row["rank_code"],
                        row["rank_name"],
                        row["short_display"],
                        row["grade_code"],
                        row["insignia_path"],
                        row["is_active"],
                        now,
                        now,
                    ),
                )

            self._write_rank_audit(conn, new_id, "duplicate", None, str(source_rank_structure_id), new_name)
            return new_id

    # ---- Organization CRUD ----------------------------------------------------
    def create_organization(self, payload: dict[str, Any], changed_by: str = "system") -> int:
        now = self._now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO organizations (
                    name, short_name, parent_organization_id, organization_type_id,
                    default_rank_structure_id, is_active, notes, external_id,
                    callsign_prefix, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (payload.get("name") or "").strip(),
                    (payload.get("short_name") or "").strip(),
                    payload.get("parent_organization_id"),
                    int(payload.get("organization_type_id")),
                    payload.get("default_rank_structure_id"),
                    int(payload.get("is_active", 1)),
                    (payload.get("notes") or "").strip(),
                    (payload.get("external_id") or None),
                    (payload.get("callsign_prefix") or None),
                    int(payload.get("sort_order", 0)),
                    now,
                    now,
                ),
            )
            org_id = int(cur.lastrowid)
            self._write_org_audit(conn, org_id, "create", None, None, payload.get("name"), changed_by)
            return org_id

    def update_organization(self, organization_id: int, payload: dict[str, Any], changed_by: str = "system") -> None:
        now = self._now()
        with self._conn() as conn:
            current = conn.execute("SELECT * FROM organizations WHERE id = ?", (int(organization_id),)).fetchone()
            if not current:
                raise ValueError("Organization not found")

            if payload.get("parent_organization_id"):
                parent_id = int(payload["parent_organization_id"])
                if parent_id == int(organization_id) or self._is_descendant(conn, parent_id, int(organization_id)):
                    raise ValueError("Invalid parent organization selection")

            conn.execute(
                """
                UPDATE organizations
                SET name = ?, short_name = ?, parent_organization_id = ?, organization_type_id = ?,
                    default_rank_structure_id = ?, is_active = ?, notes = ?, external_id = ?,
                    callsign_prefix = ?, sort_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    (payload.get("name") or "").strip(),
                    (payload.get("short_name") or "").strip(),
                    payload.get("parent_organization_id"),
                    int(payload.get("organization_type_id")),
                    payload.get("default_rank_structure_id"),
                    int(payload.get("is_active", 1)),
                    (payload.get("notes") or "").strip(),
                    (payload.get("external_id") or None),
                    (payload.get("callsign_prefix") or None),
                    int(payload.get("sort_order", 0)),
                    now,
                    int(organization_id),
                ),
            )
            self._write_org_audit(conn, int(organization_id), "update", "name", current["name"], payload.get("name"), changed_by)

    def delete_organization(self, organization_id: int, changed_by: str = "system") -> DeleteResult:
        """Delete an organization when safe, otherwise soft-disable it."""
        with self._conn() as conn:
            org = conn.execute("SELECT * FROM organizations WHERE id = ?", (int(organization_id),)).fetchone()
            if not org:
                return DeleteResult(False, "Organization not found.")

            child_count = conn.execute(
                "SELECT COUNT(*) FROM organizations WHERE parent_organization_id = ?",
                (int(organization_id),),
            ).fetchone()[0]
            if child_count:
                return DeleteResult(False, "Cannot delete organization that still has child organizations.")

            linked_override_count = conn.execute(
                "SELECT COUNT(*) FROM organization_rank_structure_overrides WHERE organization_id = ?",
                (int(organization_id),),
            ).fetchone()[0]
            if linked_override_count:
                conn.execute(
                    "UPDATE organizations SET is_active = 0, updated_at = ? WHERE id = ?",
                    (self._now(), int(organization_id)),
                )
                self._write_org_audit(conn, int(organization_id), "soft_delete", None, "1", "0", changed_by)
                return DeleteResult(False, "Organization has linked records; marked inactive instead.")

            conn.execute("DELETE FROM organizations WHERE id = ?", (int(organization_id),))
            self._write_org_audit(conn, int(organization_id), "delete", None, org["name"], None, changed_by)
            return DeleteResult(True, "Organization deleted.")

    def move_sort_order(self, organization_id: int, direction: int) -> None:
        """Move an organization up/down among sibling sort_order values."""
        with self._conn() as conn:
            org = conn.execute(
                "SELECT id, parent_organization_id, sort_order FROM organizations WHERE id = ?",
                (int(organization_id),),
            ).fetchone()
            if not org:
                return

            siblings = conn.execute(
                """
                SELECT id, sort_order FROM organizations
                WHERE parent_organization_id IS ?
                ORDER BY sort_order ASC, name COLLATE NOCASE ASC
                """,
                (org["parent_organization_id"],),
            ).fetchall()
            sibling_ids = [int(row["id"]) for row in siblings]
            if organization_id not in sibling_ids:
                return
            idx = sibling_ids.index(int(organization_id))
            swap_idx = idx + direction
            if swap_idx < 0 or swap_idx >= len(sibling_ids):
                return
            current_id = sibling_ids[idx]
            target_id = sibling_ids[swap_idx]
            current_sort = siblings[idx]["sort_order"]
            target_sort = siblings[swap_idx]["sort_order"]
            conn.execute("UPDATE organizations SET sort_order = ? WHERE id = ?", (target_sort, current_id))
            conn.execute("UPDATE organizations SET sort_order = ? WHERE id = ?", (current_sort, target_id))

    def upsert_override(self, organization_id: int, rank_structure_id: int, override_mode: str) -> None:
        now = self._now()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM organization_rank_structure_overrides WHERE organization_id = ?",
                (int(organization_id),),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE organization_rank_structure_overrides
                    SET rank_structure_id = ?, override_mode = ?, updated_at = ?
                    WHERE organization_id = ?
                    """,
                    (int(rank_structure_id), override_mode, now, int(organization_id)),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO organization_rank_structure_overrides (
                        organization_id, rank_structure_id, override_mode, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (int(organization_id), int(rank_structure_id), override_mode, now, now),
                )

    # ---- Private helpers ------------------------------------------------------
    def _is_descendant(self, conn: sqlite3.Connection, candidate_parent_id: int, organization_id: int) -> bool:
        """Return True when candidate_parent_id is in organization's child tree."""
        queue = [organization_id]
        visited: set[int] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            rows = conn.execute(
                "SELECT id FROM organizations WHERE parent_organization_id = ?",
                (current,),
            ).fetchall()
            for row in rows:
                child_id = int(row["id"])
                if child_id == int(candidate_parent_id):
                    return True
                queue.append(child_id)
        return False

    def _write_org_audit(
        self,
        conn: sqlite3.Connection,
        organization_id: int,
        action: str,
        field_name: str | None,
        old_value: Any,
        new_value: Any,
        changed_by: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO organization_audit_log (
                organization_id, action, field_name, old_value, new_value, changed_by, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(organization_id),
                action,
                field_name,
                None if old_value is None else str(old_value),
                None if new_value is None else str(new_value),
                changed_by,
                self._now(),
            ),
        )

    def _write_rank_audit(
        self,
        conn: sqlite3.Connection,
        rank_structure_id: int,
        action: str,
        field_name: str | None,
        old_value: Any,
        new_value: Any,
    ) -> None:
        conn.execute(
            """
            INSERT INTO rank_structure_audit_log (
                rank_structure_id, action, field_name, old_value, new_value, changed_by, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(rank_structure_id),
                action,
                field_name,
                None if old_value is None else str(old_value),
                None if new_value is None else str(new_value),
                "system",
                self._now(),
            ),
        )


__all__ = ["UnitsOrganizationsRepository", "DeleteResult"]
