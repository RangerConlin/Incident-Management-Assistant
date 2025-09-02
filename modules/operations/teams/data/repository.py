from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Optional

from .team import Team
from modules.operations.data.repository import _connect as _incident_connect  # reuse incident DB connection


def _ensure_team_columns(con: sqlite3.Connection) -> None:
    """Best-effort ensure extended team columns exist.

    Adds lightweight JSON and metadata columns used by Team Detail.
    Safe to run repeatedly.
    """
    cols = {r[1] for r in con.execute("PRAGMA table_info(teams)").fetchall()}
    to_add: list[tuple[str, str]] = []
    # Simple metadata
    if "name" not in cols:
        to_add.append(("name", "TEXT"))
    if "callsign" not in cols:
        to_add.append(("callsign", "TEXT"))
    if "role" not in cols:
        to_add.append(("role", "TEXT"))
    if "priority" not in cols:
        to_add.append(("priority", "INTEGER"))
    if "team_leader" not in cols:
        to_add.append(("team_leader", "INTEGER"))
    if "phone" not in cols:
        to_add.append(("phone", "TEXT"))
    if "notes" not in cols:
        to_add.append(("notes", "TEXT"))
    if "status" not in cols:
        to_add.append(("status", "TEXT"))
    if "status_updated" not in cols:
        to_add.append(("status_updated", "TEXT"))
    if "current_task_id" not in cols:
        to_add.append(("current_task_id", "INTEGER"))
    # Geo / movement
    if "last_known_lat" not in cols:
        to_add.append(("last_known_lat", "REAL"))
    if "last_known_lon" not in cols:
        to_add.append(("last_known_lon", "REAL"))
    if "route" not in cols:
        to_add.append(("route", "TEXT"))
    # JSON blobs for lists
    if "members_json" not in cols:
        to_add.append(("members_json", "TEXT"))
    if "vehicles_json" not in cols:
        to_add.append(("vehicles_json", "TEXT"))
    if "equipment_json" not in cols:
        to_add.append(("equipment_json", "TEXT"))
    if "aircraft_json" not in cols:
        to_add.append(("aircraft_json", "TEXT"))
    # Comms
    if "comms_preset_id" not in cols:
        to_add.append(("comms_preset_id", "INTEGER"))
    if "radio_ids" not in cols:
        to_add.append(("radio_ids", "TEXT"))
    # Type
    if "team_type" not in cols:
        to_add.append(("team_type", "TEXT"))
    if "last_comm_ping" not in cols:
        to_add.append(("last_comm_ping", "TEXT"))

    for col, typ in to_add:
        try:
            con.execute(f"ALTER TABLE teams ADD COLUMN {col} {typ}")
        except Exception:
            pass
    try:
        con.commit()
    except Exception:
        pass


def get_team(team_id: int) -> Optional[Team]:
    """Load a team by id from the active incident DB."""
    with _incident_connect() as con:
        _ensure_team_columns(con)
        row = con.execute("SELECT * FROM teams WHERE id=?", (int(team_id),)).fetchone()
    if not row:
        return None
    return Team.from_db_row(row)


def save_team(team: Team) -> Team:
    """Insert or update a Team in the active incident DB.

    Returns the persisted Team (with id populated).
    """
    data = team.to_db_dict()
    now = datetime.utcnow().isoformat()
    data["status_updated"] = now
    with _incident_connect() as con:
        _ensure_team_columns(con)
        if team.team_id is None:
            # Insert
            cols = [k for k in data.keys() if k != "id"]
            vals = [data[k] for k in cols]
            placeholders = ",".join(["?"] * len(cols))
            sql = f"INSERT INTO teams ({','.join(cols)}) VALUES ({placeholders})"
            cur = con.execute(sql, tuple(vals))
            team_id = int(cur.lastrowid)
            con.commit()
            team.team_id = team_id
        else:
            # Update
            cols = [k for k in data.keys() if k != "id"]
            assignments = ",".join([f"{k}=?" for k in cols])
            vals = [data[k] for k in cols] + [team.team_id]
            sql = f"UPDATE teams SET {assignments} WHERE id=?"
            con.execute(sql, tuple(vals))
            con.commit()
    return team


def set_team_status(team_id: int, status_key: str) -> None:
    """Set team status via the shared repository (keeps timeline in sync)."""
    # Delegate to the existing operations repository, which also stamps task_teams
    from modules.operations.data.repository import set_team_status as _set
    _set(int(team_id), str(status_key))


def reset_team_comm_timer(team_id: int, when: datetime | None = None) -> None:
    """Update the team's last communication ping to ``when`` or now."""
    ts = (when or datetime.utcnow()).isoformat()
    with _incident_connect() as con:
        _ensure_team_columns(con)
        con.execute(
            "UPDATE teams SET last_comm_ping=? WHERE id=?",
            (str(ts), int(team_id)),
        )
        con.commit()


def find_team_ids_by_label(label: str) -> list[int]:
    """Return team ids matching a name or callsign (case-insensitive)."""
    if not label:
        return []
    term = str(label).strip().lower()
    with _incident_connect() as con:
        _ensure_team_columns(con)
        rows = con.execute(
            "SELECT id FROM teams WHERE lower(name)=? OR lower(callsign)=?",
            (term, term),
        ).fetchall()
    return [int(r["id"]) for r in rows]

