"""FastAPI router for the Operations module (tasks, teams, debriefs)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.client import get_db
from sarapp_db.mongo.collection_names import IncidentCollections

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _tasks(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.OPERATIONS_TASKS]


def _teams(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.OPERATIONS_TEAMS]


def _debriefs(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.OPERATIONS_TASK_DEBRIEFS]


def _personnel(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")["incident_personnel"]


def _resolve_leader(incident_id: str, team_doc: dict) -> tuple[str, str]:
    """Return (leader_name, leader_phone) resolved from personnel if needed."""
    leader_name = team_doc.get("leader_name") or ""
    leader_phone = team_doc.get("leader_phone") or team_doc.get("phone") or ""
    pid = team_doc.get("leader_personnel_id") or team_doc.get("team_leader")
    if pid and (not leader_name or not leader_phone):
        p = _personnel(incident_id).find_one({"sqlite_id": str(pid)})
        if p:
            if not leader_name:
                leader_name = p.get("name") or (
                    ((p.get("first_name") or "") + " " + (p.get("last_name") or "")).strip()
                )
            if not leader_phone:
                leader_phone = p.get("phone") or ""
    return leader_name, leader_phone


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _ensure_int_ids(col) -> int:
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    counter = max_doc["int_id"] if max_doc else 0
    for doc in col.find({"int_id": {"$exists": False}}):
        counter += 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": counter}})
    return counter


def _next_int_id(col) -> int:
    _ensure_int_ids(col)
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (max_doc["int_id"] if max_doc else 0) + 1


PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
PRIORITY_INT_MAP = {"low": 1, "medium": 2, "high": 3, "critical": 4}
STATUS_TO_DB = {
    "created": "Draft", "draft": "Draft", "planned": "Planned",
    "assigned": "Assigned", "in progress": "In Progress",
    "complete": "Completed", "completed": "Completed", "cancelled": "Cancelled",
}
STATUS_LABEL = {
    "completed": "complete", "complete": "complete", "draft": "created", "created": "created",
    "planned": "planned", "assigned": "assigned", "in progress": "in progress", "cancelled": "cancelled",
}

TS_STATUS_COLS = {
    "assigned": "time_assigned", "briefed": "time_briefed",
    "enroute": "time_enroute", "arrival": "time_arrived", "on scene": "time_arrived",
    "find": "time_discovery", "discovery": "time_discovery",
    "complete": "time_complete", "returning": "time_cleared", "rtb": "time_cleared",
}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks")
def list_tasks(incident_id: str) -> list[dict]:
    col = _tasks(incident_id)
    _ensure_int_ids(col)
    return [_strip(d) for d in col.find(sort=[("int_id", 1)])]


@router.post("/incidents/{incident_id}/operations/tasks", status_code=201)
def create_task(incident_id: str, body: dict[str, Any]) -> dict:
    col = _tasks(incident_id)
    int_id = _next_int_id(col)
    # Auto-generate task_id if not supplied
    task_id_str = body.get("task_id")
    if not task_id_str:
        task_id_str = f"T-{int_id:03d}"
    doc = {
        "int_id": int_id,
        "task_id": task_id_str,
        "title": body.get("title", "<New Task>"),
        "category": body.get("category"),
        "task_type": body.get("task_type"),
        "priority": body.get("priority", "Medium"),
        "status": body.get("status", "Draft"),
        "location": body.get("location"),
        "assignment": body.get("assignment"),
        "team_leader": body.get("team_leader"),
        "team_phone": body.get("team_phone"),
        "created_by": body.get("created_by", ""),
        "created_at": _now(),
        "due_time": body.get("due_time"),
        "task_teams": [],
        "personnel": [],
        "vehicles": [],
        "aircraft": [],
        "comms": [],
        "task_assignment": {},
    }
    col.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}")
def get_task(incident_id: str, task_id: int) -> dict:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    if not doc:
        raise HTTPException(404, f"Task {task_id} not found")
    return _strip(doc)


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}")
def update_task(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    col = _tasks(incident_id)
    body.pop("int_id", None)
    result = col.find_one_and_update(
        {"int_id": task_id},
        {"$set": body},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, f"Task {task_id} not found")
    return _strip(result)


@router.get("/incidents/{incident_id}/operations/task-rows")
def fetch_task_rows(incident_id: str) -> list[dict]:
    """Summary rows for the Task Status board."""
    col = _tasks(incident_id)
    _ensure_int_ids(col)
    teams_col = _teams(incident_id)
    _ensure_int_ids(teams_col)
    rows = []
    for doc in col.find(sort=[("int_id", 1)]):
        task_int_id = doc["int_id"]
        task_str_id = doc.get("task_id") or str(task_int_id)
        # Find teams currently assigned to this task — supports both seeded
        # string-keyed assigned_teams and new-style task_teams arrays.
        assigned = []
        for tt in (doc.get("assigned_teams") or doc.get("task_teams") or []):
            team_ref = tt.get("team_id")
            if team_ref is None:
                continue
            # Look up by string team_id (seeded) or int int_id (new-style)
            team = (teams_col.find_one({"team_id": team_ref})
                    if isinstance(team_ref, str)
                    else teams_col.find_one({"int_id": team_ref}))
            if team:
                # Only include if team is still assigned to this task
                cur = team.get("current_task_id")
                if cur == task_str_id or cur == task_int_id:
                    assigned.append(team.get("name") or tt.get("sortie_id") or f"Team {team_ref}")
        priority = doc.get("priority", "")
        try:
            priority = PRIORITY_MAP.get(int(priority), str(priority))
        except (ValueError, TypeError):
            pass
        rows.append({
            "id": task_int_id,
            "number": doc.get("task_id") or f"T-{task_int_id}",
            "name": doc.get("title") or "",
            "assigned_teams": assigned,
            "status": STATUS_LABEL.get(str(doc.get("status") or "").lower(), str(doc.get("status") or "").lower()),
            "priority": priority,
            "location": doc.get("location") or "",
        })
    return rows


@router.get("/incidents/{incident_id}/operations/tasks-for-assignment")
def list_tasks_for_assignment(incident_id: str) -> list[dict]:
    col = _tasks(incident_id)
    rows = []
    for doc in col.find(sort=[("int_id", 1)]):
        priority = doc.get("priority", "")
        if isinstance(priority, int):
            priority = PRIORITY_MAP.get(priority, str(priority))
        rows.append({
            "id": doc["int_id"],
            "task_id": doc.get("task_id"),
            "title": doc.get("title"),
            "status": STATUS_LABEL.get(str(doc.get("status") or "").lower(), ""),
            "priority": priority,
            "location": doc.get("location") or "",
        })
    return rows


# ---------------------------------------------------------------------------
# Task status
# ---------------------------------------------------------------------------

@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/status")
def set_task_status(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    status_key = str(body.get("status_key", "")).lower()
    to_db = {
        "created": "Draft", "planned": "Planned", "assigned": "Assigned",
        "in progress": "In Progress", "complete": "Completed", "cancelled": "Cancelled",
    }.get(status_key, body.get("status_key", ""))
    col = _tasks(incident_id)
    result = col.find_one_and_update(
        {"int_id": task_id},
        {"$set": {"status": to_db}},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, f"Task {task_id} not found")
    return _strip(result)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/teams")
def list_teams(incident_id: str) -> list[dict]:
    col = _teams(incident_id)
    _ensure_int_ids(col)
    return [_strip(d) for d in col.find(sort=[("int_id", 1)])]


@router.post("/incidents/{incident_id}/operations/teams", status_code=201)
def create_team(incident_id: str, body: dict[str, Any]) -> dict:
    col = _teams(incident_id)
    int_id = _next_int_id(col)
    doc = {
        "int_id": int_id,
        "name": body.get("name"),
        "callsign": body.get("callsign"),
        "team_leader": body.get("team_leader"),
        "leader_phone": body.get("leader_phone"),
        "phone": body.get("phone"),
        "team_type": body.get("team_type"),
        "role": body.get("role"),
        "priority": body.get("priority"),
        "notes": body.get("notes"),
        "status": body.get("status", "Available"),
        "status_updated": None,
        "current_task_id": None,
        "location": body.get("location"),
        "needs_attention": False,
        "emergency_flag": False,
        "last_checkin_at": None,
        "checkin_reference_at": None,
        "last_comm_ping": None,
        "members_json": "[]",
        "vehicles_json": "[]",
        "equipment_json": "[]",
        "aircraft_json": "[]",
        "resource_type_id": body.get("resource_type_id"),
        "readiness_status": body.get("readiness_status"),
    }
    col.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/operations/teams/{team_id}")
def get_team(incident_id: str, team_id: int) -> dict:
    col = _teams(incident_id)
    doc = col.find_one({"int_id": team_id})
    if not doc:
        raise HTTPException(404, f"Team {team_id} not found")
    doc = _strip(doc)
    leader_name, leader_phone = _resolve_leader(incident_id, doc)
    doc["leader_name"] = leader_name
    doc["leader_phone"] = leader_phone
    return doc


@router.patch("/incidents/{incident_id}/operations/teams/{team_id}")
def update_team(incident_id: str, team_id: int, body: dict[str, Any]) -> dict:
    col = _teams(incident_id)
    body.pop("int_id", None)
    result = col.find_one_and_update(
        {"int_id": team_id},
        {"$set": body},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, f"Team {team_id} not found")
    return _strip(result)


@router.delete("/incidents/{incident_id}/operations/teams/{team_id}")
def delete_team(incident_id: str, team_id: int) -> dict:
    teams_col = _teams(incident_id)
    tasks_col = _tasks(incident_id)
    teams_col.delete_one({"int_id": team_id})
    # Remove from task_teams arrays
    tasks_col.update_many({}, {"$pull": {"task_teams": {"team_id": team_id}}})
    return {"ok": True}


@router.get("/incidents/{incident_id}/operations/teams/search")
def find_teams_by_label(incident_id: str, label: str = "") -> list[dict]:
    col = _teams(incident_id)
    if not label:
        return []
    import re
    pattern = re.compile(f"^{re.escape(label.strip())}$", re.IGNORECASE)
    return [_strip(d) for d in col.find({"$or": [{"name": pattern}, {"callsign": pattern}]})]


@router.patch("/incidents/{incident_id}/operations/teams/{team_id}/status")
def set_team_status(incident_id: str, team_id: int, body: dict[str, Any]) -> dict:
    """Update team status and optionally stamp a task_teams timestamp."""
    teams_col = _teams(incident_id)
    tasks_col = _tasks(incident_id)
    status_key = str(body.get("status_key", "")).lower()
    now = _now()
    display = {
        "enroute": "En Route", "arrival": "On Scene", "on scene": "On Scene", "rtb": "RTB",
    }.get(status_key, status_key.title())

    team = teams_col.find_one({"int_id": team_id})
    if not team:
        raise HTTPException(404, f"Team {team_id} not found")

    updates: dict = {"status": display, "status_updated": now}
    current_task_id = team.get("current_task_id")

    if status_key in {"available", "avail", "free", "unassigned"}:
        # Clear current task assignment
        if current_task_id is not None:
            # Stamp time_cleared on latest task_team for this team/task
            task = tasks_col.find_one({"int_id": current_task_id})
            if task:
                tt_list = task.get("task_teams") or []
                for i in range(len(tt_list) - 1, -1, -1):
                    if tt_list[i].get("team_id") == team_id:
                        if not tt_list[i].get("time_cleared"):
                            tasks_col.update_one(
                                {"int_id": current_task_id, f"task_teams.{i}.team_id": team_id},
                                {"$set": {f"task_teams.{i}.time_cleared": now}},
                            )
                        break
        updates["current_task_id"] = None

    elif status_key in TS_STATUS_COLS and current_task_id is not None:
        col_name = TS_STATUS_COLS[status_key]
        task = tasks_col.find_one({"int_id": current_task_id})
        if task:
            tt_list = task.get("task_teams") or []
            for i in range(len(tt_list) - 1, -1, -1):
                if tt_list[i].get("team_id") == team_id:
                    if not tt_list[i].get(col_name):
                        tasks_col.update_one(
                            {"int_id": current_task_id, f"task_teams.{i}.team_id": team_id},
                            {"$set": {f"task_teams.{i}.{col_name}": now}},
                        )
                    break

    result = teams_col.find_one_and_update(
        {"int_id": team_id},
        {"$set": updates},
        return_document=True,
    )
    return _strip(result)


@router.patch("/incidents/{incident_id}/operations/teams/{team_id}/checkin")
def touch_team_checkin(incident_id: str, team_id: int, body: dict[str, Any]) -> dict:
    col = _teams(incident_id)
    updates = {
        "last_checkin_at": body.get("checkin_time") or _now(),
        "checkin_reference_at": body.get("reference_time") or body.get("checkin_time") or _now(),
    }
    result = col.find_one_and_update({"int_id": team_id}, {"$set": updates}, return_document=True)
    if not result:
        raise HTTPException(404, f"Team {team_id} not found")
    return _strip(result)


@router.patch("/incidents/{incident_id}/operations/teams/{team_id}/comm-ping")
def reset_team_comm_timer(incident_id: str, team_id: int, body: dict[str, Any]) -> dict:
    col = _teams(incident_id)
    ts = body.get("when") or _now()
    result = col.find_one_and_update({"int_id": team_id}, {"$set": {"last_comm_ping": ts}}, return_document=True)
    if not result:
        raise HTTPException(404, f"Team {team_id} not found")
    return _strip(result)


@router.get("/incidents/{incident_id}/operations/team-assignment-rows")
def fetch_team_assignment_rows(incident_id: str) -> list[dict]:
    """Summary rows for the Team Status board."""
    teams_col = _teams(incident_id)
    tasks_col = _tasks(incident_id)
    _ensure_int_ids(teams_col)
    _ensure_int_ids(tasks_col)
    # Incident creation time is the earliest possible team baseline timestamp.
    incident_col = get_db(f"sarapp_incident_{incident_id}")["incident_profile"]
    profile = incident_col.find_one({"incident_id": incident_id}) or {}
    incident_created_at = profile.get("created_at") or profile.get("updated_at")
    rows = []
    for team in teams_col.find(sort=[("int_id", 1)]):
        team_int_id = team["int_id"]
        team_str_id = team.get("team_id") or str(team_int_id)
        current_task_ref = team.get("current_task_id")
        assignment = ""
        task_location = ""
        sortie_display = ""
        if current_task_ref is not None:
            task = (tasks_col.find_one({"task_id": current_task_ref})
                    if isinstance(current_task_ref, str)
                    else tasks_col.find_one({"int_id": current_task_ref}))
            if task:
                assignment = task.get("title") or ""
                task_location = task.get("location") or ""
                for tt in reversed(task.get("assigned_teams") or task.get("task_teams") or []):
                    ref = tt.get("team_id")
                    if ref == team_str_id or ref == team_int_id:
                        sortie_display = tt.get("sortie_id") or ""
                        break
        leader_name, leader_phone = _resolve_leader(incident_id, team)
        status = str(team.get("status") or "available").strip().lower()
        status = {"en route": "enroute", "on scene": "arrival", "rtb": "returning"}.get(status, status)
        location = team.get("location") or task_location or ""
        rows.append({
            "tt_id": None,
            "task_id": current_task_ref,
            "team_id": team_int_id,
            "sortie": sortie_display,
            "name": team.get("name") or f"Team {team_int_id}",
            "team_type": str(team.get("team_type") or "").upper(),
            "leader": leader_name,
            "contact": leader_phone,
            "status": status,
            "assignment": assignment,
            "location": location,
            "needs_attention": bool(team.get("needs_attention")),
            "needs_assistance_flag": bool(team.get("needs_attention")),
            "emergency_flag": bool(team.get("emergency_flag")),
            "last_checkin_at": team.get("last_checkin_at"),
            "checkin_reference_at": team.get("checkin_reference_at") or team.get("last_checkin_at") or team.get("created_at") or incident_created_at,
            "team_status_updated": team.get("status_updated"),
            "last_updated": team.get("last_checkin_at") or team.get("status_updated") or team.get("created_at") or incident_created_at,
        })
    return rows


# ---------------------------------------------------------------------------
# Task-team assignments
# ---------------------------------------------------------------------------

def _next_tt_id(task_teams: list) -> int:
    if not task_teams:
        return 1
    return max((tt.get("id") or 0) for tt in task_teams) + 1


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/teams")
def list_task_teams(incident_id: str, task_id: int) -> list[dict]:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    if not doc:
        raise HTTPException(404, f"Task {task_id} not found")
    return doc.get("task_teams") or []


@router.post("/incidents/{incident_id}/operations/tasks/{task_id}/teams", status_code=201)
def add_task_team(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    tasks_col = _tasks(incident_id)
    teams_col = _teams(incident_id)
    task = tasks_col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")

    team_id = body.get("team_id")
    sortie_id = body.get("sortie_id")
    primary = body.get("primary", False)

    # Create team if not specified
    if team_id is None:
        team_doc = create_team(incident_id, {})
        team_id = team_doc["int_id"]
        # Trigger ICS-214 stream creation via body flag
        body["auto_created"] = True

    existing_teams = task.get("task_teams") or []
    is_primary = 1 if (primary or not existing_teams) else 0
    now = _now()
    tt_id = _next_tt_id(existing_teams)

    # Get team info for embedding
    team = teams_col.find_one({"int_id": team_id})
    team_name = team.get("name") if team else None
    leader_name = None
    leader_contact = None

    tt = {
        "id": tt_id,
        "team_id": team_id,
        "team_name": team_name or f"Team {team_id}",
        "team_leader": leader_name or "",
        "team_leader_phone": leader_contact or "",
        "sortie_id": sortie_id,
        "is_primary": bool(is_primary),
        "time_assigned": now,
        "time_briefed": None,
        "time_enroute": None,
        "time_arrived": None,
        "time_discovery": None,
        "time_complete": None,
        "time_cleared": None,
    }
    tasks_col.update_one({"int_id": task_id}, {"$push": {"task_teams": tt}})
    # Update team's current_task_id
    teams_col.update_one({"int_id": team_id}, {"$set": {"current_task_id": task_id}})
    return {"tt_id": tt_id, "team_id": team_id, **tt}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}/status")
def set_task_team_status(incident_id: str, task_id: int, tt_id: int, body: dict[str, Any]) -> dict:
    tasks_col = _tasks(incident_id)
    teams_col = _teams(incident_id)
    status_key = str(body.get("status_key", "")).lower()
    now = _now()
    task = tasks_col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    tt_list = task.get("task_teams") or []
    idx = next((i for i, t in enumerate(tt_list) if t.get("id") == tt_id), None)
    if idx is None:
        raise HTTPException(404, f"Task team {tt_id} not found")

    updates: dict = {}
    col_name = TS_STATUS_COLS.get(status_key)
    if col_name:
        existing_ts = tt_list[idx].get(col_name)
        if not existing_ts:
            updates[f"task_teams.{idx}.{col_name}"] = now
    elif status_key == "available":
        for col in ["time_assigned", "time_briefed", "time_enroute", "time_arrived", "time_discovery", "time_complete", "time_cleared"]:
            updates[f"task_teams.{idx}.{col}"] = None

    # Update team status display
    display = {"enroute": "En Route", "arrival": "On Scene", "on scene": "On Scene", "rtb": "RTB"}.get(
        status_key, status_key.title()
    )
    team_id = tt_list[idx].get("team_id")
    if team_id is not None:
        teams_col.update_one({"int_id": team_id}, {"$set": {"status": display, "status_updated": now}})

    if updates:
        tasks_col.update_one({"int_id": task_id}, {"$set": updates})

    return {"ok": True, "status_key": status_key, "team_id": team_id}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}/primary")
def set_primary_team(incident_id: str, task_id: int, tt_id: int) -> dict:
    col = _tasks(incident_id)
    task = col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404)
    tt_list = task.get("task_teams") or []
    updates = {}
    for i, tt in enumerate(tt_list):
        updates[f"task_teams.{i}.is_primary"] = tt.get("id") == tt_id
    if updates:
        col.update_one({"int_id": task_id}, {"$set": updates})
    return {"ok": True}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}/sortie")
def update_sortie_id(incident_id: str, task_id: int, tt_id: int, body: dict[str, Any]) -> dict:
    col = _tasks(incident_id)
    task = col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404)
    tt_list = task.get("task_teams") or []
    idx = next((i for i, t in enumerate(tt_list) if t.get("id") == tt_id), None)
    if idx is None:
        raise HTTPException(404)
    col.update_one({"int_id": task_id}, {"$set": {f"task_teams.{idx}.sortie_id": body.get("sortie_id")}})
    return {"ok": True}


@router.delete("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}")
def remove_task_team(incident_id: str, task_id: int, tt_id: int) -> dict:
    col = _tasks(incident_id)
    task = col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404)
    tt_list = task.get("task_teams") or []
    was_primary = next((tt.get("is_primary", False) for tt in tt_list if tt.get("id") == tt_id), False)
    col.update_one({"int_id": task_id}, {"$pull": {"task_teams": {"id": tt_id}}})
    # If was primary and others remain, promote the first remaining
    if was_primary:
        task2 = col.find_one({"int_id": task_id})
        remaining = task2.get("task_teams") or [] if task2 else []
        if remaining:
            col.update_one({"int_id": task_id, "task_teams.id": remaining[0]["id"]},
                           {"$set": {"task_teams.$.is_primary": True}})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Task personnel / vehicles / aircraft (stubs until personnel module migrated)
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/personnel")
def list_task_personnel(incident_id: str, task_id: int) -> list[dict]:
    """Returns personnel embedded in task. Full join deferred until personnel module migrated."""
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    return doc.get("personnel") or [] if doc else []


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/vehicles")
def list_task_vehicles(incident_id: str, task_id: int) -> list[dict]:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    return doc.get("vehicles") or [] if doc else []


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/aircraft")
def list_task_aircraft(incident_id: str, task_id: int) -> list[dict]:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    return doc.get("aircraft") or [] if doc else []


# ---------------------------------------------------------------------------
# Comms
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/comms")
def list_task_comms(incident_id: str, task_id: int) -> list[dict]:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    return doc.get("comms") or [] if doc else []


@router.post("/incidents/{incident_id}/operations/tasks/{task_id}/comms", status_code=201)
def add_task_comm(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    col = _tasks(incident_id)
    task = col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404)
    comms = task.get("comms") or []
    comm_id = (max((c.get("id") or 0) for c in comms) + 1) if comms else 1
    comm = {"id": comm_id, "incident_channel_id": body.get("incident_channel_id"),
            "function": body.get("function"), "remarks": body.get("remarks")}
    col.update_one({"int_id": task_id}, {"$push": {"comms": comm}})
    return {"id": comm_id, **comm}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/comms/{comm_id}")
def update_task_comm(incident_id: str, task_id: int, comm_id: int, body: dict[str, Any]) -> dict:
    col = _tasks(incident_id)
    task = col.find_one({"int_id": task_id})
    if not task:
        raise HTTPException(404)
    comms = task.get("comms") or []
    idx = next((i for i, c in enumerate(comms) if c.get("id") == comm_id), None)
    if idx is None:
        raise HTTPException(404)
    updates = {}
    if "incident_channel_id" in body:
        updates[f"comms.{idx}.incident_channel_id"] = body["incident_channel_id"]
    if "function" in body:
        updates[f"comms.{idx}.function"] = body["function"]
    if updates:
        col.update_one({"int_id": task_id}, {"$set": updates})
    return {"ok": True}


@router.delete("/incidents/{incident_id}/operations/tasks/{task_id}/comms/{comm_id}")
def remove_task_comm(incident_id: str, task_id: int, comm_id: int) -> dict:
    col = _tasks(incident_id)
    col.update_one({"int_id": task_id}, {"$pull": {"comms": {"id": comm_id}}})
    return {"ok": True}


@router.get("/incidents/{incident_id}/operations/incident-channels")
def list_incident_channels(incident_id: str) -> list[dict]:
    """Returns incident comms channels — currently returns empty list until comms module is linked."""
    return []


# ---------------------------------------------------------------------------
# Task assignment
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/assignment")
def get_task_assignment(incident_id: str, task_id: int) -> dict:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    return doc.get("task_assignment") or {} if doc else {}


@router.put("/incidents/{incident_id}/operations/tasks/{task_id}/assignment")
def save_task_assignment(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    col = _tasks(incident_id)
    result = col.find_one_and_update(
        {"int_id": task_id},
        {"$set": {"task_assignment": body}},
        return_document=True,
    )
    if not result:
        raise HTTPException(404)
    return result.get("task_assignment") or {}


# ---------------------------------------------------------------------------
# Debriefs
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/debriefs")
def list_task_debriefs(incident_id: str, task_id: int) -> list[dict]:
    col = _debriefs(incident_id)
    return [_strip(d) for d in col.find({"task_id": task_id, "archived": {"$ne": True}})]


@router.post("/incidents/{incident_id}/operations/tasks/{task_id}/debriefs", status_code=201)
def create_debrief(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    col = _debriefs(incident_id)
    int_id = _next_int_id(col)
    doc = {
        "int_id": int_id,
        "task_id": task_id,
        "sortie_number": body.get("sortie_number", ""),
        "debriefer_id": body.get("debriefer_id", ""),
        "types": body.get("types", []),
        "forms": {},
        "archived": False,
        "created_at": _now(),
    }
    col.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/operations/debriefs/{debrief_id}")
def get_debrief(incident_id: str, debrief_id: int) -> dict:
    col = _debriefs(incident_id)
    doc = col.find_one({"int_id": debrief_id})
    if not doc:
        raise HTTPException(404)
    return _strip(doc)


@router.patch("/incidents/{incident_id}/operations/debriefs/{debrief_id}")
def update_debrief_header(incident_id: str, debrief_id: int, body: dict[str, Any]) -> dict:
    col = _debriefs(incident_id)
    body.pop("int_id", None)
    result = col.find_one_and_update({"int_id": debrief_id}, {"$set": body}, return_document=True)
    if not result:
        raise HTTPException(404)
    return _strip(result)


@router.put("/incidents/{incident_id}/operations/debriefs/{debrief_id}/forms/{form_key}")
def save_debrief_form(incident_id: str, debrief_id: int, form_key: str, body: dict[str, Any]) -> dict:
    col = _debriefs(incident_id)
    result = col.find_one_and_update(
        {"int_id": debrief_id},
        {"$set": {f"forms.{form_key}": body}},
        return_document=True,
    )
    if not result:
        raise HTTPException(404)
    return {"ok": True}


@router.post("/incidents/{incident_id}/operations/debriefs/{debrief_id}/archive")
def archive_debrief(incident_id: str, debrief_id: int) -> dict:
    col = _debriefs(incident_id)
    col.update_one({"int_id": debrief_id}, {"$set": {"archived": True}})
    return {"ok": True}


@router.delete("/incidents/{incident_id}/operations/debriefs/{debrief_id}")
def delete_debrief(incident_id: str, debrief_id: int) -> dict:
    col = _debriefs(incident_id)
    col.delete_one({"int_id": debrief_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/audit")
def list_task_audit(incident_id: str, task_id: int, page: int = 1, page_size: int = 50) -> list[dict]:
    """Returns audit entries embedded in the task document."""
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    entries = list(reversed(doc.get("audit") or [])) if doc else []
    start = (page - 1) * page_size
    return entries[start:start + page_size]


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/team-status-log")
def list_team_status_log(incident_id: str, task_id: int) -> list[dict]:
    """Returns team assignment timestamps for the status log view."""
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    if not doc:
        return []
    rows = []
    for tt in doc.get("task_teams") or []:
        rows.append({
            "tt_id": tt.get("id"),
            "team_id": tt.get("team_id"),
            "team_name": tt.get("team_name", ""),
            "time_assigned": tt.get("time_assigned"),
            "time_briefed": tt.get("time_briefed"),
            "time_enroute": tt.get("time_enroute"),
            "time_arrived": tt.get("time_arrived"),
            "time_discovery": tt.get("time_discovery"),
            "time_complete": tt.get("time_complete"),
            "time_cleared": tt.get("time_cleared"),
        })
    return rows
