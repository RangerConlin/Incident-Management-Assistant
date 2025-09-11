from __future__ import annotations

"""Read-only repository for the master communications catalog.

This layer is schema-agnostic and maps whatever columns exist in
``comms_resources`` to a canonical set of keys used by the UI.
"""

from typing import Any, Dict, List

from . import db
from .incident_repo import infer_band


def _map_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a SQLite row from ``comms_resources`` to canonical keys.

    Tolerates varying column names and missing fields.
    """
    lower = {k.lower(): row[k] for k in row.keys()}

    def pick(*names: str, default: Any = None) -> Any:
        for n in names:
            if n in lower and lower[n] not in (None, ""):
                return lower[n]
        return default

    name = pick("alpha tag", "alpha_tag", "name") or ""
    rx = pick("freq rx", "freq_rx", "rx", default=0)
    tx = pick("freq tx", "freq_tx", "tx", default=None)
    try:
        rx_freq = float(rx) if rx is not None else 0.0
    except (TypeError, ValueError):
        rx_freq = 0.0
    try:
        tx_freq = float(tx) if tx not in (None, "") else None
    except (TypeError, ValueError):
        tx_freq = None

    mapped = {
        "id": row.get("id"),
        "name": name,
        "function": pick("function", default="Tactical"),
        "rx_freq": rx_freq,
        "tx_freq": tx_freq,
        "rx_tone": pick("rx tone", "rx_tone"),
        "tx_tone": pick("tx tone", "tx_tone"),
        "system": pick("system"),
        "mode": pick("mode", default="FM"),
        "notes": pick("notes"),
        "line_a": int(pick("line_a", default=0) or 0),
        "line_c": int(pick("line_c", default=0) or 0),
    }
    mapped["display_name"] = mapped["name"] or f"Ch-{mapped['id']}"
    mapped["band"] = infer_band(mapped["rx_freq"] or mapped["tx_freq"] or 0)
    return mapped


class MasterRepository:
    """Repository interface for the master catalog."""

    def list_channels(self, filters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        filters = filters or {}
        rows: List[Dict[str, Any]] = []
        with db.get_master_conn() as conn:
            for r in conn.execute("SELECT * FROM comms_resources").fetchall():
                rows.append(_map_row(dict(r)))

        def match(row: Dict[str, Any]) -> bool:
            if val := filters.get("search"):
                text = " ".join(str(row.get(k, "")) for k in ("name", "function", "notes")).lower()
                if val.lower() not in text:
                    return False
            if val := filters.get("band"):
                if row.get("band") != val:
                    return False
            if val := filters.get("mode"):
                if row.get("mode") != val:
                    return False
            return True

        return [r for r in rows if match(r)]

    def get_channel(self, channel_id: int) -> Dict[str, Any] | None:
        with db.get_master_conn() as conn:
            row = conn.execute(
                "SELECT * FROM comms_resources WHERE id=?", (channel_id,)
            ).fetchone()
            return _map_row(dict(row)) if row else None


__all__ = ["MasterRepository"]

