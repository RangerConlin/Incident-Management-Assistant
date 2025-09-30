from __future__ import annotations

"""Read-only access to the master personnel catalog."""

import sqlite3
from typing import Callable, Iterable, List, Sequence

from utils.db import get_master_conn


class MasterPersonnelRepository:
    """Simple search interface for ``master.db`` personnel records."""

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection] | None = None):
        self._factory = connection_factory

    def _connect(self) -> sqlite3.Connection:
        if self._factory is not None:
            return self._factory()
        return get_master_conn()

    # ------------------------------------------------------------------
    def _personnel_columns(self, conn: sqlite3.Connection) -> set[str]:
        try:
            rows = conn.execute("PRAGMA table_info(personnel)").fetchall()
        except sqlite3.OperationalError:
            return set()
        # Normalize to lowercase to be resilient to schema casing differences
        return {str(row[1]).lower() for row in rows}

    @staticmethod
    def _coalesce(row: sqlite3.Row, options: Sequence[str]) -> object | None:
        fallback: object | None = None
        for name in options:
            if name in row.keys():
                value = row[name]
                if value not in (None, ""):
                    return value
                if fallback is None:
                    fallback = value
        return fallback

    def _row_to_result(self, row: sqlite3.Row) -> dict[str, object | None]:
        # Create a case-insensitive view of the row by lowercasing keys
        lowered = {str(k).lower(): row[k] for k in row.keys()}

        def coalesce_ci(options: Sequence[str]) -> object | None:
            fallback: object | None = None
            for name in options:
                key = name.lower()
                if key in lowered:
                    value = lowered[key]
                    if value not in (None, ""):
                        return value
                    if fallback is None:
                        fallback = value
            return fallback

        return {
            "id": coalesce_ci(("id", "person_id", "personnel_id")),
            "name": coalesce_ci(("name", "full_name", "display_name")),
            "callsign": coalesce_ci(("callsign", "call_sign")),
            "phone": coalesce_ci(("phone", "contact", "phone_number")),
            "agency": coalesce_ci(("home_unit", "unit", "agency", "department")),
        }

    @staticmethod
    def _searchable_columns(columns: Iterable[str]) -> List[str]:
        # Include id to support searching by personnel ID as well
        preferred = ["name", "callsign", "home_unit", "unit", "agency", "contact", "id"]
        # Columns set is already lowercased; ensure comparison is case-insensitive
        return [column for column in preferred if column.lower() in {c.lower() for c in columns}]

    def search_people(self, query: str, limit: int = 25) -> List[dict[str, object | None]]:
        """Return personnel rows matching ``query``.

        The master database has evolved over time, so column names are probed at
        runtime.  ``home_unit`` and ``unit`` are both treated as the agency field,
        while ``phone`` and ``contact`` are considered equivalent for contact
        information.
        """

        term = query.strip()
        if len(term) < 2:
            return []

        like = f"%{term.lower()}%"
        try:
            with self._connect() as conn:
                columns = self._personnel_columns(conn)
                if not columns:
                    return []
                search_columns = self._searchable_columns(columns)
                if not search_columns:
                    return []
                order_column = "name" if "name" in columns else search_columns[0]
                # Cast all columns to TEXT to safely apply LOWER/LIKE even if numeric (e.g., id)
                conditions = [
                    f"LOWER(COALESCE(CAST({column} AS TEXT), '')) LIKE ?" for column in search_columns
                ]
                sql = (
                    f"SELECT * FROM personnel WHERE {' OR '.join(conditions)} "
                    f"ORDER BY {order_column} LIMIT ?"
                )
                params = [like] * len(search_columns) + [limit]
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []
        return [self._row_to_result(row) for row in rows]
