from __future__ import annotations

"""Read-only access to the master personnel catalog."""

import sqlite3
from typing import Callable, List

from utils.db import get_master_conn


class MasterPersonnelRepository:
    """Simple search interface for ``master.db`` personnel records."""

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection] | None = None):
        self._factory = connection_factory

    def _connect(self) -> sqlite3.Connection:
        if self._factory is not None:
            return self._factory()
        return get_master_conn()

    def search_people(self, query: str, limit: int = 25) -> List[dict[str, object | None]]:
        """Return personnel rows matching ``query``.

        Searches ``name``, ``callsign``, and ``home_unit`` columns.  A minimum of
        two characters is required to avoid overly broad scans of the master
        table.
        """

        term = query.strip()
        if len(term) < 2:
            return []
        like = f"%{term.lower()}%"
        sql = (
            "SELECT id, name, callsign, phone, home_unit as agency "
            "FROM personnel WHERE lower(name) LIKE ? OR lower(callsign) LIKE ? "
            "OR lower(COALESCE(home_unit, '')) LIKE ? ORDER BY name LIMIT ?"
        )
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, (like, like, like, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]
