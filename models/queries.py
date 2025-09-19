from __future__ import annotations

from typing import List, Dict, Any, Optional
import os
import sqlite3

# Use the active incident DB path helper already used elsewhere
from utils import incident_context


def get_db_connection() -> sqlite3.Connection:
    """Return a connection to the active incident database.

    Mirrors modules.operations.data.repository connection behavior.
    """
    db_path = incident_context.get_active_incident_db_path()
    abs_path = os.path.abspath(str(db_path))
    conn = sqlite3.connect(abs_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=3000")
    except Exception:
        pass
    return conn


# ---------- Fetchers ----------
def _rows_to_dicts(cur: sqlite3.Cursor) -> List[Dict[str, Any]]:
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        info = conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in info.fetchall())
    except Exception:
        return False


def fetch_team_personnel(team_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    has_callsign = _has_column(conn, "personnel", "callsign")
    has_rank = _has_column(conn, "personnel", "rank")
    has_org = _has_column(conn, "personnel", "organization")
    has_identifier = _has_column(conn, "personnel", "identifier")

    sel_callsign = ", callsign" if has_callsign else ", NULL AS callsign"
    if has_identifier:
        sel_identifier = ", identifier"
    elif has_callsign:
        sel_identifier = ", callsign AS identifier"
    else:
        sel_identifier = ", NULL AS identifier"
    sel_rank = ", rank" if has_rank else ", NULL AS rank"
    sel_org = ", organization" if has_org else ", NULL AS organization"

    sql = f"""
    SELECT id, name, role, phone, is_medic
           {sel_callsign}
           {sel_identifier}
           {sel_rank}
           {sel_org}
    FROM personnel
    WHERE team_id = ?
    ORDER BY name COLLATE NOCASE;
    """
    cur = conn.execute(sql, (team_id,))
    return _rows_to_dicts(cur)


def fetch_team_vehicles(team_id: int) -> List[Dict[str, Any]]:
    sql = """
    SELECT id, name, callsign, type
    FROM vehicles
    WHERE team_id = ?
    ORDER BY name COLLATE NOCASE;
    """
    conn = get_db_connection()
    cur = conn.execute(sql, (team_id,))
    return _rows_to_dicts(cur)


def fetch_team_equipment(team_id: int) -> List[Dict[str, Any]]:
    sql = """
    SELECT id, name, type, serial
    FROM equipment
    WHERE team_id = ?
    ORDER BY name COLLATE NOCASE;
    """
    conn = get_db_connection()
    cur = conn.execute(sql, (team_id,))
    return _rows_to_dicts(cur)


def fetch_team_aircraft(team_id: int) -> List[Dict[str, Any]]:
    sql = """
    SELECT id, tail_number, type, callsign
    FROM aircraft
    WHERE team_id = ?
    ORDER BY tail_number COLLATE NOCASE, callsign COLLATE NOCASE;
    """
    conn = get_db_connection()
    cur = conn.execute(sql, (team_id,))
    return _rows_to_dicts(cur)


def fetch_team_leader_id(team_id: int) -> Optional[int]:
    """Fetch leader id; prefer `team_leader`, fallback to `leader_id`."""
    conn = get_db_connection()
    # Prefer team_leader
    try:
        cur = conn.execute("SELECT team_leader FROM teams WHERE id = ?", (team_id,))
        row = cur.fetchone()
        if row and row[0] is not None:
            return row[0]
    except Exception:
        pass
    # Fallback: leader_id
    try:
        cur = conn.execute("SELECT leader_id FROM teams WHERE id = ?", (team_id,))
        row = cur.fetchone()
        return None if not row else row[0]
    except Exception:
        return None


# ---------- Additional helpers for Team Detail ----------
def list_available_personnel() -> List[Dict[str, Any]]:
    """List personnel not currently assigned to any team."""
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """
            SELECT id, name, role, callsign, phone
            FROM personnel
            WHERE team_id IS NULL OR team_id = ''
            ORDER BY name COLLATE NOCASE
            """
        )
        return _rows_to_dicts(cur)
    except Exception:
        return []


def list_available_aircraft(include_team_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List aircraft not assigned to any team; optionally include those on include_team_id."""
    conn = get_db_connection()
    try:
        if include_team_id is None:
            cur = conn.execute(
                """
                SELECT id, tail_number, callsign, team_id
                FROM aircraft
                WHERE team_id IS NULL
                ORDER BY tail_number COLLATE NOCASE, callsign COLLATE NOCASE
                """
            )
        else:
            cur = conn.execute(
                """
                SELECT id, tail_number, callsign, team_id
                FROM aircraft
                WHERE team_id IS NULL OR team_id = ?
                ORDER BY tail_number COLLATE NOCASE, callsign COLLATE NOCASE
                """,
                (int(include_team_id),),
            )
        return _rows_to_dicts(cur)
    except Exception:
        return []


def set_person_medic(person_id: int, is_medic: bool) -> None:
    conn = get_db_connection()
    conn.execute(
        "UPDATE personnel SET is_medic = ? WHERE id = ?",
        (1 if bool(is_medic) else 0, int(person_id)),
    )
    conn.commit()


# ---------- Mutations ----------
def set_person_team(person_id: int, team_id: Optional[int]) -> None:
    conn = get_db_connection()
    conn.execute("UPDATE personnel SET team_id = ? WHERE id = ?", (team_id, person_id))
    conn.commit()


def set_person_role(person_id: int, role: Optional[str]) -> None:
    conn = get_db_connection()
    conn.execute("UPDATE personnel SET role = ? WHERE id = ?", (role, person_id))
    conn.commit()


def set_vehicle_team(vehicle_id: int, team_id: Optional[int]) -> None:
    conn = get_db_connection()
    conn.execute("UPDATE vehicles SET team_id = ? WHERE id = ?", (team_id, vehicle_id))
    conn.commit()


def set_equipment_team(equipment_id: int, team_id: Optional[int]) -> None:
    conn = get_db_connection()
    conn.execute("UPDATE equipment SET team_id = ? WHERE id = ?", (team_id, equipment_id))
    conn.commit()


def set_aircraft_team(aircraft_id: int, team_id: Optional[int]) -> None:
    conn = get_db_connection()
    conn.execute("UPDATE aircraft SET team_id = ? WHERE id = ?", (team_id, aircraft_id))
    conn.commit()


def set_team_leader(team_id: int, leader_id: Optional[int]) -> None:
    conn = get_db_connection()
    # Attempt to set both possible columns for compatibility
    try:
        conn.execute("UPDATE teams SET leader_id = ? WHERE id = ?", (leader_id, team_id))
    except Exception:
        pass
    try:
        conn.execute("UPDATE teams SET team_leader = ? WHERE id = ?", (leader_id, team_id))
    except Exception:
        pass
    conn.commit()


def set_team_leader_phone(team_id: int, phone: Optional[str]) -> None:
    conn = get_db_connection()
    try:
        conn.execute("UPDATE teams SET leader_phone = ? WHERE id = ?", (phone, team_id))
        conn.commit()
    except Exception:
        pass
