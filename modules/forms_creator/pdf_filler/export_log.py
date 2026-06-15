"""Database helpers for PDF export history."""

from __future__ import annotations

import json
from typing import Any


_FORM_EXPORTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    form_name TEXT,
    template_path TEXT,
    mapping_path TEXT,
    output_path TEXT,
    filled_by TEXT,
    exported_at TEXT DEFAULT (datetime('now')),
    warnings TEXT
);
"""


def _ensure_schema(db_conn: Any) -> None:
    cursor = db_conn.cursor()
    cursor.execute(_FORM_EXPORTS_SCHEMA)
    db_conn.commit()


def log_export(
    db_conn: Any,
    form_name: str,
    template_path: str,
    mapping_path: str,
    output_path: str,
    filled_by: str,
    incident_id: str,
    warnings: list[str],
) -> int:
    """Insert a PDF export audit row and return the created record id."""
    _ensure_schema(db_conn)
    cursor = db_conn.cursor()
    cursor.execute(
        """
        INSERT INTO form_exports (
            incident_id, form_name, template_path, mapping_path,
            output_path, filled_by, warnings
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            form_name,
            template_path,
            mapping_path,
            output_path,
            filled_by,
            json.dumps(warnings or []),
        ),
    )
    db_conn.commit()
    return int(cursor.lastrowid)


def get_exports(db_conn: Any, incident_id: str) -> list[dict[str, Any]]:
    """Return PDF export history for an incident, newest first."""
    _ensure_schema(db_conn)
    cursor = db_conn.cursor()
    cursor.execute(
        """
        SELECT id, incident_id, form_name, template_path, mapping_path,
               output_path, filled_by, exported_at, warnings
        FROM form_exports
        WHERE incident_id = ?
        ORDER BY datetime(exported_at) DESC, id DESC
        """,
        (incident_id,),
    )
    columns = [item[0] for item in cursor.description or []]
    rows: list[dict[str, Any]] = []
    for record in cursor.fetchall():
        row = dict(zip(columns, record))
        try:
            row["warnings"] = json.loads(row.get("warnings") or "[]")
        except json.JSONDecodeError:
            row["warnings"] = []
        rows.append(row)
    return rows
