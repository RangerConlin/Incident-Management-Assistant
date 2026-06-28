"""Operational Periods router — per-incident."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.db_manager import DatabaseManager
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.int_id import _ensure_int_ids, next_int_id

router = APIRouter()

COL = IncidentCollections.OPERATIONAL_PERIODS
STATUSES = ("Planned", "Active", "Complete", "Canceled")


def _col(incident_id: str):
    return DatabaseManager().get_incident_db(incident_id)[COL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_dt(value: Any):
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _doc_to_record(doc: dict) -> dict:
    return {
        "id": doc.get("int_id"),
        "incident_id": doc.get("incident_id", ""),
        "number": doc.get("number", 1),
        "name": doc.get("name", ""),
        "status": doc.get("status", "Planned"),
        "start_time": doc.get("start_time", ""),
        "end_time": doc.get("end_time", ""),
        "briefing_time": doc.get("briefing_time", ""),
        "debrief_time": doc.get("debrief_time", ""),
        "objectives": doc.get("objectives", ""),
        "weather_summary": doc.get("weather_summary", ""),
        "safety_message": doc.get("safety_message", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


def _validate_no_overlap(col, incident_id: str, start_time: str, end_time: str, exclude_id: Optional[int] = None) -> None:
    start_dt = _parse_dt(start_time)
    end_dt = _parse_dt(end_time)
    if start_dt is None or end_dt is None:
        raise HTTPException(status_code=422, detail="Start and end times are required.")
    if end_dt <= start_dt:
        raise HTTPException(status_code=422, detail="End time must be after start time.")
    _ensure_int_ids(col)
    for doc in col.find({"incident_id": incident_id, "deleted": {"$ne": True}}):
        if exclude_id is not None and doc.get("int_id") == exclude_id:
            continue
        other_start = _parse_dt(doc.get("start_time"))
        other_end = _parse_dt(doc.get("end_time"))
        if other_start is None or other_end is None:
            continue
        if start_dt < other_end and end_dt > other_start:
            raise HTTPException(
                status_code=409,
                detail=f"Overlaps OP {doc.get('number')} ({doc.get('start_time')} to {doc.get('end_time')}).",
            )


@router.get("/incidents/{incident_id}/planning/operational-periods")
def list_periods(incident_id: str) -> List[Dict[str, Any]]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id, "deleted": {"$ne": True}}, sort=[("number", 1)]))
    return [_doc_to_record(d) for d in docs]


@router.post("/incidents/{incident_id}/planning/operational-periods", status_code=201)
def create_period(incident_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    start_time = str(body.get("start_time") or "").strip()
    end_time = str(body.get("end_time") or "").strip()
    _validate_no_overlap(col, incident_id, start_time, end_time)
    # Determine next number
    docs = list(col.find({"incident_id": incident_id, "deleted": {"$ne": True}}))
    numbers = [d.get("number", 0) for d in docs]
    number = int(body.get("number") or ((max(numbers) + 1) if numbers else 1))
    status = str(body.get("status") or "Planned").strip().title()
    if status not in STATUSES:
        status = "Planned"
    now = _utcnow()
    new_id = next_int_id(col)
    import uuid
    doc = {
        "_id": str(uuid.uuid4()),
        "int_id": new_id,
        "incident_id": incident_id,
        "number": number,
        "name": str(body.get("name") or "").strip(),
        "status": status,
        "start_time": start_time,
        "end_time": end_time,
        "briefing_time": str(body.get("briefing_time") or "").strip(),
        "debrief_time": str(body.get("debrief_time") or "").strip(),
        "objectives": str(body.get("objectives") or "").strip(),
        "weather_summary": str(body.get("weather_summary") or "").strip(),
        "safety_message": str(body.get("safety_message") or "").strip(),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _doc_to_record(doc)


@router.get("/incidents/{incident_id}/planning/operational-periods/active")
def get_active_period(incident_id: str) -> Optional[Dict[str, Any]]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one(
        {"incident_id": incident_id, "status": "Active", "deleted": {"$ne": True}},
        sort=[("updated_at", -1)],
    )
    return _doc_to_record(doc) if doc else None


@router.get("/incidents/{incident_id}/planning/operational-periods/{period_id}")
def get_period(incident_id: str, period_id: int) -> Dict[str, Any]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": period_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Operational period not found")
    return _doc_to_record(doc)


@router.patch("/incidents/{incident_id}/planning/operational-periods/{period_id}")
def update_period(incident_id: str, period_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": period_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Operational period not found")
    start_time = str(body.get("start_time") or doc.get("start_time") or "").strip()
    end_time = str(body.get("end_time") or doc.get("end_time") or "").strip()
    if "start_time" in body or "end_time" in body:
        _validate_no_overlap(col, incident_id, start_time, end_time, exclude_id=period_id)
    upd: Dict[str, Any] = {"updated_at": _utcnow()}
    for field in ("name", "briefing_time", "debrief_time", "objectives", "weather_summary", "safety_message"):
        if field in body:
            upd[field] = str(body[field] or "").strip()
    if "start_time" in body:
        upd["start_time"] = start_time
    if "end_time" in body:
        upd["end_time"] = end_time
    if "number" in body:
        upd["number"] = int(body["number"])
    if "status" in body:
        s = str(body["status"]).strip().title()
        upd["status"] = s if s in STATUSES else doc.get("status", "Planned")
    col.update_one({"int_id": period_id, "incident_id": incident_id}, {"$set": upd})
    return get_period(incident_id, period_id)


@router.post("/incidents/{incident_id}/planning/operational-periods/{period_id}/set-active")
def set_active_period(incident_id: str, period_id: int) -> Dict[str, Any]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": period_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Operational period not found")
    now = _utcnow()
    col.update_many(
        {"incident_id": incident_id, "status": "Active", "int_id": {"$ne": period_id}},
        {"$set": {"status": "Planned", "updated_at": now}},
    )
    col.update_one({"incident_id": incident_id, "int_id": period_id}, {"$set": {"status": "Active", "updated_at": now}})
    return get_period(incident_id, period_id)


@router.post("/incidents/{incident_id}/planning/operational-periods/{period_id}/clone", status_code=201)
def clone_period(incident_id: str, period_id: int) -> Dict[str, Any]:
    from datetime import timedelta
    col = _col(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": period_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Operational period not found")
    start_dt = _parse_dt(doc.get("start_time")) or datetime.now(timezone.utc)
    end_dt = _parse_dt(doc.get("end_time")) or (start_dt + timedelta(hours=12))
    duration = end_dt - start_dt
    docs = sorted(
        [d for d in col.find({"incident_id": incident_id, "deleted": {"$ne": True}})],
        key=lambda x: x.get("number", 0),
    )
    last = docs[-1] if docs else doc
    last_end = _parse_dt(last.get("end_time")) or end_dt
    next_start = last_end.replace(microsecond=0)
    next_end = next_start + duration
    numbers = [d.get("number", 0) for d in docs]
    next_number = (max(numbers) + 1) if numbers else 1
    return create_period(incident_id, {
        "number": next_number,
        "name": doc.get("name", ""),
        "status": "Planned",
        "start_time": next_start.isoformat(timespec="seconds"),
        "end_time": next_end.isoformat(timespec="seconds"),
        "briefing_time": doc.get("briefing_time", ""),
        "debrief_time": doc.get("debrief_time", ""),
        "objectives": doc.get("objectives", ""),
        "weather_summary": doc.get("weather_summary", ""),
        "safety_message": doc.get("safety_message", ""),
    })
