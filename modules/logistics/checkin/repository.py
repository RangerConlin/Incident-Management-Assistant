"""Database access layer for the check-in module.

This module exposes simple functions that interact with both the
persistent master database and the currently active incident database.
Functions are intentionally straightforward and heavily commented so
that they can be expanded in future iterations without major refactors.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
import sqlite3

from utils.db import get_master_conn, get_incident_conn
from utils import incident_context
from utils.schema_placeholders import ensure_master_tables_exist, ensure_incident_tables_exist

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> Optional[Dict]:
    """Convert a Row to a plain dict."""
    return dict(row) if row else None


def find_personnel_by_id(pid: str) -> Optional[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM personnel_master WHERE id = ?", (pid,))
        return _row_to_dict(cur.fetchone())


def find_personnel_by_name(first: str, last: str) -> List[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute(
            "SELECT * FROM personnel_master WHERE first_name = ? AND last_name = ?",
            (first, last),
        )
        return [dict(row) for row in cur.fetchall()]


def find_equipment_by_id(eid: str) -> Optional[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM equipment_master WHERE id = ?", (eid,))
        return _row_to_dict(cur.fetchone())


def find_equipment_by_name(name: str) -> List[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM equipment_master WHERE name = ?", (name,))
        return [dict(row) for row in cur.fetchall()]


def find_vehicle_by_id(vid: str) -> Optional[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM vehicle_master WHERE id = ?", (vid,))
        return _row_to_dict(cur.fetchone())


def find_vehicle_by_name(name: str) -> List[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM vehicle_master WHERE name = ?", (name,))
        return [dict(row) for row in cur.fetchall()]


def find_aircraft_by_id(aid: str) -> Optional[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM aircraft_master WHERE id = ?", (aid,))
        return _row_to_dict(cur.fetchone())


def find_aircraft_by_tail(tail_number: str) -> List[Dict]:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        cur = conn.execute("SELECT * FROM aircraft_master WHERE tail_number = ?", (tail_number,))
        return [dict(row) for row in cur.fetchall()]

# ---------------------------------------------------------------------------
# Master creation helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.utcnow().isoformat()


def create_or_update_personnel_master(data: Dict) -> None:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        payload = data.copy()
        payload.setdefault("callsign", None)
        payload.setdefault("role", None)
        payload.setdefault("status", "Available")
        payload.setdefault("created_at", _timestamp())
        payload["updated_at"] = _timestamp()
        conn.execute(
            """
            INSERT INTO personnel_master (id, first_name, last_name, callsign, role, status, created_at, updated_at)
            VALUES (:id, :first_name, :last_name, :callsign, :role, :status, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                callsign=excluded.callsign,
                role=excluded.role,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        conn.commit()


def create_or_update_equipment_master(data: Dict) -> None:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        payload = data.copy()
        payload.setdefault("type", None)
        payload.setdefault("assigned_to", None)
        payload.setdefault("status", "Available")
        payload.setdefault("created_at", _timestamp())
        payload["updated_at"] = _timestamp()
        conn.execute(
            """
            INSERT INTO equipment_master (id, name, type, status, assigned_to, created_at, updated_at)
            VALUES (:id, :name, :type, :status, :assigned_to, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                status=excluded.status,
                assigned_to=excluded.assigned_to,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        conn.commit()


def create_or_update_vehicle_master(data: Dict) -> None:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        payload = data.copy()
        payload.setdefault("type", None)
        payload.setdefault("callsign", None)
        payload.setdefault("assigned_to", None)
        payload.setdefault("status", "Available")
        payload.setdefault("created_at", _timestamp())
        payload["updated_at"] = _timestamp()
        conn.execute(
            """
            INSERT INTO vehicle_master (id, name, type, status, callsign, assigned_to, created_at, updated_at)
            VALUES (:id, :name, :type, :status, :callsign, :assigned_to, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                status=excluded.status,
                callsign=excluded.callsign,
                assigned_to=excluded.assigned_to,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        conn.commit()


def create_or_update_aircraft_master(data: Dict) -> None:
    with get_master_conn() as conn:
        ensure_master_tables_exist(conn)
        payload = data.copy()
        payload.setdefault("tail_number", data.get("tail_number"))
        payload.setdefault("type", None)
        payload.setdefault("callsign", None)
        payload.setdefault("assigned_to", None)
        payload.setdefault("status", "Available")
        payload.setdefault("created_at", _timestamp())
        payload["updated_at"] = _timestamp()
        conn.execute(
            """
            INSERT INTO aircraft_master (id, tail_number, type, status, callsign, assigned_to, created_at, updated_at)
            VALUES (:id, :tail_number, :type, :status, :callsign, :assigned_to, :created_at, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                tail_number=excluded.tail_number,
                type=excluded.type,
                status=excluded.status,
                callsign=excluded.callsign,
                assigned_to=excluded.assigned_to,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        conn.commit()

# ---------------------------------------------------------------------------
# Incident copy helpers
# ---------------------------------------------------------------------------

def _incident_insert(sql: str, payload: Dict) -> None:
    with get_incident_conn() as conn:
        ensure_incident_tables_exist(conn)
        conn.execute(sql, payload)
        conn.commit()


def copy_personnel_to_incident(personnel: Dict) -> None:
    incident_id = incident_context.get_active_incident_id()
    payload = personnel.copy()
    payload.update(
        {
            "incident_id": incident_id,
            "status": "Checked-In",
            "checked_in_at": _timestamp(),
            "updated_at": _timestamp(),
        }
    )
    payload.setdefault("callsign", None)
    payload.setdefault("role", None)
    _incident_insert(
        """
        INSERT INTO personnel_incident (id, incident_id, first_name, last_name, callsign, role, status, checked_in_at, updated_at)
        VALUES (:id, :incident_id, :first_name, :last_name, :callsign, :role, :status, :checked_in_at, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            incident_id=excluded.incident_id,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            callsign=excluded.callsign,
            role=excluded.role,
            status=excluded.status,
            checked_in_at=excluded.checked_in_at,
            updated_at=excluded.updated_at
        """,
        payload,
    )


def copy_equipment_to_incident(equipment: Dict) -> None:
    incident_id = incident_context.get_active_incident_id()
    payload = equipment.copy()
    payload.update(
        {
            "incident_id": incident_id,
            "status": "Checked-In",
            "checked_in_at": _timestamp(),
            "updated_at": _timestamp(),
        }
    )
    payload.setdefault("type", None)
    payload.setdefault("assigned_to", None)
    _incident_insert(
        """
        INSERT INTO equipment_incident (id, incident_id, name, type, status, assigned_to, checked_in_at, updated_at)
        VALUES (:id, :incident_id, :name, :type, :status, :assigned_to, :checked_in_at, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            incident_id=excluded.incident_id,
            name=excluded.name,
            type=excluded.type,
            status=excluded.status,
            assigned_to=excluded.assigned_to,
            checked_in_at=excluded.checked_in_at,
            updated_at=excluded.updated_at
        """,
        payload,
    )


def copy_vehicle_to_incident(vehicle: Dict) -> None:
    incident_id = incident_context.get_active_incident_id()
    payload = vehicle.copy()
    payload.update(
        {
            "incident_id": incident_id,
            "status": "Checked-In",
            "checked_in_at": _timestamp(),
            "updated_at": _timestamp(),
        }
    )
    payload.setdefault("type", None)
    payload.setdefault("callsign", None)
    payload.setdefault("assigned_to", None)
    _incident_insert(
        """
        INSERT INTO vehicle_incident (id, incident_id, name, type, status, callsign, assigned_to, checked_in_at, updated_at)
        VALUES (:id, :incident_id, :name, :type, :status, :callsign, :assigned_to, :checked_in_at, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            incident_id=excluded.incident_id,
            name=excluded.name,
            type=excluded.type,
            status=excluded.status,
            callsign=excluded.callsign,
            assigned_to=excluded.assigned_to,
            checked_in_at=excluded.checked_in_at,
            updated_at=excluded.updated_at
        """,
        payload,
    )


def copy_aircraft_to_incident(aircraft: Dict) -> None:
    incident_id = incident_context.get_active_incident_id()
    payload = aircraft.copy()
    payload.update(
        {
            "incident_id": incident_id,
            "status": "Checked-In",
            "checked_in_at": _timestamp(),
            "updated_at": _timestamp(),
        }
    )
    payload.setdefault("tail_number", aircraft.get("tail_number"))
    payload.setdefault("type", None)
    payload.setdefault("callsign", None)
    payload.setdefault("assigned_to", None)
    _incident_insert(
        """
        INSERT INTO aircraft_incident (id, incident_id, tail_number, type, status, callsign, assigned_to, checked_in_at, updated_at)
        VALUES (:id, :incident_id, :tail_number, :type, :status, :callsign, :assigned_to, :checked_in_at, :updated_at)
        ON CONFLICT(id) DO UPDATE SET
            incident_id=excluded.incident_id,
            tail_number=excluded.tail_number,
            type=excluded.type,
            status=excluded.status,
            callsign=excluded.callsign,
            assigned_to=excluded.assigned_to,
            checked_in_at=excluded.checked_in_at,
            updated_at=excluded.updated_at
        """,
        payload,
    )
