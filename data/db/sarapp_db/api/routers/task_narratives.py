"""FastAPI router — task narrative entries for incident tasks."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class NarrativeRepository(BaseRepository):
    collection_name = IncidentCollections.TASK_NARRATIVES
    soft_deletes = False


def _repo(incident_id: str) -> NarrativeRepository:
    return NarrativeRepository(get_incident_db(incident_id))


def _strip(doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id", ""))
    doc.pop("updated_at", None)
    doc.pop("created_at", None)
    return doc


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
    query: dict[str, Any] = {}
    if task_id:
        query["task_id"] = task_id
    if critical_only:
        query["critical"] = 1
    if team:
        query["team_num"] = team
    docs = repo.find_many(query, sort=[("timestamp", -1)])
    results = []
    for doc in docs:
        if search:
            needle = search.lower()
            if needle not in doc.get("narrative", "").lower() and needle not in str(doc.get("entered_by", "")).lower():
                continue
        results.append(_strip(doc))
    return results


@router.post("/incidents/{incident_id}/narratives", status_code=201)
def create_narrative(incident_id: str, body: NarrativeCreate) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = {
        "task_id": body.task_id,
        "timestamp": body.timestamp,
        "narrative": body.narrative,
        "entered_by": body.entered_by,
        "team_num": body.team_num,
        "critical": body.critical,
    }
    inserted = repo.insert_one(doc)
    return _strip(inserted)


@router.patch("/incidents/{incident_id}/narratives/{entry_id}")
def update_narrative(
    incident_id: str, entry_id: str, body: NarrativeUpdate
) -> dict[str, Any]:
    repo = _repo(incident_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    if not repo.update_one(entry_id, updates):
        raise HTTPException(404, f"Narrative entry '{entry_id}' not found")
    doc = repo.find_one({"_id": entry_id})
    return _strip(doc)


@router.delete("/incidents/{incident_id}/narratives/{entry_id}", status_code=204)
def delete_narrative(incident_id: str, entry_id: str) -> None:
    repo = _repo(incident_id)
    if not repo.delete_one(entry_id):
        raise HTTPException(404, f"Narrative entry '{entry_id}' not found")
