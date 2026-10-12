"""FastAPI router for the Liaison Reporting Board.

Ops/Planning push a resolution note (from a Task or Objective, or standalone)
onto the board; the LOFR then curates a customer-facing version before
flagging it Ready to Report. Nothing here writes back to Objectives/Tasks —
this is a one-way, LOFR-owned queue of what's safe to share externally.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LiaisonReportingDigestsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_REPORTING_DIGESTS
    soft_deletes = False


class ObjectivesRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_OBJECTIVES


class TasksRepository(BaseRepository):
    collection_name = IncidentCollections.TASKS


def _digests(incident_id: str) -> LiaisonReportingDigestsRepository:
    return LiaisonReportingDigestsRepository(get_incident_db(incident_id))


def _objectives(incident_id: str) -> ObjectivesRepository:
    return ObjectivesRepository(get_incident_db(incident_id))


def _tasks(incident_id: str) -> TasksRepository:
    return TasksRepository(get_incident_db(incident_id))


def _next_int_id(repo: BaseRepository) -> int:
    col = repo._col
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (max_doc["int_id"] if max_doc else 0) + 1


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _source_title(incident_id: str, source_type: str | None, source_id: str | None) -> str:
    """Best-effort label for the originating Task/Objective, for display only."""
    if not source_type or not source_id:
        return ""
    if source_type == "objective":
        doc = _objectives(incident_id).find_by_id(source_id)
        if not doc:
            return f"Objective {source_id}"
        return doc.get("text") or doc.get("code") or f"Objective {source_id}"
    if source_type == "task":
        try:
            task_int_id = int(source_id)
        except (TypeError, ValueError):
            return f"Task {source_id}"
        doc = _tasks(incident_id).find_one({"int_id": task_int_id})
        if not doc:
            return f"Task {source_id}"
        return doc.get("title") or doc.get("task_id") or f"Task {source_id}"
    return ""


@router.get("/incidents/{incident_id}/liaison/reporting-digests")
def list_digests(incident_id: str) -> list[dict]:
    repo = _digests(incident_id)
    return [_strip(d) for d in repo.find_many({}, sort=[("updated_at", -1)])]


@router.post("/incidents/{incident_id}/liaison/reporting-digests", status_code=201)
def create_digest(incident_id: str, body: dict[str, Any]) -> dict:
    source_type = body.get("source_type") or None
    source_id = str(body["source_id"]) if body.get("source_id") else None
    raw_note = str(body.get("raw_note") or "").strip()
    if not raw_note:
        raise HTTPException(400, "raw_note is required")
    if source_type and source_type not in ("objective", "task"):
        raise HTTPException(400, "source_type must be 'objective' or 'task'")
    title = _source_title(incident_id, source_type, source_id)
    repo = _digests(incident_id)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {
        "incident_id": incident_id,
        "int_id": int_id,
        "source_type": source_type,
        "source_id": source_id,
        "source_title": title,
        "raw_note": raw_note,
        "submitted_by": body.get("submitted_by") or "",
        "lofr_summary": "",
        "ready_to_report": False,
        "updated_by": body.get("submitted_by"),
        "updated_at": ts,
        "created_at": ts,
    }
    doc = repo.insert_one(doc)
    return _strip(doc)


@router.patch("/incidents/{incident_id}/liaison/reporting-digests/{digest_id}")
def update_digest(incident_id: str, digest_id: int, body: dict[str, Any]) -> dict:
    repo = _digests(incident_id)
    doc = repo.find_one({"int_id": digest_id})
    if not doc:
        raise HTTPException(404, "Digest not found")
    updates: dict[str, Any] = {"updated_at": _now()}
    for field in ("lofr_summary", "ready_to_report", "updated_by"):
        if field in body:
            updates[field] = body[field]
    repo.update_one(doc["_id"], updates)
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


@router.delete("/incidents/{incident_id}/liaison/reporting-digests/{digest_id}", status_code=204)
def delete_digest(incident_id: str, digest_id: int) -> None:
    repo = _digests(incident_id)
    doc = repo.find_one({"int_id": digest_id})
    if not doc:
        raise HTTPException(404, "Digest not found")
    repo.delete_one(doc["_id"])
