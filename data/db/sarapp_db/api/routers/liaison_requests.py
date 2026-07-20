"""FastAPI router for the Liaison Agency Requests board.

Every outside-agency ask or offer is a "Request" — the top-level grouping
unit (e.g. "AFRCC-1: find the aircraft", "OEM-2: help with POD setup").
Each Request can link to zero or more Objectives/Tasks and carries its own
LOFR-owned narrative thread (Feedback is one of that thread's entry
categories, not a separate top-level record). This is additive: it does not
replace the existing agency-requests/resource-offers/feedback/interactions
endpoints in liaison.py, which remain in place until the UI that depends on
them is retired.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

REQUEST_TYPES = ("Request", "Offer")
STATUSES = ("Open", "In Progress", "Resolved", "Declined", "Cancelled")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LiaisonRequestsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_REQUESTS
    soft_deletes = False


class LiaisonAgenciesRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_AGENCIES
    soft_deletes = False


def _requests(incident_id: str) -> LiaisonRequestsRepository:
    return LiaisonRequestsRepository(get_incident_db(incident_id))


def _agencies(incident_id: str) -> LiaisonAgenciesRepository:
    return LiaisonAgenciesRepository(get_incident_db(incident_id))


def _next_int_id(repo: BaseRepository) -> int:
    col = repo._col
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (max_doc["int_id"] if max_doc else 0) + 1


def _agency_code_prefix(agency: dict) -> str:
    """The agency's request-numbering prefix (e.g. "AFRCC").

    This is always the Agency Code entered on the agency's own record in
    the Agency Directory — no derivation from the agency name. If it's
    missing, that's a data-entry gap on the agency record, not something
    to guess around here.
    """
    code = str(agency.get("code") or "").strip().upper()
    if not code:
        raise HTTPException(
            400,
            f"Agency {agency.get('name') or agency.get('int_id')} has no Agency Code set. "
            "Add one in the Agency Directory before creating requests for it.",
        )
    return code


def _next_request_code(repo: BaseRepository, agency_id: int, prefix: str) -> str:
    """Next sequential code for this agency, e.g. "AFRCC-3"."""
    col = repo._col
    max_seq = 0
    for doc in col.find({"agency_id": agency_id}, {"code": 1}):
        code = str(doc.get("code") or "")
        if "-" in code:
            suffix = code.rsplit("-", 1)[-1]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
    return f"{prefix}-{max_seq + 1}"


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("/incidents/{incident_id}/liaison/requests")
def list_requests(incident_id: str) -> list[dict]:
    repo = _requests(incident_id)
    return [_strip(d) for d in repo.find_many({}, sort=[("updated_at", -1)])]


@router.post("/incidents/{incident_id}/liaison/requests", status_code=201)
def create_request(incident_id: str, body: dict[str, Any]) -> dict:
    agency_id = body.get("agency_id")
    request_type = body.get("request_type")
    summary = str(body.get("summary") or "").strip()
    if agency_id is None:
        raise HTTPException(400, "agency_id required")
    if request_type not in REQUEST_TYPES:
        raise HTTPException(400, f"request_type must be one of {REQUEST_TYPES}")
    if not summary:
        raise HTTPException(400, "summary required")
    status = body.get("status") or "Open"
    if status not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    agency = _agencies(incident_id).find_one({"int_id": int(agency_id)})
    if not agency:
        raise HTTPException(404, f"Agency {agency_id} not found")
    repo = _requests(incident_id)
    prefix = _agency_code_prefix(agency)
    code = _next_request_code(repo, int(agency_id), prefix)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {
        "incident_id": incident_id,
        "int_id": int_id,
        "code": code,
        "agency_id": int(agency_id),
        "request_type": request_type,
        "summary": summary,
        "requested_by": body.get("requested_by") or "",
        "due_date": body.get("due_date") or "",
        "priority": body.get("priority") or "Medium",
        "status": status,
        "objective_ids": [str(o) for o in (body.get("objective_ids") or [])],
        "task_ids": [int(t) for t in (body.get("task_ids") or [])],
        "resource_request_ids": [str(r) for r in (body.get("resource_request_ids") or [])],
        "narrative": [],
        "created_by": body.get("created_by") or "",
        "created_at": ts,
        "updated_at": ts,
    }
    doc = repo.insert_one(doc)
    return _strip(doc)


@router.patch("/incidents/{incident_id}/liaison/requests/{request_id}")
def update_request(incident_id: str, request_id: int, body: dict[str, Any]) -> dict:
    repo = _requests(incident_id)
    doc = repo.find_one({"int_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")
    if "status" in body and body["status"] not in STATUSES:
        raise HTTPException(400, f"status must be one of {STATUSES}")
    updates: dict[str, Any] = {"updated_at": _now()}
    for field in ("summary", "priority", "status", "requested_by", "due_date"):
        if field in body:
            updates[field] = body[field]
    if "objective_ids" in body:
        updates["objective_ids"] = [str(o) for o in (body["objective_ids"] or [])]
    if "task_ids" in body:
        updates["task_ids"] = [int(t) for t in (body["task_ids"] or [])]
    if "resource_request_ids" in body:
        updates["resource_request_ids"] = [str(r) for r in (body["resource_request_ids"] or [])]
    repo.update_one(doc["_id"], updates)
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


@router.post("/incidents/{incident_id}/liaison/requests/{request_id}/narrative", status_code=201)
def add_narrative_entry(incident_id: str, request_id: int, body: dict[str, Any]) -> dict:
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    repo = _requests(incident_id)
    doc = repo.find_one({"int_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")
    entry = {
        "ts": _now(),
        "category": body.get("category") or "Update",
        "author": body.get("author") or "",
        "text": text,
    }
    narrative = list(doc.get("narrative") or [])
    narrative.append(entry)
    repo.update_one(doc["_id"], {"narrative": narrative, "updated_at": _now()})
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


@router.delete("/incidents/{incident_id}/liaison/requests/{request_id}", status_code=204)
def delete_request(incident_id: str, request_id: int) -> None:
    repo = _requests(incident_id)
    doc = repo.find_one({"int_id": request_id})
    if not doc:
        raise HTTPException(404, "Request not found")
    repo.delete_one(doc["_id"])
