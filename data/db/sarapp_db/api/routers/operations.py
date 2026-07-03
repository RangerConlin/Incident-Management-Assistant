"""FastAPI router for the Operations module (tasks, teams, debriefs)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.client import get_db
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class TasksRepository(BaseRepository):
    collection_name = IncidentCollections.OPERATIONS_TASKS


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.OPERATIONS_TEAMS


class DebriefsRepository(BaseRepository):
    # Uses its own `archived` flag for soft-delete-like behavior; `delete_debrief`
    # below is a genuine hard delete, matching prior behavior.
    collection_name = IncidentCollections.OPERATIONS_TASK_DEBRIEFS
    soft_deletes = False


def _tasks_repo(incident_id: str) -> TasksRepository:
    return TasksRepository(get_db(f"sarapp_incident_{incident_id}"))


def _teams_repo(incident_id: str) -> TeamsRepository:
    return TeamsRepository(get_db(f"sarapp_incident_{incident_id}"))


def _debriefs_repo(incident_id: str) -> DebriefsRepository:
    return DebriefsRepository(get_db(f"sarapp_incident_{incident_id}"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _audit_entry(field_changed: str, old_value: Any, new_value: Any, changed_by: str = "") -> dict:
    return {
        "ts_utc": _now(),
        "field_changed": field_changed,
        "old_value": "" if old_value is None else str(old_value),
        "new_value": "" if new_value is None else str(new_value),
        "changed_by_display": changed_by or "",
    }


def _push_task_audit(tasks_repo: "TasksRepository", task_doc_id: str, entries: list[dict]) -> None:
    """Append Task Log entries for the Log tab's audit trail (doc['audit'])."""
    if entries:
        tasks_repo.apply_update(task_doc_id, {"$push": {"audit": {"$each": entries}}})


# Read-only raw collection access — no broadcast needed for reads, so these
# keep talking to the collection directly rather than through a repository.
def _tasks(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.OPERATIONS_TASKS]


def _teams(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.OPERATIONS_TEAMS]


def _debriefs(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.OPERATIONS_TASK_DEBRIEFS]


def _personnel(incident_id: str):
    return get_db(f"sarapp_incident_{incident_id}")["incident_personnel"]


def _find_by_int_id(repo: BaseRepository, int_id: int) -> Optional[dict]:
    return repo.find_one({"int_id": int_id})


def _find_air_ops_branch_position_id(incident_id: str) -> Optional[int]:
    """Return the active Air Operations Branch position_id for chain-of-command
    auto-assignment of aircraft (team_type == "AIR") teams, or None if the
    incident has no Air Operations Branch yet (see incident_org.py's
    is_air_ops flag - there can only be one per incident)."""
    col = get_db(f"sarapp_incident_{incident_id}")[IncidentCollections.ORG_POSITIONS]
    doc = col.find_one({"incident_id": incident_id, "is_air_ops": True, "status": "active"})
    return doc.get("position_id") if doc else None


def _find_incident_person(incident_id: str, person_record) -> Optional[dict]:
    """Look up an incident-scoped personnel copy by person_record."""
    col = _personnel(incident_id)
    try:
        return col.find_one({"person_record": int(person_record)})
    except (TypeError, ValueError):
        return None


def _resolve_leader(incident_id: str, team_doc: dict) -> tuple[str, str]:
    """Return (leader_name, leader_phone) resolved from personnel if needed."""
    leader_name = team_doc.get("leader_name") or ""
    leader_phone = team_doc.get("leader_phone") or team_doc.get("phone") or ""
    pid = team_doc.get("leader_person_record") or team_doc.get("leader_personnel_id")
    if pid and (not leader_name or not leader_phone):
        p = _find_incident_person(incident_id, pid)
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
    # Backfill bookkeeping only (assigns int_id to legacy docs that predate
    # it) — not a user-facing write, so it doesn't go through a repository
    # or broadcast.
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


def _normalize_incident_person(doc: dict) -> dict:
    return {
        "person_record": doc.get("person_record"),
        "name": doc.get("name") or "",
        "rank": doc.get("rank"),
        "callsign": doc.get("callsign"),
        "role": doc.get("role"),
        "primary_role": doc.get("role"),
        "phone": doc.get("phone"),
        "email": doc.get("email"),
        "organization": doc.get("organization"),
        "person_id": doc.get("person_id") or doc.get("badge_number") or "",
        "is_medic": bool(doc.get("is_medic", False)),
    }


# ---------------------------------------------------------------------------
# Incident-scoped personnel (check-in copies of master roster records,
# keyed by the master record's int_id — see _find_incident_person)
# ---------------------------------------------------------------------------
# Personnel module is not yet migrated onto BaseRepository (see CLAUDE.md);
# left as raw collection writes, unchanged, deliberately out of this pass's
# scope.

@router.get("/incidents/{incident_id}/operations/personnel/{person_record}")
def get_incident_person(incident_id: str, person_record: int) -> dict:
    doc = _find_incident_person(incident_id, person_record)
    if not doc:
        raise HTTPException(404, f"Person {person_record} not found in incident {incident_id}")
    return _normalize_incident_person(doc)


@router.patch("/incidents/{incident_id}/operations/personnel/{person_record}")
def update_incident_person(incident_id: str, person_record: int, body: dict[str, Any]) -> dict:
    col = _personnel(incident_id)
    doc = _find_incident_person(incident_id, person_record)
    if not doc:
        raise HTTPException(404, f"Person {person_record} not found in incident {incident_id}")
    updates = {k: v for k, v in body.items() if k in ("is_medic", "rank")}
    if updates:
        col.update_one({"_id": doc["_id"]}, {"$set": updates})
        doc.update(updates)
    return _normalize_incident_person(doc)


@router.post("/incidents/{incident_id}/operations/personnel/sync-from-master")
def sync_incident_personnel_from_master(incident_id: str) -> dict:
    """Refresh every incident-scoped personnel copy from its master record.

    Called when an incident is loaded, so copies that missed a push-down
    sync (because a different incident was active at edit time) catch up.
    """
    from sarapp_db.mongo.database_manager import get_master_db
    from sarapp_db.mongo.collection_names import MasterCollections

    incident_col = _personnel(incident_id)
    master_col = get_master_db()[MasterCollections.PERSONNEL]
    updated = 0
    for copy_doc in incident_col.find({"person_record": {"$exists": True}}):
        master_doc = master_col.find_one({"person_record": copy_doc["person_record"]})
        if not master_doc:
            continue
        sync_fields = {
            "name": master_doc.get("name"),
            "rank": master_doc.get("rank"),
            "callsign": master_doc.get("callsign"),
            "role": master_doc.get("primary_role") or master_doc.get("role"),
            "phone": master_doc.get("phone"),
            "email": master_doc.get("email"),
            "organization": master_doc.get("organization"),
            "person_id": master_doc.get("person_id") or "",
            "is_medic": bool(master_doc.get("is_medic", False)),
        }
        incident_col.update_one({"_id": copy_doc["_id"]}, {"$set": sync_fields})
        updated += 1
    return {"updated": updated}


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
    repo = _tasks_repo(incident_id)
    int_id = _next_int_id(repo._col)
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
        "location_facility_id": body.get("location_facility_id"),
        "assignment": body.get("assignment"),
        "team_leader": body.get("team_leader"),
        "team_phone": body.get("team_phone"),
        "created_by": body.get("created_by", ""),
        "created_at": _now(),
        "due_time": body.get("due_time"),
        "task_teams": [],
        "active_team_ids": [],
        "personnel": [],
        "vehicles": [],
        "aircraft": [],
        "comms": [],
        "task_assignment": {},
    }
    doc = repo.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}")
def get_task(incident_id: str, task_id: int) -> dict:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id})
    if not doc:
        raise HTTPException(404, f"Task {task_id} not found")
    return _strip(doc)


_AUDIT_FIELD_LABELS = {
    "task_id": "Task ID", "title": "Title", "category": "Category", "task_type": "Type",
    "priority": "Priority", "status": "Status", "location": "Location", "location_facility_id": "Location Facility", "assignment": "Assignment",
}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}")
def update_task(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    repo = _tasks_repo(incident_id)
    doc = _find_by_int_id(repo, task_id)
    if not doc:
        raise HTTPException(404, f"Task {task_id} not found")
    body = dict(body)
    body.pop("int_id", None)
    changed_by = str(body.pop("changed_by", "") or "")
    entries = [
        _audit_entry(label, doc.get(field), new_val, changed_by)
        for field, label in _AUDIT_FIELD_LABELS.items()
        if field in body and (new_val := body[field]) != doc.get(field)
    ]
    update: dict[str, Any] = {"$set": body}
    if entries:
        update["$push"] = {"audit": {"$each": entries}}
    repo.apply_update(doc["_id"], update)
    return _strip(repo.find_by_id(doc["_id"]))


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
        # active_team_ids is maintained directly by add_task_team ($addToSet)
        # and remove_task_team/set_team_status ($pull) — it's the team_ids
        # currently assigned, no separate lookup needed. Tasks created before
        # this field existed have no key at all; fall back to the older
        # current_task_id query for those so they don't need a migration.
        active_ids = doc.get("active_team_ids")
        assigned = []
        if active_ids is not None:
            teams_iter = teams_col.find({
                "$or": [{"int_id": {"$in": active_ids}}, {"team_id": {"$in": active_ids}}]
            })
        else:
            teams_iter = teams_col.find({"current_task_id": {"$in": [task_int_id, task_str_id]}})
        for team in teams_iter:
            sortie_id = None
            for tt in reversed(doc.get("task_teams") or doc.get("assigned_teams") or []):
                if tt.get("team_id") in (team.get("int_id"), team.get("team_id")):
                    sortie_id = tt.get("sortie_id")
                    break
            assigned.append(team.get("name") or sortie_id or f"Team {team.get('int_id')}")
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
    repo = _tasks_repo(incident_id)
    doc = _find_by_int_id(repo, task_id)
    if not doc:
        raise HTTPException(404, f"Task {task_id} not found")
    repo.update_one(doc["_id"], {"status": to_db})
    return _strip(repo.find_by_id(doc["_id"]))


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
    repo = _teams_repo(incident_id)
    int_id = _next_int_id(repo._col)
    operational_unit_id = body.get("operational_unit_id")
    if operational_unit_id is None and str(body.get("team_type") or "").strip().upper() == "AIR":
        # Aircraft teams auto-slot under the Air Operations Branch for chain
        # of command - unless the caller already picked a unit explicitly.
        operational_unit_id = _find_air_ops_branch_position_id(incident_id)
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
        "ci_status": body.get("ci_status", "Available"),
        "status_updated": None,
        "current_task_id": body.get("current_task_id"),
        "location": body.get("location"),
        "operational_unit_id": operational_unit_id,
        "needs_attention": bool(body.get("needs_attention", False)),
        "emergency_flag": False,
        "last_checkin_at": None,
        "checkin_reference_at": None,
        "last_comm_ping": None,
        "members_json": body.get("members_json", "[]"),
        "vehicles_json": body.get("vehicles_json", "[]"),
        "equipment_json": body.get("equipment_json", "[]"),
        "aircraft_json": body.get("aircraft_json", "[]"),
        "resource_type_id": body.get("resource_type_id"),
        "readiness_status": body.get("readiness_status"),
    }
    doc = repo.insert_one(doc)
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
    repo = _teams_repo(incident_id)
    doc = _find_by_int_id(repo, team_id)
    if not doc:
        raise HTTPException(404, f"Team {team_id} not found")
    body.pop("int_id", None)
    if "team_type" in body and "operational_unit_id" not in body:
        # If this edit is changing the team to an aircraft type and isn't
        # also explicitly picking a unit, auto-slot under the Air
        # Operations Branch for chain of command (see create_team above).
        if str(body.get("team_type") or "").strip().upper() == "AIR":
            air_ops_id = _find_air_ops_branch_position_id(incident_id)
            if air_ops_id is not None:
                body["operational_unit_id"] = air_ops_id
    repo.update_one(doc["_id"], body)
    return _strip(repo.find_by_id(doc["_id"]))


@router.delete("/incidents/{incident_id}/operations/teams/{team_id}")
def delete_team(incident_id: str, team_id: int) -> dict:
    teams_repo = _teams_repo(incident_id)
    doc = _find_by_int_id(teams_repo, team_id)
    if doc:
        teams_repo.delete_one(doc["_id"])
    # Remove from task_teams arrays across every task in one bulk operation —
    # not a single-document broadcast-able write, so this stays a raw call.
    _tasks(incident_id).update_many({}, {"$pull": {"task_teams": {"team_id": team_id}}})
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
    teams_repo = _teams_repo(incident_id)
    tasks_repo = _tasks_repo(incident_id)
    status_key = str(body.get("status_key", "")).lower()
    now = _now()
    display = {
        "enroute": "En Route", "arrival": "On Scene", "on scene": "On Scene", "rtb": "RTB",
    }.get(status_key, status_key.title())

    team = _find_by_int_id(teams_repo, team_id)
    if not team:
        raise HTTPException(404, f"Team {team_id} not found")

    updates: dict = {"status": display, "status_updated": now}
    current_task_id = team.get("current_task_id")

    if status_key in {"available", "avail", "free", "unassigned"}:
        # Clear current task assignment
        if current_task_id is not None:
            # Stamp time_cleared on latest task_team for this team/task
            task = _find_by_int_id(tasks_repo, current_task_id)
            if task:
                tt_list = task.get("task_teams") or []
                for i in range(len(tt_list) - 1, -1, -1):
                    if tt_list[i].get("team_id") == team_id:
                        if not tt_list[i].get("time_cleared"):
                            tasks_repo.update_one(task["_id"], {f"task_teams.{i}.time_cleared": now})
                        break
            if task:
                tasks_repo.apply_update(task["_id"], {"$pull": {"active_team_ids": team_id}})
        updates["current_task_id"] = None

    elif status_key in TS_STATUS_COLS and current_task_id is not None:
        col_name = TS_STATUS_COLS[status_key]
        task = _find_by_int_id(tasks_repo, current_task_id)
        if task:
            tt_list = task.get("task_teams") or []
            for i in range(len(tt_list) - 1, -1, -1):
                if tt_list[i].get("team_id") == team_id:
                    if not tt_list[i].get(col_name):
                        entry = _audit_entry(
                            f"Team Status ({tt_list[i].get('team_name') or team_id})",
                            _team_status_from_tt(tt_list[i]),
                            display,
                            str(body.get("changed_by") or ""),
                        )
                        tasks_repo.apply_update(
                            task["_id"],
                            {"$set": {f"task_teams.{i}.{col_name}": now}, "$push": {"audit": entry}},
                        )
                    break

    teams_repo.update_one(team["_id"], updates)
    return _strip(teams_repo.find_by_id(team["_id"]))


@router.patch("/incidents/{incident_id}/operations/teams/{team_id}/checkin")
def touch_team_checkin(incident_id: str, team_id: int, body: dict[str, Any]) -> dict:
    repo = _teams_repo(incident_id)
    doc = _find_by_int_id(repo, team_id)
    if not doc:
        raise HTTPException(404, f"Team {team_id} not found")
    updates = {
        "last_checkin_at": body.get("checkin_time") or _now(),
        "checkin_reference_at": body.get("reference_time") or body.get("checkin_time") or _now(),
    }
    repo.update_one(doc["_id"], updates)
    return _strip(repo.find_by_id(doc["_id"]))


@router.patch("/incidents/{incident_id}/operations/teams/{team_id}/comm-ping")
def reset_team_comm_timer(incident_id: str, team_id: int, body: dict[str, Any]) -> dict:
    repo = _teams_repo(incident_id)
    doc = _find_by_int_id(repo, team_id)
    if not doc:
        raise HTTPException(404, f"Team {team_id} not found")
    ts = body.get("when") or body.get("ts") or _now()
    repo.update_one(doc["_id"], {"last_comm_ping": ts})
    return _strip(repo.find_by_id(doc["_id"]))


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
                task_number = task.get("task_id") or ""
                task_title = task.get("title") or ""
                if task_number and task_title:
                    assignment = f"{task_number} - {task_title}"
                else:
                    assignment = task_number or task_title
                task_location = task.get("location") or ""
                for tt in reversed(task.get("task_teams") or task.get("assigned_teams") or []):
                    ref = tt.get("team_id")
                    if ref == team_str_id or ref == team_int_id:
                        sortie_display = tt.get("sortie_id") or ""
                        break
        leader_name, leader_phone = _resolve_leader(incident_id, team)
        status = str(team.get("status") or "available").strip().lower()
        status = {"en route": "enroute", "on scene": "arrival", "rtb": "returning"}.get(status, status)
        location = team.get("location") or task_location or ""
        team_type = str(team.get("team_type") or "").upper()
        is_aircraft = team_type == "AIR"
        display_name = (team.get("callsign") if is_aircraft else None) or team.get("name") or f"Team {team_int_id}"
        rows.append({
            "tt_id": None,
            "task_id": current_task_ref,
            "team_id": team_int_id,
            "sortie": sortie_display,
            "name": display_name,
            "team_type": team_type,
            "leader": leader_name,
            "contact": leader_phone,
            "status": status,
            "ci_status": team.get("ci_status") or "Available",
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
    teams_col = _teams(incident_id)
    out: list[dict] = []
    for tt in (doc.get("task_teams") or []):
        tt = dict(tt)
        team = teams_col.find_one({"int_id": tt.get("team_id")})
        if team:
            leader_name, leader_phone = _resolve_leader(incident_id, team)
            tt["team_leader"] = leader_name or tt.get("team_leader") or ""
            tt["team_leader_phone"] = leader_phone or tt.get("team_leader_phone") or ""
            tt["team_name"] = team.get("name") or tt.get("team_name") or f"Team {tt.get('team_id')}"
        out.append(tt)
    return out


@router.post("/incidents/{incident_id}/operations/tasks/{task_id}/teams", status_code=201)
def add_task_team(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    tasks_repo = _tasks_repo(incident_id)
    teams_repo = _teams_repo(incident_id)
    task = _find_by_int_id(tasks_repo, task_id)
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
    team = _find_by_int_id(teams_repo, team_id)
    team_name = team.get("name") if team else None
    leader_name, leader_contact = _resolve_leader(incident_id, team or {})

    # A team can only be actively on one task at a time. If it's still
    # parked on a previous task (current_task_id wasn't cleared because the
    # caller never called remove_task_team), strip it from there now so it
    # doesn't show as assigned to both.
    if team is not None:
        previous_task_ref = team.get("current_task_id")
        if previous_task_ref is not None and previous_task_ref != task_id:
            previous_task = (
                tasks_repo.find_one({"task_id": previous_task_ref})
                if isinstance(previous_task_ref, str)
                else _find_by_int_id(tasks_repo, previous_task_ref)
            )
            if previous_task is not None and previous_task["_id"] != task["_id"]:
                tasks_repo.apply_update(
                    previous_task["_id"],
                    {
                        "$pull": {
                            "task_teams": {"team_id": team_id},
                            "active_team_ids": team_id,
                        }
                    },
                )

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
    tasks_repo.apply_update(
        task["_id"],
        {
            "$push": {
                "task_teams": tt,
                "audit": {"$each": [_audit_entry("Team", None, tt["team_name"], str(body.get("changed_by") or ""))]},
            },
            "$addToSet": {"active_team_ids": team_id},
        },
    )
    # Update team's current_task_id
    if team is not None:
        teams_repo.update_one(team["_id"], {"current_task_id": task_id})
    return {"tt_id": tt_id, "team_id": team_id, **tt}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}/status")
def set_task_team_status(incident_id: str, task_id: int, tt_id: int, body: dict[str, Any]) -> dict:
    tasks_repo = _tasks_repo(incident_id)
    teams_repo = _teams_repo(incident_id)
    status_key = str(body.get("status_key", "")).lower()
    now = _now()
    task = _find_by_int_id(tasks_repo, task_id)
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
        team = _find_by_int_id(teams_repo, team_id)
        if team:
            teams_repo.update_one(team["_id"], {"status": display, "status_updated": now})

    entry = _audit_entry(
        f"Team Status ({tt_list[idx].get('team_name') or team_id})",
        _team_status_from_tt(tt_list[idx]),
        display,
        str(body.get("changed_by") or ""),
    )
    if updates:
        tasks_repo.apply_update(task["_id"], {"$set": updates, "$push": {"audit": entry}})
    else:
        tasks_repo.apply_update(task["_id"], {"$push": {"audit": entry}})

    return {"ok": True, "status_key": status_key, "team_id": team_id}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}/primary")
def set_primary_team(incident_id: str, task_id: int, tt_id: int, body: dict[str, Any] | None = None) -> dict:
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if not task:
        raise HTTPException(404)
    tt_list = task.get("task_teams") or []
    updates = {}
    new_primary_name = None
    for i, tt in enumerate(tt_list):
        is_new_primary = tt.get("id") == tt_id
        updates[f"task_teams.{i}.is_primary"] = is_new_primary
        if is_new_primary:
            new_primary_name = tt.get("team_name")
    update: dict[str, Any] = {"$set": updates} if updates else {}
    if new_primary_name is not None:
        entry = _audit_entry("Primary Team", None, new_primary_name, str((body or {}).get("changed_by") or ""))
        update["$push"] = {"audit": entry}
    if update:
        repo.apply_update(task["_id"], update)
    return {"ok": True}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}/sortie")
def update_sortie_id(incident_id: str, task_id: int, tt_id: int, body: dict[str, Any]) -> dict:
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if not task:
        raise HTTPException(404)
    tt_list = task.get("task_teams") or []
    idx = next((i for i, t in enumerate(tt_list) if t.get("id") == tt_id), None)
    if idx is None:
        raise HTTPException(404)
    old_sortie = tt_list[idx].get("sortie_id")
    new_sortie = body.get("sortie_id")
    update: dict[str, Any] = {"$set": {f"task_teams.{idx}.sortie_id": new_sortie}}
    if new_sortie != old_sortie:
        team_name = tt_list[idx].get("team_name")
        update["$push"] = {
            "audit": _audit_entry(f"Sortie Number ({team_name})", old_sortie, new_sortie, str(body.get("changed_by") or ""))
        }
    repo.apply_update(task["_id"], update)
    return {"ok": True}


@router.delete("/incidents/{incident_id}/operations/tasks/{task_id}/teams/{tt_id}")
def remove_task_team(incident_id: str, task_id: int, tt_id: int, changed_by: str = "") -> dict:
    tasks_repo = _tasks_repo(incident_id)
    teams_repo = _teams_repo(incident_id)
    task = _find_by_int_id(tasks_repo, task_id)
    if not task:
        raise HTTPException(404)
    tt_list = task.get("task_teams") or []
    removed_tt = next((tt for tt in tt_list if tt.get("id") == tt_id), None)
    was_primary = bool(removed_tt and removed_tt.get("is_primary", False))
    removed_team_id = removed_tt.get("team_id") if removed_tt else None
    pull_spec: dict[str, Any] = {"task_teams": {"id": tt_id}}
    if removed_team_id is not None:
        pull_spec["active_team_ids"] = removed_team_id
    update: dict[str, Any] = {"$pull": pull_spec}
    if removed_tt is not None:
        update["$push"] = {
            "audit": _audit_entry("Team", removed_tt.get("team_name"), None, changed_by)
        }
    tasks_repo.apply_update(task["_id"], update)
    # If was primary and others remain, promote the first remaining
    if was_primary:
        task2 = tasks_repo.find_by_id(task["_id"])
        remaining = task2.get("task_teams") or [] if task2 else []
        if remaining:
            promote_idx = 0
            tasks_repo.update_one(task["_id"], {f"task_teams.{promote_idx}.is_primary": True})
    # Clear the team's stale assignment pointer, but only if it still points
    # here — avoids clobbering a newer assignment made after this removal.
    if removed_team_id is not None:
        removed_team = _find_by_int_id(teams_repo, removed_team_id)
        if removed_team and removed_team.get("current_task_id") == task_id:
            teams_repo.update_one(removed_team["_id"], {"current_task_id": None})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Task personnel / vehicles / aircraft — rolled up from the teams assigned
# to the task (there is no separate task-level assignment step; a person,
# vehicle, or aircraft shows up here because their team is on this task).
# ---------------------------------------------------------------------------

def _parse_id_list(value: Any) -> list[int]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    if not isinstance(value, (list, tuple)):
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _task_team_docs(incident_id: str, task_id: int) -> list[dict]:
    """Full team documents for every team currently assigned to the task."""
    task = _tasks(incident_id).find_one({"int_id": task_id})
    if not task:
        return []
    teams_col = _teams(incident_id)
    team_ids = [tt.get("team_id") for tt in (task.get("task_teams") or []) if tt.get("team_id") is not None]
    out: list[dict] = []
    for tid in team_ids:
        team = teams_col.find_one({"int_id": tid})
        if team:
            out.append(team)
    return out


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/personnel")
def list_task_personnel(incident_id: str, task_id: int) -> list[dict]:
    """Personnel rolled up from every team's roster on this task."""
    out: list[dict] = []
    for team in _task_team_docs(incident_id, task_id):
        team_name = team.get("name") or f"Team {team.get('int_id')}"
        member_ids = _parse_id_list(team.get("members_json") or team.get("member_person_records") or team.get("member_personnel_ids"))
        for pid in member_ids:
            person = _find_incident_person(incident_id, pid)
            if not person:
                continue
            name = person.get("name") or (
                ((person.get("first_name") or "") + " " + (person.get("last_name") or "")).strip()
            )
            out.append({
                "active": True,
                "name": name,
                "id": person.get("master_id") if person.get("master_id") is not None else person.get("sqlite_id"),
                "rank": person.get("rank") or "",
                "role": person.get("role") or "",
                "organization": person.get("organization") or "",
                "phone": person.get("phone") or "",
                "team_name": team_name,
            })
    return out


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/vehicles")
def list_task_vehicles(incident_id: str, task_id: int) -> list[dict]:
    """Vehicles rolled up from every team's roster on this task."""
    master_vehicles = get_master_db()[MasterCollections.VEHICLES]
    out: list[dict] = []
    for team in _task_team_docs(incident_id, task_id):
        for vid in _parse_id_list(team.get("vehicles_json") or team.get("vehicle_ids")):
            v = master_vehicles.find_one({"$or": [{"int_id": vid}, {"vehicle_id": vid}]})
            if not v:
                continue
            out.append({
                "active": True,
                "id": v.get("vehicle_id") or v.get("int_id"),
                "license_plate": v.get("license_plate") or "",
                "type": v.get("type") or "",
                "organization": v.get("organization") or "",
            })
    return out


@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/aircraft")
def list_task_aircraft(incident_id: str, task_id: int) -> list[dict]:
    """Aircraft rolled up from every team's roster on this task."""
    master_aircraft = get_master_db()[MasterCollections.AIRCRAFT]
    out: list[dict] = []
    for team in _task_team_docs(incident_id, task_id):
        for aid in _parse_id_list(team.get("aircraft_json") or team.get("aircraft_ids")):
            a = master_aircraft.find_one({"int_id": aid})
            if not a:
                continue
            out.append({
                "active": True,
                "callsign": a.get("callsign") or "",
                "tail_number": a.get("tail_number") or "",
                "type": a.get("type") or "",
                "organization": a.get("organization") or "",
            })
    return out


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
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if not task:
        raise HTTPException(404)
    comms = task.get("comms") or []
    comm_id = (max((c.get("id") or 0) for c in comms) + 1) if comms else 1
    comm = {"id": comm_id, "incident_channel_id": body.get("incident_channel_id"),
            "function": body.get("function"), "remarks": body.get("remarks")}
    repo.apply_update(task["_id"], {"$push": {"comms": comm}})
    return {"id": comm_id, **comm}


@router.patch("/incidents/{incident_id}/operations/tasks/{task_id}/comms/{comm_id}")
def update_task_comm(incident_id: str, task_id: int, comm_id: int, body: dict[str, Any]) -> dict:
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
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
        repo.update_one(task["_id"], updates)
    return {"ok": True}


@router.delete("/incidents/{incident_id}/operations/tasks/{task_id}/comms/{comm_id}")
def remove_task_comm(incident_id: str, task_id: int, comm_id: int) -> dict:
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if task:
        repo.apply_update(task["_id"], {"$pull": {"comms": {"id": comm_id}}})
    return {"ok": True}


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
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if not task:
        raise HTTPException(404)
    repo.update_one(task["_id"], {"task_assignment": body})
    updated = repo.find_by_id(task["_id"])
    return updated.get("task_assignment") or {}


# ---------------------------------------------------------------------------
# Task narratives
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/narrative")
def list_task_narrative(incident_id: str, task_id: int) -> list[dict]:
    col = _tasks(incident_id)
    doc = col.find_one({"int_id": task_id}, {"narrative": 1})
    entries = sorted(
        (doc or {}).get("narrative") or [],
        key=lambda e: e.get("timestamp", ""),
    )
    return entries


@router.post("/incidents/{incident_id}/operations/tasks/{task_id}/narrative", status_code=201)
def add_task_narrative(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if not task:
        raise HTTPException(404)
    entry = {
        "id": _new_id(),
        "timestamp": body.get("timestamp") or _now(),
        "narrative": body.get("narrative") or body.get("text") or "",
        "entered_by": body.get("entered_by") or "",
        "team_id": body.get("team_id"),
        "team_num": body.get("team_num") or "",
        "critical": bool(body.get("critical", False)),
        "source": body.get("source", "manual"),
    }
    repo.apply_update(task["_id"], {"$push": {"narrative": entry}})
    return entry


@router.delete(
    "/incidents/{incident_id}/operations/tasks/{task_id}/narrative/{entry_id}",
    status_code=204,
)
def delete_task_narrative(incident_id: str, task_id: int, entry_id: str) -> None:
    repo = _tasks_repo(incident_id)
    task = _find_by_int_id(repo, task_id)
    if task:
        repo.apply_update(task["_id"], {"$pull": {"narrative": {"id": entry_id}}})


# ---------------------------------------------------------------------------
# Debriefs
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/operations/tasks/{task_id}/debriefs")
def list_task_debriefs(incident_id: str, task_id: int) -> list[dict]:
    col = _debriefs(incident_id)
    return [_strip(d) for d in col.find({"task_id": task_id, "archived": {"$ne": True}})]


@router.post("/incidents/{incident_id}/operations/tasks/{task_id}/debriefs", status_code=201)
def create_debrief(incident_id: str, task_id: int, body: dict[str, Any]) -> dict:
    repo = _debriefs_repo(incident_id)
    int_id = _next_int_id(repo._col)
    doc = {
        "int_id": int_id,
        "task_id": task_id,
        "sortie_number": body.get("sortie_number", ""),
        "debriefer_id": body.get("debriefer_id", ""),
        "types": body.get("types", []),
        "forms": {},
        "linked_clue_ids": [],
        "linked_subject_ids": [],
        "archived": False,
        "created_at": _now(),
    }
    doc = repo.insert_one(doc)
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
    repo = _debriefs_repo(incident_id)
    doc = _find_by_int_id(repo, debrief_id)
    if not doc:
        raise HTTPException(404)
    body.pop("int_id", None)
    repo.update_one(doc["_id"], body)
    return _strip(repo.find_by_id(doc["_id"]))


@router.put("/incidents/{incident_id}/operations/debriefs/{debrief_id}/forms/{form_key}")
def save_debrief_form(incident_id: str, debrief_id: int, form_key: str, body: dict[str, Any]) -> dict:
    repo = _debriefs_repo(incident_id)
    doc = _find_by_int_id(repo, debrief_id)
    if not doc:
        raise HTTPException(404)
    repo.update_one(doc["_id"], {f"forms.{form_key}": body})
    return {"ok": True}


@router.post("/incidents/{incident_id}/operations/debriefs/{debrief_id}/archive")
def archive_debrief(incident_id: str, debrief_id: int) -> dict:
    repo = _debriefs_repo(incident_id)
    doc = _find_by_int_id(repo, debrief_id)
    if doc:
        repo.update_one(doc["_id"], {"archived": True})
    return {"ok": True}


@router.delete("/incidents/{incident_id}/operations/debriefs/{debrief_id}")
def delete_debrief(incident_id: str, debrief_id: int) -> dict:
    repo = _debriefs_repo(incident_id)
    doc = _find_by_int_id(repo, debrief_id)
    if doc:
        repo.delete_one(doc["_id"])
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
