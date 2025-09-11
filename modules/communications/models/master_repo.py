from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from .db import get_master_conn


class MasterRepository:
    """Read-only access to ``comms_resources`` from the master database.

    The schema may vary between deployments so rows are mapped to a canonical
    dictionary with optional keys filled with defaults.
    """

    def _map_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        def _col(name: str, default: Any = None):
            return row[name] if name in row.keys() else default

        name = _col('Alpha Tag') or _col('name') or f"Channel-{row['id']}"
        function = _col('function', 'Tactical') or 'Tactical'
        mapped = {
            'id': row['id'],
            'name': name,
            'function': function,
            'rx_freq': _col('Freq Rx'),
            'tx_freq': _col('Freq Tx'),
            'rx_tone': _col('Rx Tone'),
            'tx_tone': _col('Tx Tone'),
            'system': _col('System'),
            'mode': _col('Mode'),
            'notes': _col('Notes'),
            'line_a': _col('line_a', 0),
            'line_c': _col('line_c', 0),
        }
        mapped['display_name'] = mapped['name']
        return mapped

    # ------------------------------------------------------------------
    def list_channels(self, filters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        filters = filters or {}
        rows: List[Dict[str, Any]] = []
        with get_master_conn() as conn:
            cur = conn.execute('SELECT * FROM comms_resources')
            for row in cur.fetchall():
                mapped = self._map_row(row)
                if self._apply_filters(mapped, filters):
                    rows.append(mapped)
        return rows

    def _apply_filters(self, row: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        search = filters.get('search')
        if search:
            haystack = f"{row.get('name','')} {row.get('notes','')}".lower()
            if search.lower() not in haystack:
                return False
        mode = filters.get('mode')
        if mode and row.get('mode') != mode:
            return False
        band = filters.get('band')
        if band and band != self._infer_band(row):
            return False
        return True

    def _infer_band(self, row: Dict[str, Any]) -> str:
        f = row.get('rx_freq') or row.get('tx_freq') or 0
        try:
            f = float(f)
        except Exception:
            return 'Other'
        if 3 <= f < 30:
            return 'HF'
        if 30 <= f < 54:
            return 'VHF-LOW'
        if 118 <= f <= 137:
            return 'Air'
        if 156 <= f <= 163:
            return 'Marine'
        if 54 <= f < 300:
            return 'VHF'
        if 300 <= f < 700:
            return 'UHF'
        if 700 <= f <= 869:
            return '700/800'
        return 'Other'

    # ------------------------------------------------------------------
    def get_channel(self, id: int) -> Dict[str, Any] | None:
        with get_master_conn() as conn:
            cur = conn.execute('SELECT * FROM comms_resources WHERE id=?', (id,))
            row = cur.fetchone()
            if row is None:
                return None
            return self._map_row(row)
