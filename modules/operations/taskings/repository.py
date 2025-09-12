from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from utils import incident_context
from .models import Task, TaskTeam, TaskDetail


def _connect() -> sqlite3.Connection:
    db_path = incident_context.get_active_incident_db_path()
    con = sqlite3.connect(os.path.abspath(str(db_path)))
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=3000")
    except Exception:
        pass
    return con


def _task_status_to_key(value: Any) -> str:
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


def _team_status_from_timestamps(r: sqlite3.Row) -> str:
    def _val(key: str):
        try:
            return r[key]
        except Exception:
            return None
    if _val("time_cleared"):
        return "RTB"
    if _val("time_complete"):
        return "Complete"
    if _val("time_arrived"):
        return "On Scene"
    if _val("time_enroute"):
        return "En Route"
    if _val("time_briefed"):
        return "Briefed"
    if _val("time_assigned"):
        return "Assigned"
    return "Assigned"


def get_task(task_id: int) -> Task:
    with _connect() as con:
        _ensure_task_columns(con)
        row = con.execute(
            "SELECT id, task_id, title, priority, status, location, category, task_type,"
            " COALESCE('', created_by) AS created_by, created_at, due_time,"
            " COALESCE(assignment,'') AS assignment, COALESCE(team_leader,'') AS team_leader, COALESCE(team_phone,'') AS team_phone"
            " FROM tasks WHERE id=?",
            (int(task_id),),
        ).fetchone()
        if not row:
            raise ValueError(f"Task id not found: {task_id}")
    return Task(
        id=int(row["id"]),
        task_id=row["task_id"] or f"T-{row['id']}",
        title=row["title"] or "",
        description="",
        category=row["category"] or "<New Task>",
        task_type=row["task_type"] or None,  # mapping for task_type_id can be added later
        priority={1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(
            int(row["priority"]) if row["priority"] is not None else 0, str(row["priority"] or "")
        ),
        status=_task_status_to_key(row["status"]).title() if row["status"] else "",
        location=row["location"] or "",
        created_by=row["created_by"] or "",
        created_at=row["created_at"] or "",
        assigned_to=None,
        due_time=row["due_time"] or None,
        assignment=row["assignment"] or "",
        team_leader=row["team_leader"] or "",
        team_phone=row["team_phone"] or "",
    )


def _ensure_task_columns(con: sqlite3.Connection) -> None:
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(tasks)").fetchall()}
        if "category" not in cols:
            con.execute("ALTER TABLE tasks ADD COLUMN category TEXT")
        if "task_type" not in cols:
            con.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT")
        if "location" not in cols:
            con.execute("ALTER TABLE tasks ADD COLUMN location TEXT")
        if "assignment" not in cols:
            con.execute("ALTER TABLE tasks ADD COLUMN assignment TEXT")
        if "team_leader" not in cols:
            con.execute("ALTER TABLE tasks ADD COLUMN team_leader TEXT")
        if "team_phone" not in cols:
            con.execute("ALTER TABLE tasks ADD COLUMN team_phone TEXT")
        con.commit()
    except Exception:
        pass


def _priority_to_db(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    if s in mapping:
        return mapping[s]
    try:
        i = int(value)
        return i
    except Exception:
        return None


def _status_to_db(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    inv = {
        "created": "Draft",
        "draft": "Draft",
        "planned": "Planned",
        "assigned": "Assigned",
        "in progress": "In Progress",
        "complete": "Completed",
        "completed": "Completed",
        "cancelled": "Cancelled",
    }
    return inv.get(s, str(value))


def update_task_header(task_id: int, patch: Dict[str, Any]) -> None:
    """Persist task toolbar metadata: id, title, category, task_type, priority, status, location."""
    patch = dict(patch or {})
    with _connect() as con:
        _ensure_task_columns(con)
        cols: Dict[str, Any] = {}
        if "task_id" in patch:
            cols["task_id"] = str(patch["task_id"]) or None
        if "title" in patch:
            cols["title"] = str(patch["title"]) or None
        if "category" in patch:
            cols["category"] = str(patch["category"]) or None
        if "task_type" in patch:
            cols["task_type"] = str(patch["task_type"]) or None
        if "priority" in patch:
            cols["priority"] = _priority_to_db(patch["priority"])  # int mapping
        if "status" in patch:
            cols["status"] = _status_to_db(patch["status"])  # label mapping
        if "location" in patch:
            cols["location"] = str(patch["location"]) or None
        if "assignment" in patch:
            cols["assignment"] = str(patch["assignment"]) or None
        if "team_leader" in patch:
            cols["team_leader"] = str(patch["team_leader"]) or None
        if "team_phone" in patch:
            cols["team_phone"] = str(patch["team_phone"]) or None
        if not cols:
            return
        set_clause = ", ".join([f"{k}=?" for k in cols.keys()])
        vals = list(cols.values()) + [int(task_id)]
        con.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", vals)
        con.commit()


def list_task_teams(task_id: int) -> List[TaskTeam]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT tt.id AS id,
                   tt.teamid AS team_id,
                   tt.sortie_id AS sortie_id,
                   tt.is_primary AS is_primary,
                   tt.time_assigned, tt.time_briefed, tt.time_enroute,
                   tt.time_arrived, tt.time_discovery, tt.time_complete, tt.time_cleared,
                   tm.name AS team_name,
                   p.name AS leader_name,
                   COALESCE(p.phone, p.contact, p.email, '') AS leader_contact
            FROM task_teams tt
            LEFT JOIN teams tm ON tm.id = tt.teamid
            LEFT JOIN personnel p ON p.id = tm.team_leader
            WHERE tt.task_id=?
            ORDER BY tt.id
            """,
            (int(task_id),),
        ).fetchall()
    out: List[TaskTeam] = []
    for r in rows:
        # Prefer explicit team name; else fall back to synthetic label
        try:
            explicit_name = r["team_name"] if "team_name" in r.keys() else None
        except Exception:
            explicit_name = None
        team_label = explicit_name or (f"Team {r['team_id']}" if r["team_id"] is not None else "Team")
        out.append(
            TaskTeam(
                id=int(r["id"]),
                team_id=int(r["team_id"]) if r["team_id"] is not None else 0,
                team_name=str(team_label),
                team_leader=r["leader_name"] or "",
                team_leader_phone=r["leader_contact"] or "",
                status=_team_status_from_timestamps(r),
                sortie_number=r["sortie_id"],
                assigned_ts=r["time_assigned"],
                briefed_ts=r["time_briefed"],
                enroute_ts=r["time_enroute"],
                arrival_ts=r["time_arrived"],
                discovery_ts=r["time_discovery"],
                complete_ts=r["time_complete"],
                primary=bool(r["is_primary"]) if r["is_primary"] is not None else False,
            )
        )
    return out


def list_task_personnel(task_id: int) -> List[Dict[str, Any]]:
    """List personnel assigned to teams on this task.

    Returns dicts with: active(bool), name, id, rank, role, organization, phone, team_name, team_id.
    Active is True if the team assignment is not complete/cleared.
    """
    with _connect() as con:
        # Best-effort column detection for optional fields
        try:
            pcols = {r[1] for r in con.execute("PRAGMA table_info(personnel)").fetchall()}
        except Exception:
            pcols = set()
        has_rank = "rank" in pcols
        has_org = "organization" in pcols
        sel_rank = ", p.rank AS rank" if has_rank else ", NULL AS rank"
        sel_org = ", p.organization AS organization" if has_org else ", NULL AS organization"
        sql = (
            "SELECT p.id AS person_id, p.name AS name, p.role AS role, p.phone AS phone,"
            "       tm.name AS team_name, tm.id AS team_id,"
            "       tt.time_assigned, tt.time_briefed, tt.time_enroute, tt.time_arrived, tt.time_discovery, tt.time_complete, tt.time_cleared"
            f"      {sel_rank}{sel_org}"
            "  FROM task_teams tt"
            "  JOIN teams tm ON tm.id = tt.teamid"
            "  JOIN personnel p ON p.team_id = tm.id"
            " WHERE tt.task_id = ?"
            " ORDER BY p.name COLLATE NOCASE"
        )
        rows = con.execute(sql, (int(task_id),)).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        status = _team_status_from_timestamps(r)
        active = status not in {"Complete", "RTB"}
        out.append({
            "active": bool(active),
            "name": r["name"] or "",
            "id": r["person_id"],
            "rank": r.get("rank"),
            "role": r["role"] or "",
            "organization": r.get("organization"),
            "phone": r["phone"] or "",
            "team_name": r["team_name"] or "",
            "team_id": r["team_id"],
        })
    return out


def _has_column(con: sqlite3.Connection, table: str, col: str) -> bool:
    try:
        cur = con.execute(f"PRAGMA table_info({table})")
        return any(row[1] == col for row in cur.fetchall())
    except Exception:
        return False


def list_task_vehicles(task_id: int) -> List[Dict[str, Any]]:
    """List vehicles assigned to teams on this task.

    Returns: active(bool), id, license_plate, type, organization, team_name, team_id.
    """
    with _connect() as con:
        has_lp = _has_column(con, "vehicles", "license_plate")
        has_org = _has_column(con, "vehicles", "organization")
        sel_lp = ", v.license_plate AS license_plate" if has_lp else ", NULL AS license_plate"
        sel_org = ", v.organization AS organization" if has_org else ", NULL AS organization"
        # Fallbacks for some common schemas
        sel_type = "v.type AS type" if _has_column(con, "vehicles", "type") else ("v.make || ' ' || v.model AS type" if _has_column(con, "vehicles", "make") and _has_column(con, "vehicles", "model") else "'' AS type")
        sql = (
            "SELECT v.id AS id, " + sel_type +
            sel_lp + sel_org +
            ", tm.name AS team_name, tm.id AS team_id,"
            " tt.time_assigned, tt.time_briefed, tt.time_enroute, tt.time_arrived, tt.time_discovery, tt.time_complete, tt.time_cleared"
            "  FROM task_teams tt"
            "  JOIN teams tm ON tm.id = tt.teamid"
            "  JOIN vehicles v ON v.team_id = tm.id"
            " WHERE tt.task_id = ?"
            " ORDER BY v.id"
        )
        rows = con.execute(sql, (int(task_id),)).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        status = _team_status_from_timestamps(r)
        active = status not in {"Complete", "RTB"}
        out.append({
            "active": bool(active),
            "id": r["id"],
            "license_plate": r.get("license_plate"),
            "type": r.get("type") or "",
            "organization": r.get("organization"),
            "team_name": r.get("team_name") or "",
            "team_id": r.get("team_id"),
        })
    return out


def list_task_aircraft(task_id: int) -> List[Dict[str, Any]]:
    """List aircraft assigned to teams on this task.

    Returns: active(bool), callsign, tail_number, type, organization, team_name, team_id.
    """
    with _connect() as con:
        has_org = _has_column(con, "aircraft", "organization")
        sel_org = ", a.organization AS organization" if has_org else ", NULL AS organization"
        # type field may be named make_model in some schemas
        sel_type = "a.type AS type" if _has_column(con, "aircraft", "type") else ("a.make_model AS type" if _has_column(con, "aircraft", "make_model") else "'' AS type")
        sql = (
            "SELECT a.id AS id, a.callsign AS callsign, a.tail_number AS tail_number, " + sel_type +
            sel_org +
            ", tm.name AS team_name, tm.id AS team_id,"
            " tt.time_assigned, tt.time_briefed, tt.time_enroute, tt.time_arrived, tt.time_discovery, tt.time_complete, tt.time_cleared"
            "  FROM task_teams tt"
            "  JOIN teams tm ON tm.id = tt.teamid"
            "  JOIN aircraft a ON a.team_id = tm.id"
            " WHERE tt.task_id = ?"
            " ORDER BY a.tail_number COLLATE NOCASE, a.callsign COLLATE NOCASE"
        )
        rows = con.execute(sql, (int(task_id),)).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        status = _team_status_from_timestamps(r)
        active = status not in {"Complete", "RTB"}
        out.append({
            "active": bool(active),
            "callsign": r.get("callsign") or "",
            "tail_number": r.get("tail_number") or "",
            "type": r.get("type") or "",
            "organization": r.get("organization"),
            "team_name": r.get("team_name") or "",
            "team_id": r.get("team_id"),
        })
    return out


# --- Task Assignment (Ground/Air details) ------------------------------------

def _ensure_task_assignments_table(con: sqlite3.Connection) -> None:
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS task_assignments (
                task_id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        con.commit()
    except Exception:
        pass


def get_task_assignment(task_id: int) -> Dict[str, Any]:
    """Return assignment details for a task as a dict (may be empty)."""
    with _connect() as con:
        _ensure_task_assignments_table(con)
        row = con.execute(
            "SELECT data FROM task_assignments WHERE task_id=?",
            (int(task_id),),
        ).fetchone()
        if not row:
            return {}
        try:
            import json
            return json.loads(row[0] or "{}")
        except Exception:
            return {}


def save_task_assignment(task_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert assignment data as JSON; returns the persisted dict."""
    import json
    from datetime import datetime
    payload = dict(data or {})
    now = datetime.utcnow().isoformat()
    js = json.dumps(payload)
    with _connect() as con:
        _ensure_task_assignments_table(con)
        cur = con.execute(
            "UPDATE task_assignments SET data=?, updated_at=? WHERE task_id=?",
            (js, now, int(task_id)),
        )
        if cur.rowcount == 0:
            con.execute(
                "INSERT INTO task_assignments (task_id, data, updated_at) VALUES (?,?,?)",
                (int(task_id), js, now),
            )
        con.commit()
    return payload


def export_assignment_forms(task_id: int, forms: List[str]) -> List[Dict[str, Any]]:
    """Create placeholder exports for selected forms (ICS 204, CAPF 109, SAR 104).

    Writes JSON snapshots of the assignment data to data/exports and returns
    a list of dicts: { form: str, file_path: str }.
    """
    from pathlib import Path
    from datetime import datetime
    import json
    # Fetch data
    data = get_task_assignment(int(task_id))
    out: List[Dict[str, Any]] = []
    try:
        from utils import incident_context
        incident_id = incident_context.get_active_incident_id() or "unknown"
    except Exception:
        incident_id = "unknown"
    base = Path("data") / "exports" / str(incident_id)
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for f in (forms or []):
        key = str(f).strip().upper().replace(" ", "_")
        name = f"{key}_task{int(task_id)}_{ts}.json"
        p = base / name
        payload = {"form": key, "task_id": int(task_id), "assignment": data}
        try:
            p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            out.append({"form": key, "file_path": str(p)})
        except Exception:
            continue
    return out


# --- Task Communications (link to ICS-205 incident channels) -----------------

def _ensure_task_comms_table(con: sqlite3.Connection) -> None:
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS task_comms (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                incident_channel_id INTEGER,
                function TEXT,
                remarks TEXT
            )
            """
        )
        con.commit()
    except Exception:
        pass


def list_incident_channels() -> List[Dict[str, Any]]:
    """Return available incident channels from ICS-205 plan (if present)."""
    with _connect() as con:
        try:
            cur = con.execute(
                "SELECT id, channel, system, mode, rx_freq, tx_freq, rx_tone, tx_tone, remarks, sort_index FROM incident_channels ORDER BY sort_index, id"
            )
            rows = cur.fetchall()
        except Exception:
            return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": int(r["id"]),
            "channel": r["channel"],
            "system": r.get("system"),
            "mode": r.get("mode"),
            "rx_freq": r.get("rx_freq"),
            "tx_freq": r.get("tx_freq"),
            "rx_tone": r.get("rx_tone"),
            "tx_tone": r.get("tx_tone"),
            "remarks": r.get("remarks"),
            "sort_index": r.get("sort_index"),
        })
    return out


def list_task_comms(task_id: int) -> List[Dict[str, Any]]:
    """Return communications rows linked to a task enriched with ICS-205 details."""
    with _connect() as con:
        _ensure_task_comms_table(con)
        try:
            sql = (
                "SELECT tc.id AS id, tc.task_id, tc.incident_channel_id, tc.function, tc.remarks,"
                "       ic.channel, ic.system, ic.mode, ic.rx_freq, ic.tx_freq, ic.rx_tone, ic.tx_tone, ic.remarks AS ic_remarks, ic.sort_index"
                "  FROM task_comms tc"
                "  LEFT JOIN incident_channels ic ON ic.id = tc.incident_channel_id"
                " WHERE tc.task_id = ?"
                " ORDER BY tc.id"
            )
            rows = con.execute(sql, (int(task_id),)).fetchall()
        except Exception:
            rows = []
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": int(r["id"]),
            "incident_channel_id": r.get("incident_channel_id"),
            "channel_name": r.get("channel") or "",
            "zone": r.get("system") or "",
            "channel_number": r.get("sort_index"),
            "function": r.get("function") or "",
            "rx_frequency": r.get("rx_freq"),
            "rx_tone": r.get("rx_tone"),
            "tx_frequency": r.get("tx_freq"),
            "tx_tone": r.get("tx_tone"),
            "mode": r.get("mode") or "",
            "remarks": r.get("remarks") or r.get("ic_remarks") or "",
        })
    return out


def add_task_comm(task_id: int, incident_channel_id: Optional[int] = None, function: Optional[str] = None, remarks: Optional[str] = None) -> int:
    with _connect() as con:
        _ensure_task_comms_table(con)
        cur = con.execute(
            "INSERT INTO task_comms (task_id, incident_channel_id, function, remarks) VALUES (?, ?, ?, ?)",
            (int(task_id), int(incident_channel_id) if incident_channel_id is not None else None, function, remarks),
        )
        con.commit()
        return int(cur.lastrowid)


def update_task_comm(row_id: int, incident_channel_id: Optional[int] = None, function: Optional[str] = None) -> None:
    patch: Dict[str, Any] = {}
    if incident_channel_id is not None:
        patch["incident_channel_id"] = int(incident_channel_id)
    if function is not None:
        patch["function"] = str(function)
    if not patch:
        return
    with _connect() as con:
        _ensure_task_comms_table(con)
        cols = ", ".join(f"{k}=?" for k in patch.keys())
        vals = list(patch.values()) + [int(row_id)]
        con.execute(f"UPDATE task_comms SET {cols} WHERE id=?", vals)
        con.commit()


def remove_task_comm(row_id: int) -> None:
    with _connect() as con:
        _ensure_task_comms_table(con)
        con.execute("DELETE FROM task_comms WHERE id=?", (int(row_id),))
        con.commit()


# --- Debriefing --------------------------------------------------------------

def _ensure_task_debrief_tables(con: sqlite3.Connection) -> None:
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS task_debriefs (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                sortie_number TEXT,
                debriefer_id TEXT,
                types TEXT NOT NULL,
                status TEXT DEFAULT 'Draft',
                flagged_for_review INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS task_debrief_forms (
                id INTEGER PRIMARY KEY,
                debrief_id INTEGER NOT NULL,
                form_key TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(debrief_id, form_key)
            )
            """
        )
        con.commit()
    except Exception:
        pass
    # Add optional columns if missing
    try:
        cur = con.execute("PRAGMA table_info(task_debriefs)")
        cols = {row[1] for row in cur.fetchall()}
        adds: list[tuple[str, str]] = []
        if "submitted_by" not in cols:
            adds.append(("submitted_by", "TEXT"))
        if "submitted_at" not in cols:
            adds.append(("submitted_at", "TEXT"))
        if "reviewed_by" not in cols:
            adds.append(("reviewed_by", "TEXT"))
        if "reviewed_at" not in cols:
            adds.append(("reviewed_at", "TEXT"))
        for name, typ in adds:
            try:
                con.execute(f"ALTER TABLE task_debriefs ADD COLUMN {name} {typ}")
            except Exception:
                pass
        con.commit()
    except Exception:
        pass


def list_task_debriefs(task_id: int) -> List[Dict[str, Any]]:
    with _connect() as con:
        _ensure_task_debrief_tables(con)
        rows = con.execute(
            "SELECT id, sortie_number, debriefer_id, types, status, flagged_for_review, created_at, updated_at, submitted_by, submitted_at, reviewed_by, reviewed_at"
            "  FROM task_debriefs WHERE task_id=? ORDER BY updated_at DESC, id DESC",
            (int(task_id),),
        ).fetchall()
    out: List[Dict[str, Any]] = []
    import json
    for r in rows:
        try:
            types = json.loads(r["types"]) if r["types"] else []
        except Exception:
            types = []
        out.append({
            "id": int(r["id"]),
            "sortie_number": r.get("sortie_number"),
            "debriefer_id": r.get("debriefer_id"),
            "types": types,
            "status": r.get("status") or "Draft",
            "flagged_for_review": bool(r.get("flagged_for_review") or 0),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "submitted_by": r.get("submitted_by"),
            "submitted_at": r.get("submitted_at"),
            "reviewed_by": r.get("reviewed_by"),
            "reviewed_at": r.get("reviewed_at"),
        })
    return out


def create_debrief(task_id: int, sortie_number: str, debriefer_id: str, types: List[str]) -> int:
    from datetime import datetime
    import json
    now = datetime.utcnow().isoformat()
    with _connect() as con:
        _ensure_task_debrief_tables(con)
        cur = con.execute(
            "INSERT INTO task_debriefs (task_id, sortie_number, debriefer_id, types, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'Draft', ?, ?)",
            (int(task_id), sortie_number, debriefer_id, json.dumps(list(types or [])), now, now),
        )
        con.commit()
        return int(cur.lastrowid)


def update_debrief_header(debrief_id: int, patch: Dict[str, Any]) -> None:
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    with _connect() as con:
        _ensure_task_debrief_tables(con)
        patch = dict(patch or {})
        patch["updated_at"] = now
        cols = ", ".join(f"{k}=?" for k in patch.keys())
        vals = list(patch.values()) + [int(debrief_id)]
        con.execute(f"UPDATE task_debriefs SET {cols} WHERE id=?", vals)
        con.commit()


def save_debrief_form(debrief_id: int, form_key: str, data: Dict[str, Any]) -> None:
    from datetime import datetime
    import json
    now = datetime.utcnow().isoformat()
    js = json.dumps(dict(data or {}))
    with _connect() as con:
        _ensure_task_debrief_tables(con)
        cur = con.execute(
            "UPDATE task_debrief_forms SET data=?, updated_at=? WHERE debrief_id=? AND form_key=?",
            (js, now, int(debrief_id), str(form_key)),
        )
        if cur.rowcount == 0:
            con.execute(
                "INSERT INTO task_debrief_forms (debrief_id, form_key, data, updated_at) VALUES (?,?,?,?)",
                (int(debrief_id), str(form_key), js, now),
            )
        con.commit()


def get_debrief(debrief_id: int) -> Dict[str, Any]:
    with _connect() as con:
        _ensure_task_debrief_tables(con)
        head = con.execute(
            "SELECT id, task_id, sortie_number, debriefer_id, types, status, flagged_for_review, created_at, updated_at, submitted_by, submitted_at, reviewed_by, reviewed_at"
            "  FROM task_debriefs WHERE id=?",
            (int(debrief_id),),
        ).fetchone()
        forms = con.execute(
            "SELECT form_key, data, updated_at FROM task_debrief_forms WHERE debrief_id=?",
            (int(debrief_id),),
        ).fetchall()
    if not head:
        return {}
    import json
    try:
        types = json.loads(head["types"]) if head["types"] else []
    except Exception:
        types = []
    out: Dict[str, Any] = {
        "id": int(head["id"]),
        "task_id": head["task_id"],
        "sortie_number": head["sortie_number"],
        "debriefer_id": head["debriefer_id"],
        "types": types,
        "status": head["status"],
        "flagged_for_review": bool(head["flagged_for_review"] or 0),
        "created_at": head["created_at"],
        "updated_at": head["updated_at"],
        "submitted_by": head.get("submitted_by"),
        "submitted_at": head.get("submitted_at"),
        "reviewed_by": head.get("reviewed_by"),
        "reviewed_at": head.get("reviewed_at"),
        "forms": {},
    }
    for r in forms:
        try:
            out["forms"][r["form_key"]] = json.loads(r["data"] or "{}")
        except Exception:
            out["forms"][r["form_key"]] = {}
    return out


def archive_debrief(debrief_id: int) -> None:
    update_debrief_header(int(debrief_id), {"status": "Archived", "flagged_for_review": 0})


def delete_debrief(debrief_id: int) -> None:
    with _connect() as con:
        _ensure_task_debrief_tables(con)
        con.execute("DELETE FROM task_debrief_forms WHERE debrief_id=?", (int(debrief_id),))
        con.execute("DELETE FROM task_debriefs WHERE id=?", (int(debrief_id),))
        con.commit()


# --- Log/Audit ---------------------------------------------------------------

def _audit_has_column(con: sqlite3.Connection, name: str) -> bool:
    try:
        cols = {row[1] for row in con.execute("PRAGMA table_info(audit_logs)").fetchall()}
        return name in cols
    except Exception:
        return False


def list_audit_logs(task_id: Optional[int] = None, search: str = "", date_from: Optional[str] = None, date_to: Optional[str] = None, field_filter: str = "", limit: int = 500) -> List[Dict[str, Any]]:
    """Return audit log rows filtered for the current incident, optionally scoped to a task.

    Attempts to filter by task using either an explicit taskid column (if present)
    or a JSON substring match on detail containing "task_id": task_id.
    """
    with _connect() as con:
        try:
            cols = {row[1] for row in con.execute("PRAGMA table_info(audit_logs)").fetchall()}
        except Exception:
            cols = set()
        select = "SELECT id, ts_utc, user_id, action, detail"
        # Include legacy/extended columns if present
        extra = []
        for c in ("field_changed", "old_value", "new_value", "changed_by", "timestamp", "incident_number", "taskid"):
            if c in cols:
                extra.append(c)
        if extra:
            select += ", " + ", ".join(extra)
        where: List[str] = []
        params: List[Any] = []
        if date_from:
            where.append("ts_utc >= ?")
            params.append(str(date_from))
        if date_to:
            where.append("ts_utc <= ?")
            params.append(str(date_to))
        if field_filter:
            if "field_changed" in cols:
                where.append("field_changed LIKE ?")
                params.append(f"%{field_filter}%")
            else:
                where.append("action LIKE ?")
                params.append(f"%{field_filter}%")
        if search:
            where.append("(action LIKE ? OR detail LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if task_id is not None:
            if "taskid" in cols:
                where.append("taskid = ?")
                params.append(int(task_id))
            else:
                where.append("detail LIKE ?")
                params.append(f"%\"task_id\": {int(task_id)}%")
        sql = select + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        try:
            rows = con.execute(sql, params).fetchall()
        except Exception:
            rows = []
        # Resolve changed_by if possible
        out: List[Dict[str, Any]] = []
        for r in rows:
            d: Dict[str, Any] = {k: r[k] for k in r.keys()}
            # Preferred changed_by column, else fall back to user_id
            changer = d.get("changed_by") if "changed_by" in d else d.get("user_id")
            disp = None
            try:
                uid = int(changer) if changer is not None else None
            except Exception:
                uid = None
            if uid is not None:
                try:
                    prow = con.execute("SELECT name FROM personnel WHERE id=?", (uid,)).fetchone()
                    disp = prow["name"] if prow and prow.get("name") else str(uid)
                except Exception:
                    disp = str(uid)
            d["changed_by_display"] = disp or (str(changer) if changer is not None else "")
            out.append(d)
        return out


def export_audit_csv(task_id: Optional[int] = None, search: str = "", date_from: Optional[str] = None, date_to: Optional[str] = None, field_filter: str = "") -> str:
    rows = list_audit_logs(task_id, search, date_from, date_to, field_filter, limit=5000)
    from pathlib import Path
    from datetime import datetime
    try:
        from utils import incident_context
        incident_id = incident_context.get_active_incident_id() or "unknown"
    except Exception:
        incident_id = "unknown"
    out_dir = Path("data") / "exports" / str(incident_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    name = f"audit_task_{task_id or 'all'}_{ts}.csv"
    p = out_dir / name
    import csv
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "ts_utc", "field_changed", "old_value", "new_value", "action", "changed_by"])
        for r in rows:
            w.writerow([
                r.get("id"),
                r.get("ts_utc") or r.get("timestamp"),
                r.get("field_changed", ""),
                r.get("old_value", ""),
                r.get("new_value", ""),
                r.get("action", ""),
                r.get("changed_by_display", ""),
            ])
    return str(p)


def get_task_detail(task_id: int) -> TaskDetail:
    task = get_task(task_id)
    teams = list_task_teams(task_id)
    return TaskDetail(task=task, teams=teams, narrative=[])


# --- CRUD helpers for teams and assignments ---

def create_team(team_leader_id: Optional[int] = None) -> int:
    """Create a minimal team row and return its id.

    Initializes JSON fields as empty arrays.
    """
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO teams (team_leader, personnel, vehicles, equipment) VALUES (?, '[]', '[]', '[]')",
            (int(team_leader_id) if team_leader_id is not None else None,),
        )
        con.commit()
        return int(cur.lastrowid)


def add_task_team(task_id: int, team_id: Optional[int] = None, sortie_id: Optional[str] = None, primary: bool = False) -> int:
    """Assign a team to a task. Creates a team if team_id is None.

    Returns the task_teams id.
    """
    if team_id is None:
        team_id = create_team(None)
    # Auto-primary if first assignment for the task and primary not explicitly set
    with _connect() as con:
        existing = con.execute("SELECT COUNT(*) FROM task_teams WHERE task_id=?", (int(task_id),)).fetchone()[0]
        is_primary = 1 if (primary or existing == 0) else 0
        cur = con.execute(
            "INSERT INTO task_teams (task_id, teamid, sortie_id, is_primary) VALUES (?, ?, ?, ?)",
            (int(task_id), int(team_id), sortie_id, is_primary),
        )
        # Also set current assignment on teams
        try:
            con.execute("ALTER TABLE teams ADD COLUMN current_task_id INTEGER")
        except Exception:
            pass
        con.execute("UPDATE teams SET current_task_id=? WHERE id=?", (int(task_id), int(team_id)))
        con.commit()
        return int(cur.lastrowid)


def set_primary_team(task_id: int, tt_id: int) -> None:
    """Set a specific task_teams row as primary and clear others for the task.

    Also ensures the underlying team's current_task_id points to this task.
    """
    with _connect() as con:
        con.execute("UPDATE task_teams SET is_primary=0 WHERE task_id=?", (int(task_id),))
        con.execute("UPDATE task_teams SET is_primary=1 WHERE id=?", (int(tt_id),))
        # Update teams.current_task_id to reflect active assignment
        try:
            row = con.execute("SELECT teamid FROM task_teams WHERE id=?", (int(tt_id),)).fetchone()
            if row and row[0] is not None:
                con.execute("UPDATE teams SET current_task_id=? WHERE id=?", (int(task_id), int(row[0])))
        except Exception:
            pass
        con.commit()


def update_sortie_id(tt_id: int, sortie_id: Optional[str]) -> None:
    """Update the sortie identifier for a task_teams row."""
    with _connect() as con:
        con.execute("UPDATE task_teams SET sortie_id=? WHERE id=?", (str(sortie_id) if sortie_id is not None else None, int(tt_id)))
        con.commit()


def remove_task_team(tt_id: int) -> None:
    """Remove a team assignment from a task. Does not delete the team.

    If the removed assignment was primary, promote the most recent remaining assignment to primary.
    """
    with _connect() as con:
        row = con.execute("SELECT task_id, is_primary FROM task_teams WHERE id=?", (int(tt_id),)).fetchone()
        if not row:
            return
        task_id = int(row["task_id"]) if row["task_id"] is not None else None
        was_primary = bool(row["is_primary"]) if row["is_primary"] is not None else False
        con.execute("DELETE FROM task_teams WHERE id=?", (int(tt_id),))
        if task_id is not None and was_primary:
            nxt = con.execute("SELECT id FROM task_teams WHERE task_id=? ORDER BY id LIMIT 1", (task_id,)).fetchone()
            if nxt:
                con.execute("UPDATE task_teams SET is_primary=1 WHERE id=?", (int(nxt[0]),))
        con.commit()


def list_all_teams() -> List[Dict[str, Any]]:
    """Return a list of all teams with basic display fields for selection dialogs."""
    with _connect() as con:
        # Ensure common columns exist
        from modules.operations.data.repository import _ensure_teams_status_columns, _ensure_teams_name_column
        _ensure_teams_status_columns(con)
        _ensure_teams_name_column(con)
        rows = con.execute(
            """
            SELECT tm.id AS team_id,
                   tm.name AS team_name,
                   p.name AS leader_name,
                   COALESCE(p.phone, p.contact, p.email, '') AS leader_contact
              FROM teams tm
         LEFT JOIN personnel p ON p.id = tm.team_leader
             ORDER BY tm.id
            """
        ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "team_id": int(r["team_id"]) if r["team_id"] is not None else 0,
            "team_name": r["team_name"] or f"Team {r['team_id']}",
            "team_leader": r["leader_name"] or "",
            "team_leader_phone": r["leader_contact"] or "",
        })
    return out


def create_task(title: str = "<New Task>", task_identifier: Optional[str] = None, priority: int = 2, status: str = "Draft") -> int:
    """Create a minimal task and return its id.

    Ensures required columns are provided for common tasks schema.
    """
    from datetime import datetime
    created_at = datetime.utcnow().isoformat()
    with _connect() as con:
        # Generate next task_id if not provided (T-###)
        tid = task_identifier
        if not tid:
            try:
                row = con.execute("SELECT task_id FROM tasks WHERE task_id LIKE 'T-%' ORDER BY id DESC LIMIT 1").fetchone()
                if row and row[0] and str(row[0]).startswith("T-"):
                    try:
                        n = int(str(row[0])[2:]) + 1
                    except Exception:
                        n = 1
                else:
                    cnt = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                    n = int(cnt) + 1
                tid = f"T-{n:03d}"
            except Exception:
                tid = None
        con.execute(
            "INSERT INTO tasks (task_id, title, priority, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (tid, title, int(priority), status, created_at),
        )
        new_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        con.commit()
        return new_id
