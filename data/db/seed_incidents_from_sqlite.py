"""
One-time seed script: reads from each incident's SQLite incident.db and
seeds the corresponding sarapp_incident_<id> MongoDB database.

Rules:
    - Never modifies any SQLite file.
    - Skips documents already in MongoDB (idempotent).
    - Skips demo-incident and unassigned (no real data).
    - work_assignments map to strategies (NOT tasks).
    - task narrative entries embedded inside task documents.
    - Narrative timestamps reconstructed from incident created_at date + time field.
    - check_in_out seeded where checkins table exists.

Usage:
    python data/db/seed_incidents_from_sqlite.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from sarapp_db.mongo.database_manager import DatabaseManager
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.indexes import create_incident_indexes

_INCIDENTS_DIR = _repo_root / "data" / "incidents"

# Incidents to seed — maps incident_number to folder name
INCIDENTS = {
    "2025-FAIR":  "2025-FAIR_County_Fair",
    "25-1-7985":  "25-1-7985_Operation_Thunderbolt",
    "25-T-5874":  "25-T-5874_Operation_Wolverine",
    "26-T-4301":  "26-T-4301_Operation_Wolverine_2026",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def _seed_one(col, docs: list[dict], id_field: str) -> tuple[int, int]:
    inserted = skipped = 0
    for doc in docs:
        if col.find_one({id_field: doc[id_field]}) is not None:
            skipped += 1
        else:
            col.insert_one(doc)
            inserted += 1
    return inserted, skipped


def _report(name: str, inserted: int, skipped: int) -> None:
    print(f"    {name:<32} {inserted:>4} inserted  {skipped:>4} skipped")


def _discover_incidents() -> list[tuple[str, str]]:
    """Discover all real incident folders on disk."""
    skipped_ids = {"demo-incident", "unassigned"}
    incidents: list[tuple[str, str]] = []
    for folder_path in sorted(_INCIDENTS_DIR.iterdir()):
        if not folder_path.is_dir():
            continue

        json_path = folder_path / "incident.json"
        db_path = folder_path / "incident.db"
        if not json_path.exists() or not db_path.exists():
            continue

        try:
            with open(json_path, encoding="utf-8") as f:
                incident_json = json.load(f)
        except Exception:
            continue

        incident_number = str(incident_json.get("incident_number") or "").strip()
        if not incident_number or incident_number in skipped_ids:
            continue

        incidents.append((incident_number, folder_path.name))

    return incidents


def _parse_narrative_timestamp(time_str: str, base_date: str) -> str:
    """
    Reconstruct a full ISO timestamp from a bare time string (e.g. '2311')
    using the incident created_at date as the base date.
    """
    try:
        # Normalise time string — could be '2311', '23:11', '9:05', etc.
        t = time_str.strip().replace(":", "")
        if len(t) <= 2:
            t = t.zfill(2) + "00"
        elif len(t) == 3:
            t = "0" + t
        hour = int(t[:2])
        minute = int(t[2:4])
        # Extract date portion from base_date
        date_part = base_date[:10]  # "YYYY-MM-DD"
        dt = datetime.strptime(f"{date_part} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return base_date  # fall back to incident date


# ---------------------------------------------------------------------------
# Per-collection seeders
# ---------------------------------------------------------------------------

def seed_incident_profile(inc_json: dict, cur: sqlite3.Cursor, incident_db) -> None:
    inc_number = inc_json["incident_number"]
    meta = {}
    if _table_exists(cur, "incident_meta"):
        cur.execute("SELECT * FROM incident_meta LIMIT 1")
        row = cur.fetchone()
        if row:
            meta = dict(row)

    doc = {
        "_id": _new_id(),
        "incident_id": inc_number,
        "name": inc_json.get("name", ""),
        "incident_number": inc_number,
        "incident_type": inc_json.get("type", ""),
        "status": inc_json.get("status", "active").lower(),
        "icp_address": meta.get("icp_address"),
        "latitude": meta.get("icp_lat"),
        "longitude": meta.get("icp_lon"),
        "created_at": inc_json.get("created_at", ""),
        "updated_at": inc_json.get("updated_at", ""),
        "deleted": False,
    }
    col = incident_db[IncidentCollections.INCIDENT_PROFILE]
    i, s = _seed_one(col, [doc], "incident_id")
    _report("incident_profile", i, s)


def seed_operational_periods(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "operationalperiods"):
        return
    cur.execute("SELECT * FROM operationalperiods")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "op_id": f"{inc_number}-OP-{r['id']}",
        "incident_id": inc_number,
        "op_number": r.get("op_number") or r.get("number"),
        "name": r.get("name"),
        "start_time": r.get("start_time"),
        "end_time": r.get("end_time"),
        "briefing_time": r.get("briefing_time"),
        "debrief_time": r.get("debrief_time"),
        "status": r.get("status", "planned"),
        "objectives": r.get("objectives"),
        "weather_summary": r.get("weather_summary"),
        "safety_message": r.get("safety_message"),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.OPERATIONAL_PERIODS]
    i, s = _seed_one(col, docs, "op_id")
    _report("operational_periods", i, s)


def seed_objectives(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "incident_objectives"):
        return
    cur.execute("SELECT * FROM incident_objectives")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "objective_id": f"{inc_number}-OBJ-{r['id']}",
        "incident_id": inc_number,
        "description": r.get("description") or r.get("text"),
        "status": r.get("status", "pending"),
        "priority": r.get("priority", "normal"),
        "assigned_section": r.get("assigned_section"),
        "owner_section": r.get("owner_section"),
        "op_period_id": f"{inc_number}-OP-{r['op_period_id']}" if r.get("op_period_id") else None,
        "due_time": r.get("due_time"),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.INCIDENT_OBJECTIVES]
    i, s = _seed_one(col, docs, "objective_id")
    _report("incident_objectives", i, s)


def seed_strategies(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Seeds from objective_strategies and/or work_assignments — both map to strategies."""
    docs = []

    if _table_exists(cur, "objective_strategies"):
        cur.execute("SELECT * FROM objective_strategies")
        for r in (dict(row) for row in cur.fetchall()):
            docs.append({
                "_id": _new_id(),
                "strategy_id": f"{inc_number}-OSTRAT-{r['id']}",
                "incident_id": inc_number,
                "source": "objective_strategy",
                "objective_id": f"{inc_number}-OBJ-{r['objective_id']}" if r.get("objective_id") else None,
                "text": r.get("text"),
                "owner": r.get("owner"),
                "status": r.get("status", "planned"),
                "progress_pct": r.get("progress_pct"),
                "updated_at": r.get("updated_at", ""),
                "deleted": False,
            })

    if _table_exists(cur, "work_assignments"):
        cur.execute("SELECT * FROM work_assignments")
        for r in (dict(row) for row in cur.fetchall()):
            docs.append({
                "_id": _new_id(),
                "strategy_id": f"{inc_number}-WA-{r['id']}",
                "incident_id": inc_number,
                "source": "work_assignment",
                "assignment_number": r.get("assignment_number"),
                "name": r.get("assignment_name"),
                "objective_id": f"{inc_number}-OBJ-{r['objective_id']}" if r.get("objective_id") else None,
                "op_period_id": f"{inc_number}-OP-{r['operational_period_id']}" if r.get("operational_period_id") else None,
                "branch": r.get("branch"),
                "division_group": r.get("division_group"),
                "location": r.get("location"),
                "assignment_kind": r.get("assignment_kind"),
                "priority": r.get("priority", "normal"),
                "planning_status": r.get("planning_status"),
                "safety_status": r.get("safety_status"),
                "description": r.get("description"),
                "tactics_summary": r.get("tactics_summary"),
                "special_instructions": r.get("special_instructions"),
                "is_archived": bool(r.get("is_archived", 0)),
                "notes": r.get("notes"),
                "created_at": r.get("created_at", ""),
                "updated_at": r.get("updated_at", ""),
                "deleted": False,
            })

    if not docs:
        return
    col = incident_db[IncidentCollections.STRATEGIES]
    i, s = _seed_one(col, docs, "strategy_id")
    _report("strategies", i, s)


def seed_teams(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "teams"):
        return
    cur.execute("SELECT * FROM teams")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return

    def _parse_json_list(val) -> list:
        if not val:
            return []
        try:
            result = json.loads(val)
            return result if isinstance(result, list) else []
        except Exception:
            return []

    docs = [{
        "_id": _new_id(),
        "team_id": f"{inc_number}-TEAM-{r['id']}",
        "incident_id": inc_number,
        "name": r.get("name", f"Team {r['id']}"),
        "callsign": r.get("callsign"),
        "team_type": r.get("team_type"),
        "role": r.get("role"),
        "status": r.get("status", "available"),
        "leader_personnel_id": str(r["team_leader"]) if r.get("team_leader") else None,
        "leader_phone": r.get("leader_phone"),
        "phone": r.get("phone"),
        "member_personnel_ids": [str(x) for x in _parse_json_list(r.get("members_json") or r.get("personnel"))],
        "vehicle_ids": [str(x) for x in _parse_json_list(r.get("vehicles_json") or r.get("vehicles"))],
        "aircraft_ids": [str(x) for x in _parse_json_list(r.get("aircraft_json"))],
        "current_task_id": f"{inc_number}-TASK-{r['current_task_id']}" if r.get("current_task_id") else None,
        "last_known_lat": r.get("last_known_lat"),
        "last_known_lon": r.get("last_known_lon"),
        "notes": r.get("notes"),
        "emergency_flag": bool(r.get("emergency_flag", 0)),
        "last_checkin_at": r.get("last_checkin_at"),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.TEAMS]
    i, s = _seed_one(col, docs, "team_id")
    _report("teams", i, s)


def seed_tasks(cur: sqlite3.Cursor, incident_db, inc_number: str, base_date: str) -> None:
    if not _table_exists(cur, "tasks"):
        return
    cur.execute("SELECT * FROM tasks")
    tasks = [dict(r) for r in cur.fetchall()]
    if not tasks:
        return

    # Build lookup maps for assignments
    team_assignments: dict[int, list] = {}
    if _table_exists(cur, "task_teams"):
        cur.execute("SELECT * FROM task_teams")
        for r in (dict(row) for row in cur.fetchall()):
            team_assignments.setdefault(r["task_id"], []).append({
                "team_id": f"{inc_number}-TEAM-{r['teamid']}",
                "sortie_id": r.get("sortie_id"),
                "is_primary": bool(r.get("is_primary", 0)),
                "time_assigned": r.get("time_assigned"),
                "time_briefed": r.get("time_briefed"),
                "time_enroute": r.get("time_enroute"),
                "time_arrived": r.get("time_arrived"),
                "time_complete": r.get("time_complete"),
                "time_cleared": r.get("time_cleared"),
            })

    personnel_assignments: dict[int, list] = {}
    if _table_exists(cur, "task_personnel"):
        cur.execute("SELECT * FROM task_personnel")
        for r in (dict(row) for row in cur.fetchall()):
            personnel_assignments.setdefault(r["task_id"], []).append({
                "personnel_id": str(r["personnel_id"]),
                "role": r.get("role"),
                "organization": r.get("organization"),
                "time_assigned": r.get("time_assigned"),
            })

    vehicle_assignments: dict[int, list] = {}
    if _table_exists(cur, "task_vehicles"):
        cur.execute("SELECT * FROM task_vehicles")
        for r in (dict(row) for row in cur.fetchall()):
            vehicle_assignments.setdefault(r["task_id"], []).append({
                "vehicle_id": str(r["vehicle_id"]),
            })

    # Narrative entries — keyed by taskid (field name varies by incident)
    narrative_entries: dict[int, list] = {}
    narrative_table = None
    if _table_exists(cur, "task_narratives"):
        narrative_table = "task_narratives"
    elif _table_exists(cur, "narrative_entries"):
        narrative_table = "narrative_entries"

    if narrative_table:
        cur.execute(f"SELECT * FROM {narrative_table}")
        for r in (dict(row) for row in cur.fetchall()):
            task_key = r.get("task_id") or r.get("taskid")
            if task_key is None:
                continue
            narrative_entries.setdefault(int(task_key), []).append({
                "entry_id": _new_id(),
                "timestamp": _parse_narrative_timestamp(str(r.get("timestamp", "")), base_date),
                "narrative": r.get("narrative", ""),
                "entered_by": str(r.get("entered_by", "")),
                "critical": bool(r.get("critical", 0)),
            })

    docs = []
    for r in tasks:
        task_sqlite_id = r["id"]
        docs.append({
            "_id": _new_id(),
            "task_id": f"{inc_number}-TASK-{task_sqlite_id}",
            "incident_id": inc_number,
            "task_number": r.get("task_id", str(task_sqlite_id)),  # e.g. "T-001"
            "title": r.get("title", ""),
            "location": r.get("location"),
            "priority": str(r.get("priority", "normal")),
            "status": r.get("status", "pending"),
            "task_type": r.get("task_type"),
            "category": r.get("category"),
            "assignment": r.get("assignment"),
            "radio_primary": r.get("radio_primary"),
            "radio_alternate": r.get("radio_alternate"),
            "radio_emergency": r.get("radio_emergency"),
            "created_at": r.get("created_at", base_date),
            "updated_at": r.get("last_update") or r.get("created_at") or base_date,
            "due_time": r.get("due_time"),
            # Embedded assignments
            "assigned_teams": team_assignments.get(task_sqlite_id, []),
            "assigned_personnel": personnel_assignments.get(task_sqlite_id, []),
            "assigned_vehicles": vehicle_assignments.get(task_sqlite_id, []),
            # Embedded narrative
            "narrative": narrative_entries.get(task_sqlite_id, []),
            "deleted": False,
        })

    col = incident_db[IncidentCollections.TASKS]
    i, s = _seed_one(col, docs, "task_id")
    _report("tasks", i, s)


def seed_check_in_out(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "checkins"):
        return
    cur.execute("SELECT * FROM checkins")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "checkin_id": f"{inc_number}-CI-{r['id']}",
        "incident_id": inc_number,
        "resource_type": "personnel",
        "resource_id": str(r["person_id"]),
        "status": r.get("ci_status", "checked_in"),
        "personnel_status": r.get("personnel_status"),
        "checked_in_at": r.get("arrival_time") or r.get("created_at"),
        "checked_out_at": None,
        "location": r.get("location"),
        "location_other": r.get("location_other"),
        "shift_start": r.get("shift_start"),
        "shift_end": r.get("shift_end"),
        "team_id": f"{inc_number}-TEAM-{r['team_id']}" if r.get("team_id") else None,
        "role_on_team": r.get("role_on_team"),
        "incident_callsign": r.get("incident_callsign"),
        "incident_phone": r.get("incident_phone"),
        "operational_period_id": f"{inc_number}-OP-{r['operational_period']}" if r.get("operational_period") else None,
        "notes": r.get("notes"),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.CHECK_IN_OUT]
    i, s = _seed_one(col, docs, "checkin_id")
    _report("check_in_out", i, s)


def seed_comms_log(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "comms_log"):
        return
    cur.execute("SELECT COUNT(*) FROM comms_log")
    if cur.fetchone()[0] == 0:
        return
    cur.execute("SELECT * FROM comms_log")
    rows = [dict(r) for r in cur.fetchall()]
    docs = [{
        "_id": _new_id(),
        "comms_id": f"{inc_number}-COMMS-{r['id']}",
        "incident_id": inc_number,
        "ts_utc": r.get("ts_utc"),
        "ts_local": r.get("ts_local"),
        "priority": r.get("priority"),
        "direction": r.get("direction"),
        "from_unit": r.get("from_unit"),
        "to_unit": r.get("to_unit"),
        "message": r.get("message"),
        "action_taken": r.get("action_taken"),
        "follow_up_required": bool(r.get("follow_up_required", 0)),
        "disposition": r.get("disposition"),
        "frequency": r.get("frequency"),
        "band": r.get("band"),
        "mode": r.get("mode"),
        "resource_id": r.get("resource_id"),
        "resource_label": r.get("resource_label"),
        "operator_user_id": r.get("operator_user_id"),
        "operator_display_name": r.get("operator_display_name"),
        "team_id": f"{inc_number}-TEAM-{r['team_id']}" if r.get("team_id") else None,
        "task_id": f"{inc_number}-TASK-{r['task_id']}" if r.get("task_id") else None,
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.COMMUNICATIONS_LOG]
    i, s = _seed_one(col, docs, "comms_id")
    _report("communications_log", i, s)


def seed_incident_organization(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Merges ics203_positions, ics203_units, ics203_assignments, ics203_agency_reps
    into one document per org version (one version per incident if no versioning table)."""
    if not _table_exists(cur, "ics203_positions"):
        return
    cur.execute("SELECT COUNT(*) FROM ics203_positions")
    if cur.fetchone()[0] == 0:
        return

    # Positions
    cur.execute("SELECT * FROM ics203_positions ORDER BY sort_order")
    positions = [dict(r) for r in cur.fetchall()]

    # Units
    units = []
    if _table_exists(cur, "ics203_units"):
        cur.execute("SELECT * FROM ics203_units ORDER BY sort_order")
        units = [dict(r) for r in cur.fetchall()]

    # Assignments keyed by position_id
    assignments_by_position: dict[int, list] = {}
    if _table_exists(cur, "ics203_assignments"):
        cur.execute("SELECT * FROM ics203_assignments")
        for r in (dict(row) for row in cur.fetchall()):
            assignments_by_position.setdefault(r["position_id"], []).append({
                "assignment_id": str(r["id"]),
                "person_id": str(r["person_id"]) if r.get("person_id") else None,
                "display_name": r.get("display_name"),
                "callsign": r.get("callsign"),
                "phone": r.get("phone"),
                "agency": r.get("agency"),
                "is_deputy": bool(r.get("is_deputy", 0)),
                "is_trainee": bool(r.get("is_trainee", 0)),
                "start_utc": r.get("start_utc"),
                "end_utc": r.get("end_utc"),
                "notes": r.get("notes"),
            })

    # Agency reps
    agency_reps = []
    if _table_exists(cur, "ics203_agency_reps"):
        cur.execute("SELECT * FROM ics203_agency_reps")
        agency_reps = [dict(r) for r in cur.fetchall()]

    # Version — check for versions table, otherwise treat as single version
    versions = [{"id": 1, "op_period_id": None, "created_at": "", "notes": ""}]
    if _table_exists(cur, "ics203_versions"):
        cur.execute("SELECT * FROM ics203_versions")
        rows = cur.fetchall()
        if rows:
            versions = [dict(r) for r in rows]

    docs = []
    for v in versions:
        ver_id = v.get("id", 1)
        docs.append({
            "_id": _new_id(),
            "version_id": f"{inc_number}-ORG-{ver_id}",
            "incident_id": inc_number,
            "op_period_id": f"{inc_number}-OP-{v['op_period_id']}" if v.get("op_period_id") else None,
            "created_at": v.get("created_at", ""),
            "notes": v.get("notes"),
            "units": [{
                "unit_id": str(u["id"]),
                "unit_type": u.get("unit_type"),
                "name": u.get("name"),
                "parent_unit_id": str(u["parent_unit_id"]) if u.get("parent_unit_id") else None,
                "sort_order": u.get("sort_order"),
            } for u in units],
            "positions": [{
                "position_id": str(p["id"]),
                "title": p.get("title"),
                "unit_id": str(p["unit_id"]) if p.get("unit_id") else None,
                "sort_order": p.get("sort_order"),
                "assignments": assignments_by_position.get(p["id"], []),
            } for p in positions],
            "agency_reps": [{
                "agency_rep_id": str(r.get("id", "")),
                "agency": r.get("agency"),
                "representative": r.get("representative"),
                "phone": r.get("phone"),
                "notes": r.get("notes"),
            } for r in agency_reps],
            "deleted": False,
        })

    col = incident_db[IncidentCollections.INCIDENT_ORGANIZATION]
    i, s = _seed_one(col, docs, "version_id")
    _report("incident_organization", i, s)


def seed_unit_logs(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Seeds ics214_streams with entries embedded per stream."""
    if not _table_exists(cur, "ics214_streams"):
        return
    cur.execute("SELECT COUNT(*) FROM ics214_streams")
    if cur.fetchone()[0] == 0:
        return

    # Entries keyed by stream_id
    entries_by_stream: dict[str, list] = {}
    if _table_exists(cur, "ics214_entries"):
        cur.execute("SELECT * FROM ics214_entries ORDER BY timestamp_utc")
        for r in (dict(row) for row in cur.fetchall()):
            entries_by_stream.setdefault(r["stream_id"], []).append({
                "entry_id": str(r["id"]),
                "timestamp_utc": r.get("timestamp_utc", ""),
                "text": r.get("text", ""),
                "source": r.get("source"),
                "actor_user_id": str(r["actor_user_id"]) if r.get("actor_user_id") else None,
                "autogenerated": bool(r.get("autogenerated", 0)),
                "critical_flag": bool(r.get("critical_flag", 0)),
                "tags": json.loads(r["tags"]) if r.get("tags") else [],
            })

    cur.execute("SELECT * FROM ics214_streams")
    rows = [dict(r) for r in cur.fetchall()]

    # Parse section field — may be a JSON string or a plain string
    def _parse_section(val):
        if not val:
            return None
        try:
            return json.loads(val)
        except Exception:
            return val

    docs = [{
        "_id": _new_id(),
        "stream_id": r["id"],
        "incident_id": inc_number,
        "name": r.get("name", ""),
        "op_number": r.get("op_number"),
        "kind": r.get("kind"),
        "section": _parse_section(r.get("section")),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "entries": entries_by_stream.get(r["id"], []),
        "deleted": False,
    } for r in rows]

    col = incident_db[IncidentCollections.UNIT_LOGS]
    i, s = _seed_one(col, docs, "stream_id")
    _report("unit_logs", i, s)


def seed_meetings(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "meetings"):
        return
    cur.execute("SELECT COUNT(*) FROM meetings")
    if cur.fetchone()[0] == 0:
        return

    # Attendees keyed by meeting_id
    attendees_by_meeting: dict[int, list] = {}
    if _table_exists(cur, "meeting_attendees"):
        cur.execute("SELECT * FROM meeting_attendees")
        for r in (dict(row) for row in cur.fetchall()):
            attendees_by_meeting.setdefault(r["meeting_id"], []).append({
                "display_name": r.get("display_name"),
                "attendee_type": r.get("attendee_type"),
                "role": r.get("role"),
                "requirement_status": r.get("requirement_status"),
                "attendance_status": r.get("attendance_status"),
            })

    # Checklist items keyed by meeting_id
    checklist_by_meeting: dict[int, list] = {}
    if _table_exists(cur, "meeting_checklist_items"):
        cur.execute("SELECT * FROM meeting_checklist_items ORDER BY sort_order")
        for r in (dict(row) for row in cur.fetchall()):
            checklist_by_meeting.setdefault(r["meeting_id"], []).append({
                "group_name": r.get("group_name"),
                "text": r.get("text", ""),
                "assigned_to": r.get("assigned_to"),
                "is_complete": bool(r.get("is_complete", 0)),
                "is_not_applicable": bool(r.get("is_not_applicable", 0)),
                "sort_order": r.get("sort_order"),
            })

    cur.execute("SELECT * FROM meetings")
    rows = [dict(r) for r in cur.fetchall()]

    docs = [{
        "_id": _new_id(),
        "meeting_id": f"{inc_number}-MTG-{r['id']}",
        "incident_id": inc_number,
        "op_period_id": f"{inc_number}-OP-{r['operational_period_id']}" if r.get("operational_period_id") else None,
        "template_id": r.get("template_id"),
        "title": r.get("title", ""),
        "meeting_date": r.get("meeting_date"),
        "start_time": r.get("start_time"),
        "end_time": r.get("end_time"),
        "location": r.get("location"),
        "virtual_link": r.get("virtual_link"),
        "owner": r.get("owner"),
        "status": r.get("status", "scheduled"),
        "show_on_ics230": bool(r.get("show_on_ics230", 0)),
        "freeform_notes": r.get("freeform_notes"),
        "notes_log_routing_status": r.get("notes_log_routing_status"),
        "attendees": attendees_by_meeting.get(r["id"], []),
        "checklist_items": checklist_by_meeting.get(r["id"], []),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "deleted": False,
    } for r in rows]

    col = incident_db[IncidentCollections.MEETINGS]
    i, s = _seed_one(col, docs, "meeting_id")
    _report("meetings", i, s)


def seed_task_debriefs(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Embeds debrief data into existing task documents."""
    # Handle both old schema (debriefs table) and new schema (task_debriefs table)
    debrief_table = None
    if _table_exists(cur, "task_debriefs"):
        debrief_table = "task_debriefs"
    elif _table_exists(cur, "debriefs"):
        debrief_table = "debriefs"
    if not debrief_table:
        return

    cur.execute(f"SELECT * FROM {debrief_table}")
    debrief_rows = [dict(r) for r in cur.fetchall()]
    if not debrief_rows:
        return

    # Build sub-form data keyed by debrief id
    subforms: dict[int, dict] = {}
    subform_tables = [
        ("debrief_ground_sar", "ground_sar"),
        ("debrief_area_search", "area_search"),
        ("debrief_tracking", "tracking"),
        ("debrief_hasty_search", "hasty_search"),
        ("debrief_air_general", "air_general"),
        ("debrief_air_sar", "air_sar"),
    ]
    for table, key in subform_tables:
        if _table_exists(cur, table):
            cur.execute(f"SELECT * FROM {table}")
            for r in (dict(row) for row in cur.fetchall()):
                did = r.get("debrief_id")
                if did is not None:
                    subforms.setdefault(did, {})[key] = {
                        k: v for k, v in r.items() if k not in ("id", "debrief_id") and v is not None
                    }

    tasks_col = incident_db[IncidentCollections.TASKS]
    updated = skipped = 0

    for r in debrief_rows:
        task_sqlite_id = r.get("task_id")
        if task_sqlite_id is None:
            continue
        task_id = f"{inc_number}-TASK-{task_sqlite_id}"
        task_doc = tasks_col.find_one({"task_id": task_id})
        if task_doc is None:
            skipped += 1
            continue
        if task_doc.get("debrief"):
            skipped += 1
            continue

        # new schema has types as JSON list; old schema has debrief_type string
        types_raw = r.get("types") or r.get("debrief_type")
        try:
            types = json.loads(types_raw) if isinstance(types_raw, str) and types_raw.startswith("[") else ([types_raw] if types_raw else [])
        except Exception:
            types = [types_raw] if types_raw else []

        debrief = {
            "debrief_id": str(r["id"]),
            "sortie_number": r.get("sortie_number"),
            "debriefer_id": str(r.get("debriefer_id") or r.get("debriefer") or ""),
            "types": types,
            "status": r.get("status", "draft"),
            "flagged_for_review": bool(r.get("flagged_for_review", 0)),
            "submitted_by": str(r["submitted_by"]) if r.get("submitted_by") else None,
            "submitted_at": r.get("submitted_at"),
            "reviewed_by": str(r["reviewed_by"]) if r.get("reviewed_by") else None,
            "reviewed_at": r.get("reviewed_at"),
            "created_at": r.get("created_at", ""),
            "updated_at": r.get("updated_at", ""),
            "forms": subforms.get(r["id"], {}),
        }

        tasks_col.update_one({"task_id": task_id}, {"$set": {"debrief": debrief}})
        updated += 1

    _report("tasks (debrief embed)", updated, skipped)


def seed_incident_channels(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "incident_channels"):
        return
    cur.execute("SELECT * FROM incident_channels")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "channel_id": f"{inc_number}-CH-{r['id']}",
        "incident_id": inc_number,
        "master_id": str(r["master_id"]) if r.get("master_id") else None,
        "channel": r.get("channel", ""),
        "function": r.get("function"),
        "band": r.get("band"),
        "system": r.get("system"),
        "mode": r.get("mode"),
        "rx_freq": r.get("rx_freq"),
        "tx_freq": r.get("tx_freq"),
        "rx_tone": r.get("rx_tone"),
        "tx_tone": r.get("tx_tone"),
        "squelch_type": r.get("squelch_type"),
        "squelch_value": r.get("squelch_value"),
        "repeater": bool(r.get("repeater", 0)),
        "offset": r.get("offset"),
        "encryption": r.get("encryption"),
        "assignment_division": r.get("assignment_division"),
        "assignment_team": r.get("assignment_team"),
        "priority": r.get("priority", "Normal"),
        "include_on_205": bool(r.get("include_on_205", 0)),
        "remarks": r.get("remarks"),
        "sort_index": r.get("sort_index"),
        "line_a": bool(r.get("line_a", 0)),
        "line_c": bool(r.get("line_c", 0)),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.INCIDENT_CHANNELS]
    i, s = _seed_one(col, docs, "channel_id")
    _report("incident_channels", i, s)


def seed_resources(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Seeds logistics_resource_status_items — one document per resource regardless of type."""
    if not _table_exists(cur, "logistics_resource_status_items"):
        return
    cur.execute("SELECT * FROM logistics_resource_status_items")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "resource_id": f"{inc_number}-RES-{r['id']}",
        "incident_id": inc_number,
        "source_id": str(r["resource_id"]),
        "name": r.get("resource_name", ""),
        "resource_type": r.get("resource_type", ""),
        "status": r.get("status", ""),
        "eta_utc": r.get("eta_utc"),
        "assigned_to": str(r["assigned_to"]) if r.get("assigned_to") else None,
        "assignment_reference": r.get("assignment_reference"),
        "location": r.get("location"),
        "checked_in_time": r.get("checked_in_time"),
        "last_updated": r.get("last_updated", ""),
        "notes": r.get("notes"),
        "source_entity_type": r.get("source_entity_type"),
        "source_record_id": str(r["source_record_id"]) if r.get("source_record_id") else None,
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.RESOURCES]
    i, s = _seed_one(col, docs, "resource_id")
    _report("resources", i, s)


def seed_task_comms(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Folds task_comms into the communications_log collection with a task_id reference."""
    if not _table_exists(cur, "task_comms"):
        return
    cur.execute("SELECT * FROM task_comms WHERE incident_channel_id IS NOT NULL OR function IS NOT NULL OR remarks IS NOT NULL")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "comms_id": f"{inc_number}-TCOMMS-{r['id']}",
        "incident_id": inc_number,
        "source": "task_comms",
        "task_id": f"{inc_number}-TASK-{r['task_id']}" if r.get("task_id") else None,
        "channel_id": f"{inc_number}-CH-{r['incident_channel_id']}" if r.get("incident_channel_id") else None,
        "function": r.get("function"),
        "remarks": r.get("remarks"),
        "deleted": False,
    } for r in rows]
    if not docs:
        return
    col = incident_db[IncidentCollections.COMMUNICATIONS_LOG]
    i, s = _seed_one(col, docs, "comms_id")
    _report("communications_log (task_comms)", i, s)


def seed_strategy_details(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Embeds work_assignment_tasks/resources/outputs/log into existing strategy documents."""
    if not _table_exists(cur, "work_assignments"):
        return

    strategies_col = incident_db[IncidentCollections.STRATEGIES]
    cur.execute("SELECT id FROM work_assignments")
    wa_ids = [r[0] for r in cur.fetchall()]
    if not wa_ids:
        return

    updated = skipped = 0
    for wa_id in wa_ids:
        strategy_id = f"{inc_number}-WA-{wa_id}"
        doc = strategies_col.find_one({"strategy_id": strategy_id})
        if doc is None:
            skipped += 1
            continue
        if doc.get("linked_tasks") is not None:
            skipped += 1
            continue

        linked_tasks = []
        if _table_exists(cur, "work_assignment_tasks"):
            cur.execute("SELECT * FROM work_assignment_tasks WHERE work_assignment_id=?", (wa_id,))
            for r in (dict(row) for row in cur.fetchall()):
                linked_tasks.append({
                    "task_id": f"{inc_number}-TASK-{r['task_id']}",
                    "link_type": r.get("link_type"),
                    "notes": r.get("notes"),
                    "created_at": r.get("created_at", ""),
                })

        resources_needed = []
        if _table_exists(cur, "work_assignment_resources"):
            cur.execute("SELECT * FROM work_assignment_resources WHERE work_assignment_id=?", (wa_id,))
            for r in (dict(row) for row in cur.fetchall()):
                resources_needed.append({
                    "resource_type_id": str(r["resource_type_id"]) if r.get("resource_type_id") else None,
                    "resource_type_text": r.get("resource_type_text"),
                    "capability_text": r.get("capability_text"),
                    "quantity_required": r.get("quantity_required"),
                    "quantity_assigned": r.get("quantity_assigned"),
                    "quantity_available": r.get("quantity_available"),
                    "quantity_gap": r.get("quantity_gap"),
                    "unit": r.get("unit"),
                    "priority": r.get("priority"),
                    "notes": r.get("notes"),
                })

        outputs = []
        if _table_exists(cur, "work_assignment_outputs"):
            cur.execute("SELECT * FROM work_assignment_outputs WHERE work_assignment_id=?", (wa_id,))
            for r in (dict(row) for row in cur.fetchall()):
                outputs.append({
                    "output_type": r.get("output_type"),
                    "status": r.get("status"),
                    "generated_at": r.get("generated_at"),
                    "notes": r.get("notes"),
                })

        log_entries = []
        if _table_exists(cur, "work_assignment_log"):
            cur.execute("SELECT * FROM work_assignment_log WHERE work_assignment_id=? ORDER BY timestamp", (wa_id,))
            for r in (dict(row) for row in cur.fetchall()):
                log_entries.append({
                    "timestamp": r.get("timestamp", ""),
                    "entered_by": str(r["entered_by"]) if r.get("entered_by") else None,
                    "entry_type": r.get("entry_type"),
                    "entry_text": r.get("entry_text", ""),
                    "critical": bool(r.get("critical", 0)),
                })

        strategies_col.update_one(
            {"strategy_id": strategy_id},
            {"$set": {
                "linked_tasks": linked_tasks,
                "resources_needed": resources_needed,
                "outputs": outputs,
                "log": log_entries,
            }}
        )
        updated += 1

    _report("strategies (detail embed)", updated, skipped)


def seed_task_assignments(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Embeds assignment_ground and assignment_air into existing task documents."""
    tasks_col = incident_db[IncidentCollections.TASKS]
    updated = skipped = 0

    ground_by_task: dict[int, dict] = {}
    if _table_exists(cur, "assignment_ground"):
        cur.execute("SELECT * FROM assignment_ground")
        for r in (dict(row) for row in cur.fetchall()):
            ground_by_task[r["taskid"]] = {k: v for k, v in r.items() if k not in ("id", "taskid") and v is not None}

    air_by_task: dict[int, dict] = {}
    if _table_exists(cur, "assignment_air"):
        cur.execute("SELECT * FROM assignment_air")
        for r in (dict(row) for row in cur.fetchall()):
            air_by_task[r["taskid"]] = {k: v for k, v in r.items() if k not in ("id", "taskid") and v is not None}

    all_task_ids = set(ground_by_task.keys()) | set(air_by_task.keys())
    if not all_task_ids:
        return

    for task_sqlite_id in all_task_ids:
        task_id = f"{inc_number}-TASK-{task_sqlite_id}"
        doc = tasks_col.find_one({"task_id": task_id})
        if doc is None:
            skipped += 1
            continue
        if doc.get("assignment_ground") is not None or doc.get("assignment_air") is not None:
            skipped += 1
            continue
        update = {}
        if task_sqlite_id in ground_by_task:
            update["assignment_ground"] = ground_by_task[task_sqlite_id]
        if task_sqlite_id in air_by_task:
            update["assignment_air"] = air_by_task[task_sqlite_id]
        tasks_col.update_one({"task_id": task_id}, {"$set": update})
        updated += 1

    _report("tasks (assignment embed)", updated, skipped)


def seed_incident_journal(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    if not _table_exists(cur, "planning_logs"):
        return
    cur.execute("SELECT * FROM planning_logs")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "journal_id": f"{inc_number}-JNL-{r['id']}",
        "incident_id": inc_number,
        "text": r.get("text", ""),
        "timestamp": r.get("timestamp", ""),
        "entered_by": str(r["entered_by"]) if r.get("entered_by") else None,
        "deleted": False,
    } for r in rows]
    col = incident_db[IncidentCollections.INCIDENT_JOURNAL]
    i, s = _seed_one(col, docs, "journal_id")
    _report("incident_journal", i, s)


def seed_personnel(cur: sqlite3.Cursor, incident_db, inc_number: str) -> None:
    """Incident-local personnel roster (separate from master personnel)."""
    if not _table_exists(cur, "personnel"):
        return
    cur.execute("SELECT * FROM personnel")
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return
    docs = [{
        "_id": _new_id(),
        "roster_id": f"{inc_number}-PERS-{r['id']}",
        "incident_id": inc_number,
        "sqlite_id": str(r["id"]),
        "name": r.get("name", ""),
        "rank": r.get("rank"),
        "callsign": r.get("callsign"),
        "role": r.get("role"),
        "phone": r.get("phone") or r.get("contact"),
        "email": r.get("email"),
        "unit": r.get("unit"),
        "organization": r.get("organization"),
        "team_id": f"{inc_number}-TEAM-{r['team_id']}" if r.get("team_id") else None,
        "is_medic": bool(r.get("is_medic", 0)),
        "deleted": False,
    } for r in rows if r.get("name", "").strip()]
    if not docs:
        return
    col = incident_db["incident_personnel"]  # incident-scoped roster, separate from master
    i, s = _seed_one(col, docs, "roster_id")
    _report("incident_personnel", i, s)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 65)
    print("SARApp incident SQLite -> MongoDB seed")
    print("=" * 65)

    mgr = DatabaseManager()
    if not mgr.is_connected():
        print("ERROR: Cannot connect to MongoDB. Check SARAPP_MONGO_URI.")
        return 1

    overall_ok = True

    incidents = _discover_incidents()
    if not incidents:
        print("No incident SQLite databases found to seed.")
        return 0

    for inc_number, folder in incidents:
        folder_path = _INCIDENTS_DIR / folder
        json_path = folder_path / "incident.json"
        db_path = folder_path / "incident.db"

        print(f"\n--- {inc_number} ({folder}) ---")

        if not json_path.exists():
            print("  SKIP: incident.json not found")
            continue
        if not db_path.exists():
            print("  SKIP: incident.db not found")
            continue

        with open(json_path, encoding="utf-8") as f:
            inc_json = json.load(f)

        base_date = inc_json.get("created_at") or "2025-01-01 00:00:00"

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        try:
            incident_db = mgr.get_incident_db(inc_number)
            create_incident_indexes(incident_db)

            seed_incident_profile(inc_json, cur, incident_db)
            seed_operational_periods(cur, incident_db, inc_number)
            seed_objectives(cur, incident_db, inc_number)
            seed_strategies(cur, incident_db, inc_number)
            seed_teams(cur, incident_db, inc_number)
            seed_tasks(cur, incident_db, inc_number, base_date)
            seed_check_in_out(cur, incident_db, inc_number)
            seed_comms_log(cur, incident_db, inc_number)
            seed_incident_channels(cur, incident_db, inc_number)
            seed_resources(cur, incident_db, inc_number)
            seed_task_comms(cur, incident_db, inc_number)
            seed_strategy_details(cur, incident_db, inc_number)
            seed_task_assignments(cur, incident_db, inc_number)
            seed_incident_organization(cur, incident_db, inc_number)
            seed_unit_logs(cur, incident_db, inc_number)
            seed_meetings(cur, incident_db, inc_number)
            seed_task_debriefs(cur, incident_db, inc_number)
            seed_incident_journal(cur, incident_db, inc_number)
            seed_personnel(cur, incident_db, inc_number)

        except Exception as exc:
            print(f"  ERROR seeding {inc_number}: {exc}")
            overall_ok = False
        finally:
            conn.close()

    print()
    print("=" * 65)
    print("RESULT: Done." if overall_ok else "RESULT: Completed with errors — see above.")
    print("No SQLite files were modified.")
    print("=" * 65)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
