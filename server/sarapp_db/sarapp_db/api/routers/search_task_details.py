"""Search Assignment / Task Planner router (SAR Toolkit) — MongoDB-backed.

Per docs/archive/design-documents/toolkit_sar_playbook.md's explicit
ownership rule, "Operations owns the official task/assignment record and
deployment lifecycle." This collection does NOT duplicate that record. It
holds only the SAR-specific fields a search task needs on top of a general
Operations task (segment_id, search_method, track_spacing, completion
criteria, safety notes, ...), keyed by `task_id` = the int_id of the
existing Operations task (IncidentCollections.TASKS, see
server/sarapp_db/sarapp_db/api/routers/operations.py). Publishing a search
task from the desktop planner creates the real task through the Operations
API first, then creates/updates the linked record here referencing that
task's id. See the module docstring on the desktop panel
(apps/desktop/sarapp_desktop/modules/sartoolkit/panels/search_task_planner_panel.py)
for the decision writeup.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

SEARCH_METHODS = ["Parallel", "Grid", "Hasty", "Air-scent", "Sector", "Line"]


class SearchTaskDetailsRepository(BaseRepository):
    collection_name = IncidentCollections.SEARCH_TASK_DETAILS


def _repo(incident_id: str) -> SearchTaskDetailsRepository:
    return SearchTaskDetailsRepository(get_incident_db(incident_id))


class SearchTaskDetailPayload(BaseModel):
    task_id: int
    segment_id: Optional[str] = None
    search_method: str = "Parallel"
    track_spacing: str = ""
    completion_criteria: str = ""
    safety_notes: str = ""
    radio_channel: str = ""
    team_leader: str = ""
    departure_time: Optional[str] = None
    due_back_time: Optional[str] = None


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id") or ""),
        "incident_id": str(doc.get("incident_id") or ""),
        "task_id": doc.get("task_id"),
        "segment_id": doc.get("segment_id"),
        "search_method": str(doc.get("search_method") or "Parallel"),
        "track_spacing": str(doc.get("track_spacing") or ""),
        "completion_criteria": str(doc.get("completion_criteria") or ""),
        "safety_notes": str(doc.get("safety_notes") or ""),
        "radio_channel": str(doc.get("radio_channel") or ""),
        "team_leader": str(doc.get("team_leader") or ""),
        "departure_time": doc.get("departure_time"),
        "due_back_time": doc.get("due_back_time"),
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
    }


@router.get("/incidents/{incident_id}/search-task-details")
def list_search_task_details(incident_id: str) -> List[Dict[str, Any]]:
    repo = _repo(incident_id)
    rows = repo.find_many({"incident_id": incident_id})
    return [_serialize(r) for r in rows]


@router.get("/incidents/{incident_id}/search-task-details/by-task/{task_id}")
def get_search_task_detail_by_task(incident_id: str, task_id: int) -> Dict[str, Any]:
    repo = _repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "task_id": task_id})
    if not doc:
        raise HTTPException(status_code=404, detail="No search task detail for that task")
    return _serialize(doc)


@router.post("/incidents/{incident_id}/search-task-details", status_code=201)
def create_search_task_detail(incident_id: str, payload: SearchTaskDetailPayload) -> Dict[str, Any]:
    if payload.search_method not in SEARCH_METHODS:
        raise HTTPException(status_code=422, detail=f"Invalid search_method: {payload.search_method}")
    repo = _repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id, "task_id": payload.task_id})
    if existing is not None:
        raise HTTPException(status_code=409, detail="A search task detail already exists for that task_id")
    doc = repo.insert_one({"incident_id": incident_id, **payload.model_dump()})
    return _serialize(doc)


@router.put("/incidents/{incident_id}/search-task-details/{detail_id}")
def update_search_task_detail(incident_id: str, detail_id: str, payload: SearchTaskDetailPayload) -> Dict[str, Any]:
    if payload.search_method not in SEARCH_METHODS:
        raise HTTPException(status_code=422, detail=f"Invalid search_method: {payload.search_method}")
    repo = _repo(incident_id)
    existing = repo.find_by_id(detail_id)
    if not existing or str(existing.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Search task detail not found")
    repo.update_one(detail_id, {"incident_id": incident_id, **payload.model_dump()})
    updated = repo.find_by_id(detail_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Search task detail not found after update")
    return _serialize(updated)


@router.delete("/incidents/{incident_id}/search-task-details/{detail_id}")
def delete_search_task_detail(incident_id: str, detail_id: str) -> Dict[str, bool]:
    repo = _repo(incident_id)
    existing = repo.find_by_id(detail_id)
    if not existing or str(existing.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Search task detail not found")
    return {"ok": repo.soft_delete(detail_id)}
