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
        row = con.execute(
            "SELECT id, task_id, title, priority, status, location,"
            " COALESCE('', created_by) AS created_by, created_at, due_time"
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
        category="<New Task>",
        task_type=None,  # mapping for task_type_id can be added later
        priority={1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(
            int(row["priority"]) if row["priority"] is not None else 0, str(row["priority"] or "")
        ),
        status=_task_status_to_key(row["status"]).title() if row["status"] else "",
        location=row["location"] or "",
        created_by=row["created_by"] or "",
        created_at=row["created_at"] or "",
        assigned_to=None,
        due_time=row["due_time"] or None,
    )


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
        team_label = r["sortie_id"] or (f"Team {r['team_id']}" if r["team_id"] is not None else "Team")
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
