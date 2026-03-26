from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from . import incident_context
from . import incident_db


@dataclass
class IcpLocation:
    address: str
    latitude: float
    longitude: float


def _connect_active() -> sqlite3.Connection:
    # Ensure the per-incident DB exists and schema is compatible
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("Active incident has not been set")
    db_path = incident_db.ensure_incident_database(incident_id)
    conn = sqlite3.connect(db_path)
    return conn


def get_icp_location() -> Optional[IcpLocation]:
    try:
        with _connect_active() as conn:
            row = conn.execute(
                "SELECT icp_address, icp_lat, icp_lon FROM incident_meta WHERE id = 1"
            ).fetchone()
            if not row:
                return None
            addr, lat, lon = row
            if addr is None or lat is None or lon is None:
                return None
            return IcpLocation(address=str(addr), latitude=float(lat), longitude=float(lon))
    except Exception:
        return None


def set_icp_location(address: str, latitude: float, longitude: float) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect_active() as conn:
        conn.execute(
            "UPDATE incident_meta SET icp_address=?, icp_lat=?, icp_lon=?, updated_at=? WHERE id = 1",
            (address, float(latitude), float(longitude), ts),
        )
        if conn.total_changes == 0:
            conn.execute(
                "INSERT INTO incident_meta (id, icp_address, icp_lat, icp_lon, updated_at) VALUES (1, ?, ?, ?, ?)",
                (address, float(latitude), float(longitude), ts),
            )
        conn.commit()

    # Emit cross-app signal if available
    try:
        from .app_signals import app_signals

        app_signals.icpLocationChanged.emit(
            {"address": address, "lat": float(latitude), "lon": float(longitude)}
        )
    except Exception:
        pass


__all__ = ["IcpLocation", "get_icp_location", "set_icp_location"]
