"""Intel router (MongoDB-backed): clues, subjects, env snapshots, reports, form entries."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _ensure_int_ids(col) -> None:
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _next_int_id(col) -> int:
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


def _col(incident_id: str, name: str):
    return get_incident_db(incident_id)[name]


# ===========================================================================
# CLUES
# ===========================================================================

def _map_clue(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "type": doc.get("type", ""),
        "score": doc.get("score", 0),
        "at_time": doc.get("at_time", ""),
        "location_text": doc.get("location_text", ""),
        "geom": doc.get("geom"),
        "entered_by": doc.get("entered_by", ""),
        "team_text": doc.get("team_text"),
        "description": doc.get("description"),
        "attachments_json": doc.get("attachments_json"),
        "linked_subject_id": doc.get("linked_subject_id"),
        "linked_task_id": doc.get("linked_task_id"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


class ClueCreate(BaseModel):
    type: str
    score: int = 0
    at_time: str
    location_text: str
    entered_by: str
    geom: Optional[str] = None
    team_text: Optional[str] = None
    description: Optional[str] = None
    attachments_json: Optional[str] = None
    linked_subject_id: Optional[int] = None
    linked_task_id: Optional[int] = None


class ClueUpdate(ClueCreate):
    pass


@router.get("/incidents/{incident_id}/intel/clues")
def list_clues(incident_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_CLUES)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("created_at", -1))
    return [_map_clue(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/clues", status_code=201)
def add_clue(incident_id: str, data: ClueCreate):
    col = _col(incident_id, IncidentCollections.INTEL_CLUES)
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    now = _utcnow()
    doc = {"_id": _new_id(), "int_id": int_id, "incident_id": incident_id, **data.model_dump(), "created_at": now, "updated_at": now}
    col.insert_one(doc)
    return _map_clue(col.find_one({"int_id": int_id}))


@router.get("/incidents/{incident_id}/intel/clues/{clue_id}")
def get_clue(incident_id: str, clue_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_CLUES)
    doc = col.find_one({"int_id": clue_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Clue not found")
    return _map_clue(doc)


@router.put("/incidents/{incident_id}/intel/clues/{clue_id}")
def update_clue(incident_id: str, clue_id: int, data: ClueUpdate):
    col = _col(incident_id, IncidentCollections.INTEL_CLUES)
    updates = {**data.model_dump(), "updated_at": _utcnow()}
    result = col.find_one_and_update(
        {"int_id": clue_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Clue not found")
    return _map_clue(result)


@router.delete("/incidents/{incident_id}/intel/clues/{clue_id}", status_code=204)
def delete_clue(incident_id: str, clue_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_CLUES)
    result = col.delete_one({"int_id": clue_id, "incident_id": incident_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Clue not found")


# ===========================================================================
# SUBJECTS
# ===========================================================================

def _map_subject(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "name": doc.get("name", ""),
        "sex": doc.get("sex"),
        "dob": doc.get("dob"),
        "race": doc.get("race"),
        "photo": doc.get("photo"),
        "lkp_time": doc.get("lkp_time"),
        "lkp_place": doc.get("lkp_place"),
    }


class SubjectCreate(BaseModel):
    name: str
    sex: Optional[str] = None
    dob: Optional[str] = None
    race: Optional[str] = None
    photo: Optional[str] = None
    lkp_time: Optional[str] = None
    lkp_place: Optional[str] = None


@router.get("/incidents/{incident_id}/intel/subjects")
def list_subjects(incident_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("name", 1))
    return [_map_subject(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/subjects", status_code=201)
def add_subject(incident_id: str, data: SubjectCreate):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    doc = {"_id": _new_id(), "int_id": int_id, "incident_id": incident_id, **data.model_dump()}
    col.insert_one(doc)
    return _map_subject(col.find_one({"int_id": int_id}))


@router.get("/incidents/{incident_id}/intel/subjects/{subject_id}")
def get_subject(incident_id: str, subject_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    doc = col.find_one({"int_id": subject_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Subject not found")
    return _map_subject(doc)


@router.put("/incidents/{incident_id}/intel/subjects/{subject_id}")
def update_subject(incident_id: str, subject_id: int, data: SubjectCreate):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    result = col.find_one_and_update(
        {"int_id": subject_id, "incident_id": incident_id},
        {"$set": data.model_dump()},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Subject not found")
    return _map_subject(result)


@router.delete("/incidents/{incident_id}/intel/subjects/{subject_id}", status_code=204)
def delete_subject(incident_id: str, subject_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    result = col.delete_one({"int_id": subject_id, "incident_id": incident_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subject not found")


# ===========================================================================
# ENV SNAPSHOTS
# ===========================================================================

def _map_env(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "op_period": doc.get("op_period"),
        "weather_json": doc.get("weather_json"),
        "hazards_json": doc.get("hazards_json"),
        "terrain_json": doc.get("terrain_json"),
        "notes": doc.get("notes"),
    }


class EnvSnapshotCreate(BaseModel):
    op_period: int
    weather_json: Optional[str] = None
    hazards_json: Optional[str] = None
    terrain_json: Optional[str] = None
    notes: Optional[str] = None


@router.get("/incidents/{incident_id}/intel/env-snapshots")
def list_env_snapshots(incident_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_ENV_SNAPSHOTS)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("op_period", 1))
    return [_map_env(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/env-snapshots", status_code=201)
def add_env_snapshot(incident_id: str, data: EnvSnapshotCreate):
    col = _col(incident_id, IncidentCollections.INTEL_ENV_SNAPSHOTS)
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    doc = {"_id": _new_id(), "int_id": int_id, "incident_id": incident_id, **data.model_dump()}
    col.insert_one(doc)
    return _map_env(col.find_one({"int_id": int_id}))


@router.get("/incidents/{incident_id}/intel/env-snapshots/{snapshot_id}")
def get_env_snapshot(incident_id: str, snapshot_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_ENV_SNAPSHOTS)
    doc = col.find_one({"int_id": snapshot_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Env snapshot not found")
    return _map_env(doc)


@router.put("/incidents/{incident_id}/intel/env-snapshots/{snapshot_id}")
def update_env_snapshot(incident_id: str, snapshot_id: int, data: EnvSnapshotCreate):
    col = _col(incident_id, IncidentCollections.INTEL_ENV_SNAPSHOTS)
    result = col.find_one_and_update(
        {"int_id": snapshot_id, "incident_id": incident_id},
        {"$set": data.model_dump()},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Env snapshot not found")
    return _map_env(result)


@router.delete("/incidents/{incident_id}/intel/env-snapshots/{snapshot_id}", status_code=204)
def delete_env_snapshot(incident_id: str, snapshot_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_ENV_SNAPSHOTS)
    result = col.delete_one({"int_id": snapshot_id, "incident_id": incident_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Env snapshot not found")


# ===========================================================================
# INTEL REPORTS
# ===========================================================================

def _map_report(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "title": doc.get("title", ""),
        "body_md": doc.get("body_md", ""),
        "linked_subject_id": doc.get("linked_subject_id"),
        "linked_task_id": doc.get("linked_task_id"),
        "created_at": doc.get("created_at", ""),
    }


class IntelReportCreate(BaseModel):
    title: str
    body_md: str
    linked_subject_id: Optional[int] = None
    linked_task_id: Optional[int] = None


@router.get("/incidents/{incident_id}/intel/reports")
def list_reports(incident_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_REPORTS)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("created_at", -1))
    return [_map_report(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/reports", status_code=201)
def add_report(incident_id: str, data: IntelReportCreate):
    col = _col(incident_id, IncidentCollections.INTEL_REPORTS)
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    now = _utcnow()
    doc = {"_id": _new_id(), "int_id": int_id, "incident_id": incident_id, **data.model_dump(), "created_at": now}
    col.insert_one(doc)
    return _map_report(col.find_one({"int_id": int_id}))


@router.get("/incidents/{incident_id}/intel/reports/{report_id}")
def get_report(incident_id: str, report_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_REPORTS)
    doc = col.find_one({"int_id": report_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return _map_report(doc)


@router.put("/incidents/{incident_id}/intel/reports/{report_id}")
def update_report(incident_id: str, report_id: int, data: IntelReportCreate):
    col = _col(incident_id, IncidentCollections.INTEL_REPORTS)
    result = col.find_one_and_update(
        {"int_id": report_id, "incident_id": incident_id},
        {"$set": data.model_dump()},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return _map_report(result)


# ===========================================================================
# FORM ENTRIES
# ===========================================================================

def _map_form_entry(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("int_id"),
        "form_name": doc.get("form_name", ""),
        "data_json": doc.get("data_json", ""),
    }


class FormEntryCreate(BaseModel):
    form_name: str
    data_json: str


@router.get("/incidents/{incident_id}/intel/form-entries")
def list_form_entries(incident_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_FORM_ENTRIES)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id}).sort("form_name", 1))
    return [_map_form_entry(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/form-entries", status_code=201)
def add_form_entry(incident_id: str, data: FormEntryCreate):
    col = _col(incident_id, IncidentCollections.INTEL_FORM_ENTRIES)
    _ensure_int_ids(col)
    int_id = _next_int_id(col)
    doc = {"_id": _new_id(), "int_id": int_id, "incident_id": incident_id, **data.model_dump()}
    col.insert_one(doc)
    return _map_form_entry(col.find_one({"int_id": int_id}))


@router.get("/incidents/{incident_id}/intel/form-entries/{entry_id}")
def get_form_entry(incident_id: str, entry_id: int):
    col = _col(incident_id, IncidentCollections.INTEL_FORM_ENTRIES)
    doc = col.find_one({"int_id": entry_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Form entry not found")
    return _map_form_entry(doc)
