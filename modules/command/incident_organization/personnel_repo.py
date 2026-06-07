from __future__ import annotations

"""Read-only personnel lookup for organization assignments."""

import sqlite3
from typing import Callable, Iterable, Sequence

from utils.db import get_master_conn


class PersonnelPoolRepository:
    """Searches existing personnel data without owning personnel records."""

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection] | None = None):
        self._factory = connection_factory

    def _connect(self) -> sqlite3.Connection:
        if self._factory is not None:
            return self._factory()
        return get_master_conn()

    @staticmethod
    def _personnel_columns(conn: sqlite3.Connection) -> set[str]:
        try:
            rows = conn.execute("PRAGMA table_info(personnel)").fetchall()
        except sqlite3.OperationalError:
            return set()
        return {str(row[1]).lower() for row in rows}

    @staticmethod
    def _searchable_columns(columns: Iterable[str]) -> list[str]:
        preferred = ["name", "callsign", "home_unit", "unit", "agency", "contact", "id"]
        lowered = {column.lower() for column in columns}
        return [column for column in preferred if column.lower() in lowered]

    @staticmethod
    def _row_to_result(row: sqlite3.Row) -> dict[str, object | None]:
        lowered = {str(key).lower(): row[key] for key in row.keys()}

        def coalesce(options: Sequence[str]) -> object | None:
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
            "id": coalesce(("id", "person_id", "personnel_id")),
            "name": coalesce(("name", "full_name", "display_name")),
            "callsign": coalesce(("callsign", "call_sign")),
            "phone": coalesce(("phone", "contact", "phone_number")),
            "agency": coalesce(("home_unit", "unit", "agency", "department")),
        }

    def search_people(self, query: str, limit: int = 25) -> list[dict[str, object | None]]:
        term = query.strip()
        if len(term) < 2:
            return []
        like = f"%{term.lower()}%"
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                columns = self._personnel_columns(conn)
                if not columns:
                    return []
                search_columns = self._searchable_columns(columns)
                if not search_columns:
                    return []
                order_column = "name" if "name" in columns else search_columns[0]
                conditions = [
                    f"LOWER(COALESCE(CAST({column} AS TEXT), '')) LIKE ?"
                    for column in search_columns
                ]
                rows = conn.execute(
                    f"SELECT * FROM personnel WHERE {' OR '.join(conditions)} "
                    f"ORDER BY {order_column} LIMIT ?",
                    [like] * len(search_columns) + [limit],
                ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [self._row_to_result(row) for row in rows]
