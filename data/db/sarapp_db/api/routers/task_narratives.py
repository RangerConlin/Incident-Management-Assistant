"""FastAPI router — task narrative entries embedded on incident tasks."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class TasksRepository(BaseRepository):
    collection_name = IncidentCollections.TASKS


def _repo(incident_id: str) -> TasksRepository:
    return TasksRepository(get_incident_db(incident_id))


def _new_entry_id() -> str:
    return uuid.uuid4().hex


def _task_query(task_id: int) -> dict[str, Any]:
    return {"int_id": task_id}


def _normalize_entry(entry: dict[str, Any], task_id: int) -> dict[str, Any]:
    doc = dict(entry)
    doc["id"] = str(doc.get("id") or doc.get("entry_id") or doc.get("_id") or _new_entry_id())
    doc["task_id"] = int(doc.get("task_id") or task_id)
    doc["timestamp"] = str(doc.get("timestamp") or doc.get("ts_utc") or "")
    doc["narrative"] = str(doc.get("narrative") or doc.get("text") or doc.get("entry_text") or "")
    doc["entered_by"] = str(doc.get("entered_by") or doc.get("author_user_id") or doc.get("author_display_name") or "")
    doc["team_num"] = str(doc.get("team_num") or doc.get("team") or doc.get("team_name") or "")
    doc["critical"] = 1 if doc.get("critical") in (True, 1, "1", "true", "True") else 0
    doc.pop("_id", None)
    doc.pop("entry_id", None)
    return doc


def _find_entry(
    repo: TasksRepository,
    entry_id: str,
) -> tuple[dict[str, Any], int, dict[str, Any]]:
    task = repo.find_one({"$or": [{"narrative.id": entry_id}, {"narrative.entry_id": entry_id}]})
    if not task:
        raise HTTPException(404, f"Narrative entry '{entry_id}' not found")
    entries = task.get("narrative") or []
    for idx, entry in enumerate(entries):
        if str(entry.get("id") or entry.get("entry_id") or "") == str(entry_id):
            return task, idx, _normalize_entry(entry, int(task.get("int_id") or 0))
    raise HTTPException(404, f"Narrative entry '{entry_id}' not found")


class NarrativeCreate(BaseModel):
    task_id: int
    timestamp: str
    narrative: str
    entered_by: str = ""
    team_num: str = ""
    critical: int = 0


class NarrativeUpdate(BaseModel):
    timestamp: Optional[str] = None
    narrative: Optional[str] = None
    entered_by: Optional[str] = None
    team_num: Optional[str] = None
    critical: Optional[int] = None


@router.get("/incidents/{incident_id}/narratives")
def list_narratives(
    incident_id: str,
    task_id: int = 0,
    search: str = "",
    critical_only: bool = False,
    team: str = "",
) -> list[dict[str, Any]]:
    repo = _repo(incident_id)
    query: dict[str, Any] = {"narrative.0": {"$exists": True}}
    if task_id:
        query["int_id"] = task_id
    tasks = repo.find_many(query, sort=[("int_id", 1)])
    results = []
    needle = search.lower()
    for task in tasks:
        task_int_id = int(task.get("int_id") or 0)
        for entry in task.get("narrative") or []:
            doc = _normalize_entry(entry, task_int_id)
            if critical_only and not int(doc.get("critical") or 0):
                continue
            if team and str(doc.get("team_num") or "") != str(team):
                continue
            if needle and needle not in doc["narrative"].lower() and needle not in str(doc.get("entered_by", "")).lower():
                continue
            results.append(doc)
    results.sort(key=lambda d: str(d.get("timestamp") or ""), reverse=True)
    return results


@router.post("/incidents/{incident_id}/narratives", status_code=201)
def create_narrative(incident_id: str, body: NarrativeCreate) -> dict[str, Any]:
    repo = _repo(incident_id)
    task = repo.find_one(_task_query(body.task_id))
    if not task:
        raise HTTPException(404, f"Task {body.task_id} not found")
    doc = {
        "id": _new_entry_id(),
        "task_id": body.task_id,
        "timestamp": body.timestamp,
        "narrative": body.narrative,
        "entered_by": body.entered_by,
        "team_num": body.team_num,
        "critical": 1 if body.critical else 0,
    }
    repo.apply_update(task["_id"], {"$push": {"narrative": doc}})
    return doc


@router.patch("/incidents/{incident_id}/narratives/{entry_id}")
def update_narrative(
    incident_id: str, entry_id: str, body: NarrativeUpdate
) -> dict[str, Any]:
    repo = _repo(incident_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    task, idx, _entry = _find_entry(repo, entry_id)
    normalized_updates: dict[str, Any] = {}
    for key, value in updates.items():
        normalized_updates[f"narrative.{idx}.{key}"] = (1 if value else 0) if key == "critical" else value
    repo.apply_update(task["_id"], {"$set": normalized_updates})
    updated = repo.find_by_id(task["_id"])
    if not updated:
        raise HTTPException(404, f"Narrative entry '{entry_id}' not found")
    return _normalize_entry((updated.get("narrative") or [])[idx], int(updated.get("int_id") or 0))


@router.delete("/incidents/{incident_id}/narratives/{entry_id}", status_code=204)
def delete_narrative(incident_id: str, entry_id: str) -> None:
    repo = _repo(incident_id)
    task, _idx, entry = _find_entry(repo, entry_id)
    pull_key = "entry_id" if any(
        str(row.get("entry_id") or "") == str(entry["id"])
        for row in task.get("narrative") or []
    ) else "id"
    repo.apply_update(task["_id"], {"$pull": {"narrative": {pull_key: entry_id}}})
