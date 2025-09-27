"""Seeding and synchronization for certification catalog into SQLite.

On app init, call `sync()` to ensure the DB mirror of the hardcoded
catalog is present and up to date, including tags. This operation is
idempotent and safe to run multiple times.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable

from utils.db import get_master_conn
from utils.sqlite_helpers import enable_foreign_keys, exec_script, upsert
from modules.personnel.models.cert_catalog import CATALOG, CATALOG_VERSION


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS certification_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE,
    name TEXT,
    description TEXT,
    category TEXT,
    issuing_organization TEXT,
    parent_certification_id INTEGER NULL,
    FOREIGN KEY(parent_certification_id) REFERENCES certification_types(id)
);

-- Ensure unique index on code even if legacy table lacked the constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_certification_types_code ON certification_types(code);

CREATE TABLE IF NOT EXISTS cert_tags (
    certification_type_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY(certification_type_id, tag),
    FOREIGN KEY(certification_type_id) REFERENCES certification_types(id)
);

CREATE TABLE IF NOT EXISTS personnel_certifications (
    id INTEGER PRIMARY KEY,
    personnel_id INTEGER NOT NULL,
    certification_type_id INTEGER NOT NULL,
    level INTEGER NOT NULL DEFAULT 0,
    attachment_url TEXT NULL,
    FOREIGN KEY(certification_type_id) REFERENCES certification_types(id)
);
"""


def _get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    cur = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,))
    row = cur.fetchone()
    return (row[0] if row else default)


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    upsert(conn, "app_meta", ("key",), {"key": key, "value": value})


def _sync_catalog(conn: sqlite3.Connection) -> None:
    """Upsert all catalog entries into certification_types by `code`.

    Ensures the row has the code-defined stable `id` and attributes.
    After types are synced, tags are re-written to match the code.
    """
    for ct in CATALOG:
        upsert(
            conn,
            table="certification_types",
            key_columns=("code",),
            values={
                "id": ct.id,
                "code": ct.code,
                "name": ct.name,
                "description": ct.name,  # description mirrors name for now
                "category": ct.category,
                "issuing_organization": ct.issuing_org,
                "parent_certification_id": ct.parent_id,
            },
        )

    # Refresh tag mirror to reflect code catalog exactly
    # Delete existing tags for codes present, then insert current tags
    # Map code -> id from DB to ensure referential integrity
    code_to_id: dict[str, int] = {}
    cur = conn.execute("SELECT id, code FROM certification_types")
    for row in cur.fetchall():
        code_to_id[str(row[1])] = int(row[0])

    # Clear tags for all known types
    conn.execute("DELETE FROM cert_tags")
    for ct in CATALOG:
        type_id = code_to_id.get(ct.code)
        if type_id is None:
            continue
        for tag in ct.tags:
            conn.execute(
                "INSERT OR IGNORE INTO cert_tags (certification_type_id, tag) VALUES (?, ?)",
                (type_id, str(tag)),
            )


def sync() -> tuple[bool, str]:
    """Ensure mirror schema exists and catalog is in sync.

    Returns (changed: bool, message: str) for UI display.
    """
    conn = get_master_conn()
    enable_foreign_keys(conn)
    exec_script(conn, SCHEMA_SQL)

    prev = _get_meta(conn, "CERT_CATALOG_VERSION")
    changed = prev != CATALOG_VERSION

    _sync_catalog(conn)
    _set_meta(conn, "CERT_CATALOG_VERSION", CATALOG_VERSION)

    conn.commit()
    try:
        conn.close()
    except Exception:
        pass

    if changed:
        return True, f"Certification catalog updated to {CATALOG_VERSION}"
    return False, f"Certification catalog already at {CATALOG_VERSION}"


__all__ = ["sync"]
