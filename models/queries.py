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
    """Return personnel assigned to the given team.

    Supports two schema shapes:
    - Legacy: ``personnel.team_id`` column exists.
    - Current: team membership lives in ``teams.members_json`` (list of ids).
    """
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

    # Path 1: personnel.team_id column available
    if _has_column(conn, "personnel", "team_id"):
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

    # Path 2: use teams.members_json
    try:
        members: List[int] = []
        if _has_column(conn, "teams", "members_json"):
            row = conn.execute("SELECT members_json FROM teams WHERE id = ?", (team_id,)).fetchone()
            if row and row[0]:
                try:
                    import json
                    members = [int(x) for x in json.loads(row[0]) or []]
                except Exception:
                    members = []
        if not members:
            return []
        placeholders = ",".join(["?"] * len(members))
        sql = (
            "SELECT id, name, role, phone, is_medic"
            f"{sel_callsign}{sel_identifier}{sel_rank}{sel_org}"
            f" FROM personnel WHERE id IN ({placeholders})"
        )
        cur = conn.execute(sql, tuple(members))
        # Preserve the order of members_json when possible
        rows = {int(d["id"]): d for d in _rows_to_dicts(cur)}
        ordered = [rows[i] for i in members if i in rows]
        return ordered
    except Exception:
        return []
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
    conn = get_db_connection()
    has_status = _has_column(conn, "aircraft", "status")
    sel_status = ", status" if has_status else ", NULL AS status"
    sql = f"""
    SELECT id, tail_number, type, callsign{sel_status}
    FROM aircraft
    WHERE team_id = ?
    ORDER BY tail_number COLLATE NOCASE, callsign COLLATE NOCASE;
    """
    cur = conn.execute(sql, (team_id,))
    return _rows_to_dicts(cur)


def list_incident_vehicles() -> List[Dict[str, Any]]:
    """Return all vehicles that are signed into the active incident.

    This routine is defensive against schema variants. If the incident
    vehicles table does not provide ``name`` it will synthesize it from
    ``make`` and ``model`` when available. Optional columns are included
    when present.
    """
    conn = get_db_connection()
    # Probe available columns
    has_name = _has_column(conn, "vehicles", "name")
    has_callsign = _has_column(conn, "vehicles", "callsign")
    has_type = _has_column(conn, "vehicles", "type")
    has_make = _has_column(conn, "vehicles", "make")
    has_model = _has_column(conn, "vehicles", "model")
    has_team_id = _has_column(conn, "vehicles", "team_id")

    # Build select fragments
    sel_name = (
        "name AS name"
        if has_name
        else "TRIM(COALESCE(make,'')||' '||COALESCE(model,'')) AS name"
        if (has_make or has_model)
        else "CAST(id AS TEXT) AS name"
    )
    sel_callsign = "callsign" if has_callsign else "NULL AS callsign"
    sel_type = "type" if has_type else "NULL AS type"
    sel_team = "team_id" if has_team_id else "NULL AS team_id"

    # Optional team name via join if teams table exists
    has_teams = _has_column(conn, "teams", "id") and _has_column(conn, "teams", "name")
    join_clause = " LEFT JOIN teams t ON v.team_id = t.id" if has_teams and has_team_id else ""
    sel_team_name = ", t.name AS team_name" if join_clause else ", NULL AS team_name"

    sql = (
        "SELECT v.id, "
        + sel_name
        + ", "
        + sel_callsign
        + ", "
        + sel_type
        + ", "
        + sel_team
        + sel_team_name
        + " FROM vehicles v"
        + join_clause
        + " ORDER BY name COLLATE NOCASE, callsign COLLATE NOCASE"
    )
    cur = conn.execute(sql)
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
    """List personnel not currently assigned to any team.

    Works with either ``personnel.team_id`` or ``teams.members_json``.
    """
    conn = get_db_connection()
    callsign_sel = "callsign" if _has_column(conn, "personnel", "callsign") else "NULL AS callsign"
    try:
        if _has_column(conn, "personnel", "team_id"):
            sql = (
                "SELECT id, name, role, "
                + callsign_sel
                + ", phone FROM personnel WHERE team_id IS NULL OR team_id = ''"
                + " ORDER BY name COLLATE NOCASE"
            )
            cur = conn.execute(sql)
            return _rows_to_dicts(cur)
        # Fallback: exclude anyone referenced in any members_json
        if _has_column(conn, "teams", "members_json"):
            import json
            rows = conn.execute("SELECT members_json FROM teams").fetchall()
            assigned: set[int] = set()
            for r in rows:
                try:
                    for x in json.loads(r[0] or "[]"):
                        try:
                            assigned.add(int(x))
                        except Exception:
                            continue
                except Exception:
                    continue
            if assigned:
                placeholders = ",".join(["?"] * len(assigned))
                sql = (
                    "SELECT id, name, role, "
                    + callsign_sel
                    + ", phone FROM personnel WHERE id NOT IN (" + placeholders + ")"
                    + " ORDER BY name COLLATE NOCASE"
                )
                cur = conn.execute(sql, tuple(sorted(assigned)))
            else:
                sql = "SELECT id, name, role, " + callsign_sel + ", phone FROM personnel ORDER BY name COLLATE NOCASE"
                cur = conn.execute(sql)
            return _rows_to_dicts(cur)
        return []
    except Exception:
        return []
def list_available_aircraft(include_team_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List aircraft not assigned to any team; optionally include those on include_team_id."""
    conn = get_db_connection()
    try:
        has_status = _has_column(conn, "aircraft", "status")
        sel_status = ", status" if has_status else ", NULL AS status"
        base_sql = (
            "SELECT id, tail_number, callsign, team_id"
            f"{sel_status} FROM aircraft"
        )
        order_clause = " ORDER BY tail_number COLLATE NOCASE, callsign COLLATE NOCASE"
        if include_team_id is None:
            sql = base_sql + " WHERE team_id IS NULL" + order_clause
            cur = conn.execute(sql)
        else:
            sql = base_sql + " WHERE team_id IS NULL OR team_id = ?" + order_clause
            cur = conn.execute(sql, (int(include_team_id),))
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
    """Assign or unassign a person to a team.

    If ``personnel.team_id`` exists, update it. Additionally, when the
    ``teams.members_json`` column is present, keep it in sync by adding or
    removing the ``person_id`` accordingly so UI that depends on JSON lists
    stays consistent across schema variants.
    """
    conn = get_db_connection()
    # Best-effort legacy column update
    if _has_column(conn, "personnel", "team_id"):
        conn.execute("UPDATE personnel SET team_id = ? WHERE id = ?", (team_id, person_id))
    # Keep JSON membership in sync when available
    if _has_column(conn, "teams", "members_json"):
        import json
        # Remove person from all teams first to enforce uniqueness
        cur = conn.execute("SELECT id, members_json FROM teams")
        rows = cur.fetchall()
        updated_any = False
        for row in rows:
            tid = int(row[0]) if row[0] is not None else None
            try:
                members = list(json.loads(row[1] or "[]"))
            except Exception:
                members = []
            new_members = [int(x) for x in members if int(x) != int(person_id)]
            if new_members != members:
                conn.execute(
                    "UPDATE teams SET members_json = ? WHERE id = ?",
                    (json.dumps(new_members), tid),
                )
                updated_any = True
        # If assigning, add to the target team
        if team_id is not None:
            r = conn.execute("SELECT members_json FROM teams WHERE id = ?", (int(team_id),)).fetchone()
            members = []
            if r and r[0]:
                try:
                    members = list(json.loads(r[0] or "[]"))
                except Exception:
                    members = []
            if int(person_id) not in [int(x) for x in members]:
                members.append(int(person_id))
                conn.execute(
                    "UPDATE teams SET members_json = ? WHERE id = ?",
                    (json.dumps(members), int(team_id)),
                )
                updated_any = True
        if updated_any:
            conn.commit()
            return
    # Commit for the legacy path or if nothing else triggered a commit
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

def list_incident_equipment() -> List[Dict[str, Any]]:
    """Return all equipment signed into the active incident with optional team info."""
    conn = get_db_connection()
    # Probe available columns
    has_name = _has_column(conn, "equipment", "name")
    has_type = _has_column(conn, "equipment", "type")
    has_serial = _has_column(conn, "equipment", "serial") or _has_column(conn, "equipment", "serial_number")
    has_team_id = _has_column(conn, "equipment", "team_id")

    sel_name = "name" if has_name else "CAST(id AS TEXT) AS name"
    sel_type = "type" if has_type else "NULL AS type"
    sel_serial = "serial" if _has_column(conn, "equipment", "serial") else ("serial_number" if _has_column(conn, "equipment", "serial_number") else "NULL AS serial")
    sel_team = "team_id" if has_team_id else "NULL AS team_id"

    # Optional team name via join if teams table exists
    has_teams = _has_column(conn, "teams", "id") and _has_column(conn, "teams", "name")
    join_clause = " LEFT JOIN teams t ON e.team_id = t.id" if has_teams and has_team_id else ""
    sel_team_name = ", t.name AS team_name" if join_clause else ", NULL AS team_name"

    sql = (
        "SELECT e.id, " + sel_name + ", " + sel_type + ", " + sel_serial + ", " + sel_team + sel_team_name +
        " FROM equipment e" + join_clause + " ORDER BY name COLLATE NOCASE"
    )
    cur = conn.execute(sql)
    return _rows_to_dicts(cur)
# --- PATCH: override list functions to include status/eta when available ---
from typing import Any, Dict, List, Optional  # re-import safe

def list_incident_vehicles() -> List[Dict[str, Any]]:  # type: ignore[override]
    """Return all vehicles signed into the incident with team, status, ETA when available.

    Falls back to synthesizing status from assignment when explicit columns are missing.
    """
    conn = get_db_connection()
    has_name = _has_column(conn, "vehicles", "name")
    has_callsign = _has_column(conn, "vehicles", "callsign")
    has_type = _has_column(conn, "vehicles", "type")
    has_make = _has_column(conn, "vehicles", "make")
    has_model = _has_column(conn, "vehicles", "model")
    has_team_id = _has_column(conn, "vehicles", "team_id")
    has_status_col = _has_column(conn, "vehicles", "status")

    sel_name = (
        "name AS name" if has_name else (
            "TRIM(COALESCE(make,'')||' '||COALESCE(model,'')) AS name" if (has_make or has_model) else "CAST(id AS TEXT) AS name"
        )
    )
    sel_callsign = "callsign" if has_callsign else "NULL AS callsign"
    sel_type = "type" if has_type else "NULL AS type"
    sel_team = "team_id" if has_team_id else "NULL AS team_id"
    sel_status = "status" if has_status_col else "NULL AS status"
    sel_eta = (
        "eta" if _has_column(conn, "vehicles", "eta") else (
            "eta_utc" if _has_column(conn, "vehicles", "eta_utc") else "NULL AS eta"
        )
    )

    has_teams = _has_column(conn, "teams", "id") and _has_column(conn, "teams", "name")
    join_clause = " LEFT JOIN teams t ON v.team_id = t.id" if has_teams and has_team_id else ""
    sel_team_name = ", t.name AS team_name" if join_clause else ", NULL AS team_name"

    sql = (
        "SELECT v.id, " + sel_name + ", " + sel_callsign + ", " + sel_type + ", " + sel_team + ", " + sel_status + ", " + sel_eta + sel_team_name +
        " FROM vehicles v" + join_clause + " ORDER BY name COLLATE NOCASE, callsign COLLATE NOCASE"
    )
    cur = conn.execute(sql)
    return _rows_to_dicts(cur)


def list_incident_equipment() -> List[Dict[str, Any]]:  # type: ignore[override]
    """Return all equipment signed into the incident with team, status, ETA when available."""
    conn = get_db_connection()
    has_name = _has_column(conn, "equipment", "name")
    has_type = _has_column(conn, "equipment", "type")
    has_serial = _has_column(conn, "equipment", "serial") or _has_column(conn, "equipment", "serial_number")
    has_team_id = _has_column(conn, "equipment", "team_id")

    sel_name = "name" if has_name else "CAST(id AS TEXT) AS name"
    sel_type = "type" if has_type else "NULL AS type"
    sel_serial = (
        "serial" if _has_column(conn, "equipment", "serial") else (
            "serial_number" if _has_column(conn, "equipment", "serial_number") else "NULL AS serial"
        )
    )
    sel_team = "team_id" if has_team_id else "NULL AS team_id"
    sel_status = "status" if _has_column(conn, "equipment", "status") else "NULL AS status"
    sel_eta = (
        "eta" if _has_column(conn, "equipment", "eta") else (
            "eta_utc" if _has_column(conn, "equipment", "eta_utc") else "NULL AS eta"
        )
    )

    has_teams = _has_column(conn, "teams", "id") and _has_column(conn, "teams", "name")
    join_clause = " LEFT JOIN teams t ON e.team_id = t.id" if has_teams and has_team_id else ""
    sel_team_name = ", t.name AS team_name" if join_clause else ", NULL AS team_name"

    sql = (
        "SELECT e.id, " + sel_name + ", " + sel_type + ", " + sel_serial + ", " + sel_team + ", " + sel_status + ", " + sel_eta + sel_team_name +
        " FROM equipment e" + join_clause + " ORDER BY name COLLATE NOCASE"
    )
    cur = conn.execute(sql)
    return _rows_to_dicts(cur)
