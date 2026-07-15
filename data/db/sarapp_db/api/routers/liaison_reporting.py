"""FastAPI router for the Liaison Reporting Board.

Lets the LOFR pull a shareable digest from an Objective or Task (auto-summary),
then curate a customer-facing version before flagging it Ready to Report.
Nothing here writes back to Objectives/Tasks — this is a one-way, LOFR-owned
snapshot of what's safe to share externally.
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


def _pull_auto_summary(incident_id: str, source_type: str, source_id: str) -> tuple[str, str]:
    """Return (title, auto_summary) pulled from the live Objective/Task record."""
    if source_type == "objective":
        doc = _objectives(incident_id).find_by_id(source_id)
        if not doc:
            raise HTTPException(404, f"Objective {source_id} not found")
        title = doc.get("text") or doc.get("code") or f"Objective {source_id}"
        status = doc.get("status") or "unknown"
        narrative = doc.get("narrative") or ""
        summary = f"Status: {status}."
        if narrative:
            summary += f" {narrative}"
        return title, summary
    if source_type == "task":
        try:
            task_int_id = int(source_id)
        except (TypeError, ValueError):
            raise HTTPException(400, "task source_id must be an integer")
        doc = _tasks(incident_id).find_one({"int_id": task_int_id})
        if not doc:
            raise HTTPException(404, f"Task {source_id} not found")
        title = doc.get("title") or doc.get("task_id") or f"Task {source_id}"
        status = doc.get("status") or "unknown"
        entries = doc.get("narrative") or []
        latest = ""
        if entries:
            latest_entry = sorted(entries, key=lambda e: str(e.get("timestamp") or ""))[-1]
            latest = latest_entry.get("narrative") or ""
        summary = f"Status: {status}."
        if latest:
            summary += f" Latest: {latest}"
        return title, summary
    raise HTTPException(400, "source_type must be 'objective' or 'task'")


@router.get("/incidents/{incident_id}/liaison/reporting-digests")
def list_digests(incident_id: str) -> list[dict]:
    repo = _digests(incident_id)
    return [_strip(d) for d in repo.find_many({}, sort=[("updated_at", -1)])]


@router.post("/incidents/{incident_id}/liaison/reporting-digests", status_code=201)
def create_digest(incident_id: str, body: dict[str, Any]) -> dict:
    source_type = body.get("source_type")
    source_id = body.get("source_id")
    if not source_type or not source_id:
        raise HTTPException(400, "source_type and source_id required")
    title, auto_summary = _pull_auto_summary(incident_id, source_type, str(source_id))
    repo = _digests(incident_id)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {
        "incident_id": incident_id,
        "int_id": int_id,
        "source_type": source_type,
        "source_id": str(source_id),
        "source_title": title,
        "auto_summary": auto_summary,
        "lofr_summary": auto_summary,
        "ready_to_report": False,
        "last_synced_at": ts,
        "updated_by": body.get("updated_by"),
        "updated_at": ts,
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


@router.post("/incidents/{incident_id}/liaison/reporting-digests/{digest_id}/resync")
def resync_digest(incident_id: str, digest_id: int) -> dict:
    """Re-pull the auto_summary from the live source without touching lofr_summary."""
    repo = _digests(incident_id)
    doc = repo.find_one({"int_id": digest_id})
    if not doc:
        raise HTTPException(404, "Digest not found")
    title, auto_summary = _pull_auto_summary(incident_id, doc["source_type"], doc["source_id"])
    repo.update_one(doc["_id"], {
        "source_title": title,
        "auto_summary": auto_summary,
        "last_synced_at": _now(),
        "updated_at": _now(),
    })
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


@router.delete("/incidents/{incident_id}/liaison/reporting-digests/{digest_id}", status_code=204)
def delete_digest(incident_id: str, digest_id: int) -> None:
    repo = _digests(incident_id)
    doc = repo.find_one({"int_id": digest_id})
    if not doc:
        raise HTTPException(404, "Digest not found")
    repo.delete_one(doc["_id"])
