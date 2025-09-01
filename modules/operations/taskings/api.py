from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from modules.operations.taskings.models import Task, TaskDetail, NarrativeEntry, TaskTeam
from modules.operations.taskings.data.lookups import CATEGORIES, PRIORITIES, TASK_STATUSES, team_statuses_for_category

# For now, simulate persistence with sample data and an in-memory store.
# When mission DB is ready, swap these out to use utils.mission_db connections.
try:
    from data.sample_data import SAMPLE_TASKS  # type: ignore[attr-defined]
except Exception:
    SAMPLE_TASKS = []  # type: ignore[assignment]

router = APIRouter(prefix="/api/operations/taskings", tags=["operations-taskings"])

# In-memory stores for demo
_TASKS: Dict[int, Task] = {}
_TASK_NARRATIVE: Dict[int, list[NarrativeEntry]] = {}
_TASK_TEAMS: Dict[int, list[TaskTeam]] = {}


# Seed from SAMPLE_TASKS if present
if SAMPLE_TASKS:
    for i, t in enumerate(SAMPLE_TASKS, start=1):
        task = Task(
            id=i,
            task_id=t.get("task_id", f"T-{i:03d}"),
            title=t.get("title", "Untitled Task"),
            description=t.get("description", ""),
            category=t.get("category", "<New Task>"),
            task_type=t.get("task_type"),
            priority=t.get("priority", "Medium"),
            status=t.get("status", "Draft"),
            location=t.get("location", ""),
            created_by=t.get("created_by", "system"),
            created_at=t.get("created_at", ""),
            assigned_to=t.get("assigned_to"),
            due_time=t.get("due_time"),
        )
        _TASKS[task.id] = task
        _TASK_NARRATIVE[task.id] = []
        _TASK_TEAMS[task.id] = []


@router.get("/lookups")
def get_lookups() -> Dict[str, Any]:
    return {
        "categories": CATEGORIES,
        "priorities": PRIORITIES,
        "task_statuses": TASK_STATUSES,
    }


@router.get("")
def list_tasks() -> Dict[str, Any]:
    return {"tasks": list(_TASKS.values()), "total": len(_TASKS)}


@router.get("/{task_id}")
def get_task(task_id: int) -> TaskDetail:
    task = _TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskDetail(task=task, narrative=_TASK_NARRATIVE.get(task_id, []), teams=_TASK_TEAMS.get(task_id, []))


@router.patch("/{task_id}/status")
def set_task_status(task_id: int, payload: Dict[str, Any]):
    task = _TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    status = payload.get("status")
    if status not in TASK_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    task.status = status
    return task


@router.get("/{task_id}/narrative")
def list_narrative(task_id: int):
    return {"entries": _TASK_NARRATIVE.get(task_id, [])}


@router.post("/{task_id}/narrative")
def add_narrative(task_id: int, payload: Dict[str, Any]):
    entries = _TASK_NARRATIVE.setdefault(task_id, [])
    entry = NarrativeEntry(
        id=len(entries) + 1,
        timestamp=payload.get("timestamp"),
        entry_text=payload.get("entry_text", ""),
        entered_by=payload.get("entered_by", ""),
        team_name=payload.get("team_name"),
        critical_flag=bool(payload.get("critical_flag", False)),
    )
    entries.append(entry)
    return entry


@router.get("/{task_id}/teams")
def list_task_teams(task_id: int):
    return {"teams": _TASK_TEAMS.get(task_id, [])}


@router.post("/{task_id}/teams")
def add_task_team(task_id: int, payload: Dict[str, Any]):
    teams = _TASK_TEAMS.setdefault(task_id, [])
    t = TaskTeam(
        id=len(teams) + 1,
        team_id=payload["team_id"],
        team_name=payload.get("team_name", f"Team {payload['team_id']}"),
        team_leader=payload.get("team_leader", ""),
        team_leader_phone=payload.get("team_leader_phone", ""),
        status="Assigned",
        sortie_number=payload.get("sortie_number"),
        assigned_ts=payload.get("assigned_ts"),
        primary=payload.get("primary", False),
    )
    # auto-primary if first team
    if not teams:
        t.primary = True
    teams.append(t)
    return t


@router.patch("/{task_id}/teams/{tt_id}")
def update_team_status(task_id: int, tt_id: int, payload: Dict[str, Any]):
    teams = _TASK_TEAMS.get(task_id, [])
    for t in teams:
        if t.id == tt_id:
            new_status = payload.get("status")
            if not new_status:
                raise HTTPException(400, detail="Missing status")
            allowed = team_statuses_for_category(_TASKS[task_id].category)
            if new_status not in allowed:
                raise HTTPException(400, detail=f"Invalid status for category: {new_status}")
            t.status = new_status
            # naive auto-stamp rules
            from datetime import datetime
            now = datetime.utcnow().isoformat()
            if new_status == "Assigned":
                t.assigned_ts = now
            elif new_status == "Briefed":
                t.briefed_ts = now
            elif new_status == "En Route":
                t.enroute_ts = now
            elif new_status == "On Scene":
                t.arrival_ts = now
            elif new_status == "Discovery/Find":
                t.discovery_ts = now
            elif new_status == "Complete":
                t.complete_ts = now
            return t
    raise HTTPException(404, detail="Team assignment not found")

