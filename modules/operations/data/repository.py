from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from utils import incident_context


def _connect() -> sqlite3.Connection:
    """Open a connection to the active incident database.

    Raises RuntimeError if no active incident is set.
    """
    db_path = incident_context.get_active_incident_db_path()
    # ensure absolute path for sqlite
    abs_path = os.path.abspath(str(db_path))
    con = sqlite3.connect(abs_path)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=3000")
    except Exception:
        pass
    return con


def _has_table(con: sqlite3.Connection, name: str) -> bool:
    try:
        cur = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None
    except Exception:
        return False


def _priority_label(value: Any) -> str:
    """Map integer priority (1..4) to label; pass through strings.

    1 -> Low, 2 -> Medium, 3 -> High, 4 -> Critical
    """
    try:
        i = int(value)
    except Exception:
        return str(value) if value is not None else ""
    return {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(i, str(i))


def _task_status_label(value: Any) -> str:
    """Normalize task status strings to align with color keys.

    Maps e.g. "Completed" -> "complete", "Draft" -> "created".
    """
    if value is None:
        return ""
    s = str(value).strip().lower()
    return {
        "completed": "complete",
        "complete": "complete",
        "draft": "created",
        "created": "created",
        "planned": "planned",
        "assigned": "assigned",
        "in progress": "in progress",
        "cancelled": "cancelled",
    }.get(s, s)


def _ensure_teams_status_columns(con: sqlite3.Connection) -> None:
    """Add teams.status and teams.status_updated if missing (best-effort)."""
    try:
        cur = con.execute("PRAGMA table_info(teams)")
        cols = {row[1] for row in cur.fetchall()}
        if "status" not in cols:
            con.execute("ALTER TABLE teams ADD COLUMN status TEXT")
        if "status_updated" not in cols:
            con.execute("ALTER TABLE teams ADD COLUMN status_updated TEXT")
        con.commit()
    except Exception:
        pass


def _ensure_teams_current_task_column(con: sqlite3.Connection) -> None:
    """Add teams.current_task_id if missing (best-effort)."""
    try:
        cur = con.execute("PRAGMA table_info(teams)")
        cols = {row[1] for row in cur.fetchall()}
        if "current_task_id" not in cols:
            con.execute("ALTER TABLE teams ADD COLUMN current_task_id INTEGER")
            con.commit()
    except Exception:
        pass


def _ensure_teams_name_column(con: sqlite3.Connection) -> None:
    """Add teams.name if missing (best-effort)."""
    try:
        cur = con.execute("PRAGMA table_info(teams)")
        cols = {row[1] for row in cur.fetchall()}
        if "name" not in cols:
            con.execute("ALTER TABLE teams ADD COLUMN name TEXT")
            con.commit()
    except Exception:
        pass


def _ensure_teams_attention_column(con: sqlite3.Connection) -> None:
    """Add teams.needs_attention if missing (best-effort)."""
    try:
        cur = con.execute("PRAGMA table_info(teams)")
        cols = {row[1] for row in cur.fetchall()}
        if "needs_attention" not in cols:
            con.execute("ALTER TABLE teams ADD COLUMN needs_attention BOOLEAN DEFAULT 0")
            con.commit()
    except Exception:
        pass


def _ensure_team_alert_columns(con: sqlite3.Connection) -> None:
    """Ensure modern alert columns exist on the teams table."""
    try:
        cur = con.execute("PRAGMA table_info(teams)")
        cols = {row[1] for row in cur.fetchall()}
        to_add: list[tuple[str, str]] = []
        if "emergency_flag" not in cols:
            to_add.append(("emergency_flag", "BOOLEAN"))
        if "last_checkin_at" not in cols:
            to_add.append(("last_checkin_at", "TEXT"))
        if "checkin_reference_at" not in cols:
            to_add.append(("checkin_reference_at", "TEXT"))
        for col, typ in to_add:
            try:
                con.execute(f"ALTER TABLE teams ADD COLUMN {col} {typ}")
            except Exception:
                pass
        if to_add:
            try:
                con.commit()
            except Exception:
                pass
    except Exception:
        pass


def _iso_timestamp(value: datetime | None) -> str:
    """Return an ISO-8601 string for ``value`` normalized to UTC."""
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo is None or dt.utcoffset() is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()

def _derive_team_status(row: sqlite3.Row) -> str:
    """Derive a coarse team status from task_teams timestamp columns.

    Uses the following precedence: cleared -> complete -> arrived -> enroute ->
    briefed -> assigned. Falls back to "assigned" if no timestamps.
    """
    # Note: columns may be NULL or empty strings
    def _val(key: str):
        try:
            return row[key]
        except Exception:
            return None

    if _val("time_cleared"):
        return "returning"
    if _val("time_complete"):
        return "complete"
    if _val("time_arrived"):
        # We use "arrival" to match TEAM_STATUS_COLORS keys
        return "arrival"
    if _val("time_enroute"):
        return "enroute"
    if _val("time_briefed"):
        return "briefed"
    if _val("time_assigned"):
        return "assigned"
    # If no timestamps present, consider the team "available" for display
    ts_keys = [
        "time_assigned",
        "time_briefed",
        "time_enroute",
        "time_arrived",
        "time_discovery",
        "time_complete",
        "time_cleared",
    ]
    if not any(_val(k) for k in ts_keys):
        return "available"
    return "assigned"


def fetch_task_rows() -> List[Dict[str, Any]]:
    """Return task rows for the Task Status board from the incident DB.

    Each dict contains: number, name, assigned_teams (List[str]), status,
    priority, location.
    """
    with _connect() as con:
        tasks = con.execute(
            "SELECT id, task_id, title, status, priority, location FROM tasks ORDER BY id"
        ).fetchall()
        # Preload assignments grouped by task_id
        tt_rows = con.execute(
            """
            SELECT tt.task_id,
                   tt.teamid,
                   tt.sortie_id,
                   tm.name AS team_name
              FROM task_teams tt
         LEFT JOIN teams tm ON tt.teamid = tm.id
             ORDER BY tt.id
            """
        ).fetchall()

    assigned_map: Dict[int, List[str]] = {}
    for r in tt_rows:
        label = (
            r["team_name"]
            or r["sortie_id"]
            or (f"Team {r['teamid']}" if r["teamid"] is not None else "Team")
        )
        assigned_map.setdefault(int(r["task_id"]), []).append(str(label))

    out: List[Dict[str, Any]] = []
    for t in tasks:
        out.append(
            {
                "id": int(t["id"]),
                "number": t["task_id"] or f"T-{t['id']}",
                "name": t["title"] or "",
                "assigned_teams": assigned_map.get(int(t["id"]), []),
                "status": _task_status_label(t["status"]),
                "priority": _priority_label(t["priority"]),
                "location": t["location"] or "",
            }
        )
    return out


def fetch_team_assignment_rows() -> List[Dict[str, Any]]:
    """Return team rows for the Team Status board based on teams as the source.

    Each dict contains: team_id, sortie, name(label), leader, contact, status,
    assignment (task title if currently assigned), location (task location),
    task_id (current).
    """
    with _connect() as con:
        _ensure_teams_status_columns(con)
        _ensure_teams_current_task_column(con)
        _ensure_teams_name_column(con)
        _ensure_teams_attention_column(con)
        _ensure_team_alert_columns(con)
        has_msg = _has_table(con, "message_log_entry")
        last_msg_select = (
            "(SELECT MAX(timestamp) FROM message_log_entry me WHERE me.sender = COALESCE(tm.callsign, tm.name) OR me.recipient = COALESCE(tm.callsign, tm.name))"
            if has_msg
            else "NULL"
        )
        sql = f"""
            SELECT tm.id AS team_id,
                   tm.current_task_id AS task_id,
                   (SELECT tt2.sortie_id
                      FROM task_teams tt2
                     WHERE tt2.teamid = tm.id
                       AND (tm.current_task_id IS NULL OR tt2.task_id = tm.current_task_id)
                     ORDER BY tt2.id DESC
                     LIMIT 1) AS sortie_id,
                   tm.name AS team_name,
                   t.title AS assignment,
                   t.location AS task_location,
                   tm.status AS team_status,
                   tm.status_updated AS team_status_updated,
                   tm.needs_attention AS needs_attention,
                   tm.emergency_flag AS emergency_flag,
                   tm.last_checkin_at AS last_checkin_at,
                   tm.checkin_reference_at AS checkin_reference_at,
                   {last_msg_select} AS last_msg_ts,
                   p.name AS leader_name,
                   COALESCE(p.phone, p.contact, p.email, '') AS leader_contact
              FROM teams tm
         LEFT JOIN tasks t ON t.id = tm.current_task_id
         LEFT JOIN personnel p ON p.id = tm.team_leader
         ORDER BY tm.id
        """
        rows = con.execute(sql).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        team_id = int(r["team_id"]) if r["team_id"] is not None else None
        # Prefer explicit team name; else use sortie, else synthetic label
        team_label = r["team_name"] or r["sortie_id"] or (f"Team {team_id}" if team_id is not None else "Team")
        ts = r["team_status"] if "team_status" in r.keys() else None
        status = str(ts).strip().lower() if ts else "available"
        status = {
            "en route": "enroute",
            "on scene": "arrival",
            "rtb": "returning",
        }.get(status, status)
        # Compute derived last update as max of team status_updated and latest comms log
        try:
            ts1 = (r["team_status_updated"] or "").strip() if "team_status_updated" in r.keys() else ""
        except Exception:
            ts1 = ""
        try:
            ts2 = (r["last_msg_ts"] or "").strip() if "last_msg_ts" in r.keys() else ""
        except Exception:
            ts2 = ""
        # Choose lexicographically max ISO timestamp if both exist, else whichever is non-empty
        derived_last_updated = None
        if ts1 and ts2:
            derived_last_updated = ts1 if ts1 >= ts2 else ts2
        else:
            derived_last_updated = ts1 or ts2 or None
        needs_attention = r["needs_attention"] if "needs_attention" in r.keys() else 0
        try:
            needs_attention = int(needs_attention)
        except Exception:
            needs_attention = 1 if str(needs_attention).strip().lower() in {"true", "yes", "1"} else 0
        raw_emergency = r["emergency_flag"] if "emergency_flag" in r.keys() else 0
        try:
            emergency_flag = bool(int(raw_emergency))
        except Exception:
            emergency_flag = str(raw_emergency).strip().lower() in {"true", "yes", "1"}
        last_checkin_at = r["last_checkin_at"] if "last_checkin_at" in r.keys() else None
        checkin_reference_at = (
            r["checkin_reference_at"] if "checkin_reference_at" in r.keys() else None
        )
        last_checkin_at = str(last_checkin_at).strip() if last_checkin_at else None
        checkin_reference_at = (
            str(checkin_reference_at).strip() if checkin_reference_at else None
        )
        last_updated = (
            last_checkin_at
            or checkin_reference_at
            or derived_last_updated
        )
        # Only show a sortie number if the team is currently assigned to a task
        # and that task assignment has a sortie id.
        try:
            current_task_id = int(r["task_id"]) if r["task_id"] is not None else None
        except Exception:
            current_task_id = None
        raw_sortie = r["sortie_id"] if "sortie_id" in r.keys() else None
        sortie_display = str(raw_sortie) if (current_task_id is not None and raw_sortie) else ""

        out.append(
            {
                "tt_id": None,
                "task_id": current_task_id,
                "team_id": team_id,
                "sortie": sortie_display,
                "name": str(team_label),
                "leader": r["leader_name"] or "",
                "contact": r["leader_contact"] or "",
                "status": status,
                "assignment": r["assignment"] or "",
                "location": r["task_location"] or "",
                "needs_attention": bool(needs_attention),
                "needs_assistance_flag": bool(needs_attention),
                "emergency_flag": emergency_flag,
                "last_checkin_at": last_checkin_at,
                "checkin_reference_at": checkin_reference_at,
                "team_status_updated": ts1 or None,
                "last_updated": last_updated,
            }
        )
    return out


def touch_team_checkin(
    team_id: int,
    *,
    checkin_time: datetime | None = None,
    reference_time: datetime | None = None,
) -> None:
    """Persist an updated check-in baseline for the given team."""

    check_dt = checkin_time or datetime.now(timezone.utc)
    ref_dt = reference_time or check_dt
    check_iso = _iso_timestamp(check_dt)
    ref_iso = _iso_timestamp(ref_dt)

    with _connect() as con:
        _ensure_team_alert_columns(con)
        con.execute(
            "UPDATE teams SET last_checkin_at=?, checkin_reference_at=? WHERE id=?",
            (check_iso, ref_iso, int(team_id)),
        )
        con.commit()


def set_task_status(task_id: int, status_key: str) -> None:
    """Persist a task status change to the DB.

    status_key should be one of: created, planned, assigned, in progress,
    complete, cancelled. These are mapped to human-readable DB values.
    """
    key = str(status_key).strip().lower()
    to_db = {
        "created": "Draft",
        "planned": "Planned",
        "assigned": "Assigned",
        "in progress": "In Progress",
        "complete": "Completed",
        "cancelled": "Cancelled",
    }.get(key, status_key)
    with _connect() as con:
        con.execute("UPDATE tasks SET status=? WHERE id=?", (to_db, int(task_id)))
        con.commit()


def set_team_assignment_status(tt_id: int, status_key: str) -> None:
    """Persist a team assignment status by stamping the appropriate timestamp.

    Maps common status keys to columns in task_teams: assigned, briefed,
    enroute, arrival(on scene), find(discovery), complete, returning(cleared).
    """
    key = str(status_key).strip().lower()
    col_map = {
        "assigned": "time_assigned",
        "briefed": "time_briefed",
        "enroute": "time_enroute",
        "arrival": "time_arrived",
        "on scene": "time_arrived",
        "find": "time_discovery",
        "discovery": "time_discovery",
        "complete": "time_complete",
        "returning": "time_cleared",
        "rtb": "time_cleared",
    }
    col = col_map.get(key)
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    with _connect() as con:
        # Update task_teams timeline (first instance only if already stamped)
        if col:
            try:
                prev = con.execute(f"SELECT {col} FROM task_teams WHERE id=?", (int(tt_id),)).fetchone()
                already = bool(prev and prev[0])
            except Exception:
                already = False
            if not already:
                con.execute(f"UPDATE task_teams SET {col}=? WHERE id=?", (now, int(tt_id)))
        elif key in {"available"}:
            # Clear all timestamps to represent availability
            con.execute(
                "UPDATE task_teams SET time_assigned=NULL, time_briefed=NULL, time_enroute=NULL, time_arrived=NULL, time_discovery=NULL, time_complete=NULL, time_cleared=NULL WHERE id=?",
                (int(tt_id),),
            )
        # Also maintain team-level status to support unassigned contexts
        try:
            _ensure_teams_status_columns(con)
            trow = con.execute("SELECT teamid FROM task_teams WHERE id=?", (int(tt_id),)).fetchone()
            if trow and trow[0] is not None:
                team_id = int(trow[0])
                display = {
                    "enroute": "En Route",
                    "on scene": "On Scene",
                    "arrival": "On Scene",
                    "rtb": "RTB",
                }.get(key, str(status_key).title())
                con.execute("UPDATE teams SET status=?, status_updated=? WHERE id=?", (display, now, team_id))
        except Exception:
            pass
        con.commit()
        # Notify UI that team status changed (if team_id is known)
        try:
            if 'team_id' in locals() and team_id is not None:
                from utils.app_signals import app_signals
                app_signals.teamStatusChanged.emit(int(team_id))
        except Exception:
            pass


def set_team_status(team_id: int, status_key: str) -> None:
    """Persist team-level status and stamp timeline for current assignment.

    Updates teams.status/status_updated, and if the team is currently assigned,
    stamps the appropriate time_* on a task_teams row for auditing.
    """
    key = str(status_key).strip().lower()
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    display = {
        "enroute": "En Route",
        "on scene": "On Scene",
        "arrival": "On Scene",
        "rtb": "RTB",
    }.get(key, str(status_key).title())
    col_map = {
        "assigned": "time_assigned",
        "briefed": "time_briefed",
        "enroute": "time_enroute",
        "arrival": "time_arrived",
        "on scene": "time_arrived",
        "find": "time_discovery",
        "discovery": "time_discovery",
        "complete": "time_complete",
        "returning": "time_cleared",
        "rtb": "time_cleared",
    }
    with _connect() as con:
        _ensure_teams_status_columns(con)
        _ensure_teams_current_task_column(con)
        con.execute(
            "UPDATE teams SET status=?, status_updated=? WHERE id=?",
            (display, now, int(team_id)),
        )
        row = con.execute(
            "SELECT current_task_id FROM teams WHERE id=?",
            (int(team_id),),
        ).fetchone()
        task_id = int(row[0]) if row and row[0] is not None else None
        if task_id and key in col_map:
            tt = con.execute(
                "SELECT id FROM task_teams WHERE task_id=? AND teamid=? ORDER BY id DESC LIMIT 1",
                (task_id, int(team_id)),
            ).fetchone()
            if tt:
                tt_id = int(tt[0])
            else:
                cur = con.execute(
                    "INSERT INTO task_teams (task_id, teamid, is_primary) VALUES (?, ?, 0)",
                    (task_id, int(team_id)),
                )
                tt_id = int(cur.lastrowid)
            col = col_map[key]
            con.execute(f"UPDATE task_teams SET {col}=? WHERE id=?", (now, tt_id))
        con.commit()
        # Emit teamStatusChanged for UI timers
        try:
            from utils.app_signals import app_signals
            app_signals.teamStatusChanged.emit(int(team_id))
        except Exception:
            pass
