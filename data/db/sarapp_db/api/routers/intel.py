"""
Intel Module API router — Module 7 All-Hazards Information Management.

Covers: subjects, leads, intel items (with embedded observations),
assessments, intel log, reports, and the dashboard summary endpoint.

Legacy clue/env-snapshot/form-entry endpoints are retained at the bottom
for backward compatibility until they are formally decommissioned.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _col(incident_id: str, name: str):
    return get_incident_db(incident_id)[name]


def _ensure_int_ids(col) -> None:
    """Lazy-migrate documents that are missing int_id (numeric surrogate key)."""
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


def _write_log(incident_id: str, entity_type: str, entity_id: str,
               event_type: str, summary: str, actor: str = "system") -> None:
    """Append a chronological entry to the intel activity log."""
    log_col = _col(incident_id, IncidentCollections.INTEL_LOG)
    log_col.insert_one({
        "_id": _new_id(),
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "event_type": event_type,
        "summary": summary,
        "actor": actor,
        "logged_at": _utcnow(),
    })


# ===========================================================================
# DASHBOARD
# ===========================================================================

@router.get("/incidents/{incident_id}/intel/dashboard")
def get_intel_dashboard(incident_id: str) -> Dict[str, Any]:
    """Return summary counts and recent activity for the Intel dashboard."""
    subjects_col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    leads_col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    items_col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    assessments_col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    log_col = _col(incident_id, IncidentCollections.INTEL_LOG)

    active_subjects = subjects_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "status": {"$nin": ["Archived", "Closed"]},
    })
    open_leads = leads_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "status": {"$nin": ["Closed", "Rejected", "Converted"]},
    })
    total_items = items_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "status": {"$nin": ["Archived"]},
    })
    critical_items = items_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "priority": "Critical", "status": {"$nin": ["Archived"]},
    })
    worsening_items = items_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "trend": "Worsening", "status": {"$nin": ["Archived"]},
    })
    improving_items = items_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "trend": "Improving", "status": {"$nin": ["Archived"]},
    })
    open_assessments = assessments_col.count_documents({
        "incident_id": incident_id, "deleted": False,
        "status": {"$nin": ["Archived"]},
    })
    # 20 most recent log entries for the Recent Activity feed
    recent = list(log_col.find(
        {"incident_id": incident_id},
        sort=[("logged_at", -1)],
        limit=20,
    ))

    # Critical items list for dashboard centre panel
    critical_docs = list(items_col.find(
        {"incident_id": incident_id, "deleted": False,
         "priority": "Critical", "status": {"$nin": ["Archived"]}},
        sort=[("updated_at", -1)],
        limit=8,
    ))

    # Open leads for dashboard snapshot panel (unresolved, priority order)
    lead_docs = list(leads_col.find(
        {"incident_id": incident_id, "deleted": False,
         "status": {"$nin": ["Closed", "Rejected", "Converted"]}},
        sort=[("updated_at", -1)],
        limit=8,
    ))

    return {
        "active_subjects": active_subjects,
        "open_leads": open_leads,
        "total_items": total_items,
        "critical_items": critical_items,
        "worsening_items": worsening_items,
        "improving_items": improving_items,
        "open_assessments": open_assessments,
        "recent_activity": [
            {
                "entity_type": e.get("entity_type"),
                "entity_id": e.get("entity_id"),
                "event_type": e.get("event_type"),
                "summary": e.get("summary"),
                "actor": e.get("actor"),
                "timestamp": e.get("logged_at"),
            }
            for e in recent
        ],
        "critical_item_list": [
            {
                "number": str(d.get("_id", ""))[-4:].upper(),
                "title": d.get("title", ""),
                "item_type": d.get("item_type", ""),
                "priority": d.get("priority", ""),
                "trend": d.get("trend", "Unknown"),
                "updated_at": d.get("updated_at", ""),
            }
            for d in critical_docs
        ],
        "open_lead_list": [
            {
                "title": d.get("title", ""),
                "priority": d.get("priority", ""),
                "status": d.get("status", ""),
                "assigned_to": d.get("assigned_to"),
                "source_type": d.get("source_type", ""),
                "updated_at": d.get("updated_at", ""),
            }
            for d in lead_docs
        ],
    }


# ===========================================================================
# SUBJECTS
# ===========================================================================

def _map_subject(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("_id"),
        "incident_id": doc.get("incident_id"),
        "subject_type": doc.get("subject_type", "Missing Person"),
        "status": doc.get("status", "Active"),
        # Core identity
        "name": doc.get("name", ""),
        "sex": doc.get("sex"),
        "dob": doc.get("dob"),
        "age": doc.get("age"),
        "race": doc.get("race"),
        "height": doc.get("height"),
        "weight": doc.get("weight"),
        "hair_color": doc.get("hair_color"),
        "eye_color": doc.get("eye_color"),
        "distinguishing_features": doc.get("distinguishing_features"),
        "photo_path": doc.get("photo_path"),
        # Missing person fields
        "lkp_time": doc.get("lkp_time"),
        "lkp_place": doc.get("lkp_place"),
        "pls_time": doc.get("pls_time"),
        "pls_place": doc.get("pls_place"),
        # Contact / reporting party fields
        "phone": doc.get("phone"),
        "email": doc.get("email"),
        "address": doc.get("address"),
        "organization": doc.get("organization"),
        # Medical
        "medical_conditions": doc.get("medical_conditions"),
        "medications": doc.get("medications"),
        "mobility_limitations": doc.get("mobility_limitations"),
        # Experience / behavior
        "outdoor_experience": doc.get("outdoor_experience"),
        "behavioral_notes": doc.get("behavioral_notes"),
        "equipment_description": doc.get("equipment_description"),
        "clothing_description": doc.get("clothing_description"),
        "vehicle_description": doc.get("vehicle_description"),
        # Witness / contact specifics
        "reliability": doc.get("reliability"),
        "initial_report": doc.get("initial_report"),
        # Links
        "linked_item_ids": doc.get("linked_item_ids", []),
        "linked_task_ids": doc.get("linked_task_ids", []),
        # Metadata
        "notes": doc.get("notes"),
        "created_by": doc.get("created_by", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "deleted": doc.get("deleted", False),
    }


class SubjectCreate(BaseModel):
    subject_type: str = "Missing Person"
    name: str
    status: str = "Active"
    sex: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    race: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    distinguishing_features: Optional[str] = None
    photo_path: Optional[str] = None
    lkp_time: Optional[str] = None
    lkp_place: Optional[str] = None
    pls_time: Optional[str] = None
    pls_place: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    organization: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    mobility_limitations: Optional[str] = None
    outdoor_experience: Optional[str] = None
    behavioral_notes: Optional[str] = None
    equipment_description: Optional[str] = None
    clothing_description: Optional[str] = None
    vehicle_description: Optional[str] = None
    reliability: Optional[str] = None
    initial_report: Optional[str] = None
    linked_item_ids: List[str] = Field(default_factory=list)
    linked_task_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: str = ""


class SubjectUpdate(SubjectCreate):
    pass


@router.get("/incidents/{incident_id}/intel/subjects")
def list_subjects(
    incident_id: str,
    subject_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if not include_deleted:
        q["deleted"] = False
    if subject_type:
        q["subject_type"] = subject_type
    if status:
        q["status"] = status
    docs = list(col.find(q).sort("updated_at", -1))
    return [_map_subject(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/subjects", status_code=201)
def create_subject(incident_id: str, data: SubjectCreate):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    now = _utcnow()
    doc = {
        "_id": _new_id(),
        "incident_id": incident_id,
        "deleted": False,
        "created_at": now,
        "updated_at": now,
        **data.model_dump(),
    }
    col.insert_one(doc)
    result = col.find_one({"_id": doc["_id"]})
    _write_log(incident_id, "subject", doc["_id"], "created",
               f"Subject created: {data.name} ({data.subject_type})", data.created_by or "system")
    return _map_subject(result)


@router.get("/incidents/{incident_id}/intel/subjects/{subject_id}")
def get_subject(incident_id: str, subject_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    doc = col.find_one({"_id": subject_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Subject not found")
    return _map_subject(doc)


@router.patch("/incidents/{incident_id}/intel/subjects/{subject_id}")
def update_subject(incident_id: str, subject_id: str, data: SubjectUpdate):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    updates = {**data.model_dump(exclude_unset=False), "updated_at": _utcnow()}
    result = col.find_one_and_update(
        {"_id": subject_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Subject not found")
    _write_log(incident_id, "subject", subject_id, "updated",
               f"Subject updated: {result.get('name')}", data.created_by or "system")
    return _map_subject(result)


@router.delete("/incidents/{incident_id}/intel/subjects/{subject_id}", status_code=204)
def archive_subject(incident_id: str, subject_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_SUBJECTS)
    result = col.find_one_and_update(
        {"_id": subject_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "updated_at": _utcnow()}},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Subject not found")
    _write_log(incident_id, "subject", subject_id, "archived",
               f"Subject archived: {result.get('name')}")


# ===========================================================================
# LEADS
# ===========================================================================

def _map_lead(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("_id"),
        "incident_id": doc.get("incident_id"),
        "lead_number": doc.get("lead_number"),
        "title": doc.get("title", ""),
        "summary": doc.get("summary", ""),
        "source_type": doc.get("source_type", ""),
        "reported_by": doc.get("reported_by", ""),
        "contact_info": doc.get("contact_info"),
        "location_text": doc.get("location_text"),
        "priority": doc.get("priority", "Medium"),
        "status": doc.get("status", "New"),
        "assigned_to": doc.get("assigned_to"),
        "assigned_team_id": doc.get("assigned_team_id"),
        "notes": doc.get("notes"),
        "converted_to_type": doc.get("converted_to_type"),
        "converted_to_id": doc.get("converted_to_id"),
        "created_by": doc.get("created_by", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "deleted": doc.get("deleted", False),
    }


def _next_lead_number(incident_id: str) -> int:
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    top = col.find_one(
        {"incident_id": incident_id, "lead_number": {"$exists": True}},
        sort=[("lead_number", -1)],
    )
    return (top["lead_number"] + 1) if top else 1


class LeadCreate(BaseModel):
    title: str
    summary: str = ""
    source_type: str = ""
    reported_by: str = ""
    contact_info: Optional[str] = None
    location_text: Optional[str] = None
    priority: str = "Medium"
    status: str = "New"
    assigned_to: Optional[str] = None
    assigned_team_id: Optional[int] = None  # numeric team id for ICS-214 linkage
    notes: Optional[str] = None
    created_by: str = ""


class LeadUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    source_type: Optional[str] = None
    reported_by: Optional[str] = None
    contact_info: Optional[str] = None
    location_text: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team_id: Optional[int] = None
    notes: Optional[str] = None


class LeadConvert(BaseModel):
    target_type: str  # "subject", "item", "assessment"
    actor: str = "system"


@router.get("/incidents/{incident_id}/intel/leads")
def list_leads(
    incident_id: str,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
):
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if not include_deleted:
        q["deleted"] = False
    if status:
        q["status"] = status
    if priority:
        q["priority"] = priority
    if assigned_to:
        q["assigned_to"] = assigned_to
    docs = list(col.find(q).sort("updated_at", -1))
    return [_map_lead(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/leads", status_code=201)
def create_lead(incident_id: str, data: LeadCreate):
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    now = _utcnow()
    lead_number = _next_lead_number(incident_id)
    doc = {
        "_id": _new_id(),
        "incident_id": incident_id,
        "lead_number": lead_number,
        "deleted": False,
        "created_at": now,
        "updated_at": now,
        **data.model_dump(),
    }
    col.insert_one(doc)
    result = col.find_one({"_id": doc["_id"]})
    _write_log(incident_id, "lead", doc["_id"], "created",
               f"Lead #{lead_number} created: {data.title}", data.created_by or "system")
    return _map_lead(result)


@router.get("/incidents/{incident_id}/intel/leads/{lead_id}")
def get_lead(incident_id: str, lead_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    doc = col.find_one({"_id": lead_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _map_lead(doc)


@router.patch("/incidents/{incident_id}/intel/leads/{lead_id}")
def update_lead(incident_id: str, lead_id: str, data: LeadUpdate):
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    updates["updated_at"] = _utcnow()
    result = col.find_one_and_update(
        {"_id": lead_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Lead not found")
    _write_log(incident_id, "lead", lead_id, "updated",
               f"Lead #{result.get('lead_number')} updated: {result.get('title')}")
    return _map_lead(result)


@router.delete("/incidents/{incident_id}/intel/leads/{lead_id}", status_code=204)
def close_lead(incident_id: str, lead_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    result = col.find_one_and_update(
        {"_id": lead_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "status": "Closed", "updated_at": _utcnow()}},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Lead not found")
    _write_log(incident_id, "lead", lead_id, "closed",
               f"Lead #{result.get('lead_number')} closed")


@router.post("/incidents/{incident_id}/intel/leads/{lead_id}/convert")
def convert_lead(incident_id: str, lead_id: str, data: LeadConvert):
    """Mark lead as converted; the client is responsible for creating the target record."""
    col = _col(incident_id, IncidentCollections.INTEL_LEADS)
    result = col.find_one_and_update(
        {"_id": lead_id, "incident_id": incident_id},
        {"$set": {
            "status": "Converted",
            "converted_to_type": data.target_type,
            "updated_at": _utcnow(),
        }},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Lead not found")
    _write_log(incident_id, "lead", lead_id, "converted",
               f"Lead #{result.get('lead_number')} converted to {data.target_type}", data.actor)
    return _map_lead(result)


# ===========================================================================
# INTEL ITEMS
# ===========================================================================

def _map_observation(obs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "obs_id": obs.get("obs_id", ""),
        "observed_at": obs.get("observed_at", ""),
        "observer": obs.get("observer", ""),
        "source_team": obs.get("source_team"),
        "source_team_id": obs.get("source_team_id"),
        "status": obs.get("status", ""),
        "severity": obs.get("severity", "Unknown"),
        "confidence": obs.get("confidence", "Unconfirmed"),
        "summary": obs.get("summary", ""),
        "detailed_notes": obs.get("detailed_notes"),
        "location_text": obs.get("location_text"),
        "attachments": obs.get("attachments", []),
    }


def _map_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("_id"),
        "incident_id": doc.get("incident_id"),
        "item_type": doc.get("item_type", ""),
        "title": doc.get("title", ""),
        "status": doc.get("status", "Active"),
        "priority": doc.get("priority", "Medium"),
        "confidence": doc.get("confidence", "Unconfirmed"),
        "trend": doc.get("trend", "Unknown"),
        "location_text": doc.get("location_text"),
        "linked_subject_ids": doc.get("linked_subject_ids", []),
        "linked_task_ids": doc.get("linked_task_ids", []),
        "linked_team_ids": doc.get("linked_team_ids", []),
        "created_by": doc.get("created_by", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "notes": doc.get("notes"),
        "deleted": doc.get("deleted", False),
        "observations": [_map_observation(o) for o in doc.get("observations", [])],
        # Linkage back to lead if converted
        "source_lead_id": doc.get("source_lead_id"),
    }


class ObservationCreate(BaseModel):
    observed_at: Optional[str] = None  # ISO string; defaults to now
    observer: str = ""
    source_team: Optional[str] = None
    source_team_id: Optional[int] = None  # numeric team id for ICS-214 linkage
    status: str = ""
    severity: str = "Unknown"
    confidence: str = "Unconfirmed"
    summary: str
    detailed_notes: Optional[str] = None
    location_text: Optional[str] = None
    attachments: List[str] = Field(default_factory=list)
    actor: str = "system"


class ObservationUpdate(BaseModel):
    observed_at: Optional[str] = None
    observer: Optional[str] = None
    source_team: Optional[str] = None
    source_team_id: Optional[int] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[str] = None
    summary: Optional[str] = None
    detailed_notes: Optional[str] = None
    location_text: Optional[str] = None
    attachments: Optional[List[str]] = None


class IntelItemCreate(BaseModel):
    item_type: str
    title: str
    status: str = "Active"
    priority: str = "Medium"
    confidence: str = "Unconfirmed"
    trend: str = "Unknown"
    location_text: Optional[str] = None
    linked_subject_ids: List[str] = Field(default_factory=list)
    linked_task_ids: List[str] = Field(default_factory=list)
    linked_team_ids: List[int] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: str = ""
    source_lead_id: Optional[str] = None


class IntelItemUpdate(BaseModel):
    item_type: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[str] = None
    trend: Optional[str] = None
    location_text: Optional[str] = None
    linked_subject_ids: Optional[List[str]] = None
    linked_task_ids: Optional[List[str]] = None
    linked_team_ids: Optional[List[int]] = None
    notes: Optional[str] = None
    actor: str = "system"


@router.get("/incidents/{incident_id}/intel/items")
def list_items(
    incident_id: str,
    item_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    trend: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
):
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if not include_deleted:
        q["deleted"] = False
    if item_type:
        q["item_type"] = item_type
    if status:
        q["status"] = status
    if priority:
        q["priority"] = priority
    if trend:
        q["trend"] = trend
    docs = list(col.find(q).sort("updated_at", -1))
    return [_map_item(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/items", status_code=201)
def create_item(incident_id: str, data: IntelItemCreate):
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    now = _utcnow()
    doc = {
        "_id": _new_id(),
        "incident_id": incident_id,
        "deleted": False,
        "observations": [],
        "created_at": now,
        "updated_at": now,
        **data.model_dump(),
    }
    col.insert_one(doc)
    result = col.find_one({"_id": doc["_id"]})
    _write_log(incident_id, "item", doc["_id"], "created",
               f"Intel Item created: {data.title} ({data.item_type})", data.created_by or "system")
    return _map_item(result)


@router.get("/incidents/{incident_id}/intel/items/{item_id}")
def get_item(incident_id: str, item_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    doc = col.find_one({"_id": item_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Intel item not found")
    return _map_item(doc)


@router.patch("/incidents/{incident_id}/intel/items/{item_id}")
def update_item(incident_id: str, item_id: str, data: IntelItemUpdate):
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    updates = {k: v for k, v in data.model_dump().items() if v is not None and k != "actor"}
    updates["updated_at"] = _utcnow()
    result = col.find_one_and_update(
        {"_id": item_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Intel item not found")
    _write_log(incident_id, "item", item_id, "updated",
               f"Intel Item updated: {result.get('title')}", data.actor)
    return _map_item(result)


@router.delete("/incidents/{incident_id}/intel/items/{item_id}", status_code=204)
def archive_item(incident_id: str, item_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    result = col.find_one_and_update(
        {"_id": item_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "status": "Archived", "updated_at": _utcnow()}},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Intel item not found")
    _write_log(incident_id, "item", item_id, "archived",
               f"Intel Item archived: {result.get('title')}")


@router.post("/incidents/{incident_id}/intel/items/{item_id}/observations", status_code=201)
def add_observation(incident_id: str, item_id: str, data: ObservationCreate):
    """Append an observation to an existing intel item (items are the parent document)."""
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    obs = {
        "obs_id": _new_id(),
        "observed_at": data.observed_at or _utcnow(),
        "observer": data.observer,
        "source_team": data.source_team,
        "source_team_id": data.source_team_id,
        "status": data.status,
        "severity": data.severity,
        "confidence": data.confidence,
        "summary": data.summary,
        "detailed_notes": data.detailed_notes,
        "location_text": data.location_text,
        "attachments": data.attachments,
    }
    result = col.find_one_and_update(
        {"_id": item_id, "incident_id": incident_id},
        {
            "$push": {"observations": obs},
            "$set": {"updated_at": _utcnow()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Intel item not found")
    _write_log(incident_id, "item", item_id, "observation_added",
               f"Observation added to: {result.get('title')}", data.actor)
    return _map_item(result)


@router.patch("/incidents/{incident_id}/intel/items/{item_id}/observations/{obs_id}")
def update_observation(incident_id: str, item_id: str, obs_id: str, data: ObservationUpdate):
    """Update a single embedded observation by obs_id."""
    col = _col(incident_id, IncidentCollections.INTEL_ITEMS)
    updates = {
        f"observations.$.{k}": v
        for k, v in data.model_dump(exclude_unset=True).items()
        if v is not None
    }
    updates["updated_at"] = _utcnow()
    result = col.find_one_and_update(
        {"_id": item_id, "incident_id": incident_id, "observations.obs_id": obs_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Intel item or observation not found")
    _write_log(incident_id, "item", item_id, "observation_updated",
               f"Observation updated on: {result.get('title')}")
    return _map_item(result)


# ===========================================================================
# ASSESSMENTS
# ===========================================================================

def _map_assessment(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("_id"),
        "incident_id": doc.get("incident_id"),
        "assessment_number": doc.get("assessment_number"),
        "title": doc.get("title", ""),
        "narrative": doc.get("narrative", ""),
        "confidence": doc.get("confidence", "Medium"),
        "status": doc.get("status", "Draft"),
        "recommendations": doc.get("recommendations"),
        "linked_subject_ids": doc.get("linked_subject_ids", []),
        "linked_item_ids": doc.get("linked_item_ids", []),
        "linked_task_ids": doc.get("linked_task_ids", []),
        "author": doc.get("author", ""),
        "notes": doc.get("notes"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "published_at": doc.get("published_at"),
        "deleted": doc.get("deleted", False),
    }


def _next_assessment_number(incident_id: str) -> int:
    col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    top = col.find_one(
        {"incident_id": incident_id, "assessment_number": {"$exists": True}},
        sort=[("assessment_number", -1)],
    )
    return (top["assessment_number"] + 1) if top else 1


class AssessmentCreate(BaseModel):
    title: str
    narrative: str = ""
    confidence: str = "Medium"
    status: str = "Draft"
    recommendations: Optional[str] = None
    linked_subject_ids: List[str] = Field(default_factory=list)
    linked_item_ids: List[str] = Field(default_factory=list)
    linked_task_ids: List[str] = Field(default_factory=list)
    author: str = ""
    notes: Optional[str] = None


class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    narrative: Optional[str] = None
    confidence: Optional[str] = None
    status: Optional[str] = None
    recommendations: Optional[str] = None
    linked_subject_ids: Optional[List[str]] = None
    linked_item_ids: Optional[List[str]] = None
    linked_task_ids: Optional[List[str]] = None
    notes: Optional[str] = None
    actor: str = "system"


@router.get("/incidents/{incident_id}/intel/assessments")
def list_assessments(
    incident_id: str,
    status: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
):
    col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if not include_deleted:
        q["deleted"] = False
    if status:
        q["status"] = status
    docs = list(col.find(q).sort("updated_at", -1))
    return [_map_assessment(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/assessments", status_code=201)
def create_assessment(incident_id: str, data: AssessmentCreate):
    col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    now = _utcnow()
    num = _next_assessment_number(incident_id)
    doc = {
        "_id": _new_id(),
        "incident_id": incident_id,
        "assessment_number": num,
        "deleted": False,
        "created_at": now,
        "updated_at": now,
        **data.model_dump(),
    }
    col.insert_one(doc)
    result = col.find_one({"_id": doc["_id"]})
    _write_log(incident_id, "assessment", doc["_id"], "created",
               f"Assessment A-{num} created: {data.title}", data.author or "system")
    return _map_assessment(result)


@router.get("/incidents/{incident_id}/intel/assessments/{assessment_id}")
def get_assessment(incident_id: str, assessment_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    doc = col.find_one({"_id": assessment_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _map_assessment(doc)


@router.patch("/incidents/{incident_id}/intel/assessments/{assessment_id}")
def update_assessment(incident_id: str, assessment_id: str, data: AssessmentUpdate):
    col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    updates = {k: v for k, v in data.model_dump().items() if v is not None and k != "actor"}
    updates["updated_at"] = _utcnow()
    if updates.get("status") == "Published" and "published_at" not in updates:
        updates["published_at"] = _utcnow()
    result = col.find_one_and_update(
        {"_id": assessment_id, "incident_id": incident_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _write_log(incident_id, "assessment", assessment_id, "updated",
               f"Assessment A-{result.get('assessment_number')} updated: {result.get('title')}",
               data.actor)
    return _map_assessment(result)


@router.delete("/incidents/{incident_id}/intel/assessments/{assessment_id}", status_code=204)
def archive_assessment(incident_id: str, assessment_id: str):
    col = _col(incident_id, IncidentCollections.INTEL_ASSESSMENTS)
    result = col.find_one_and_update(
        {"_id": assessment_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "status": "Archived", "updated_at": _utcnow()}},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Assessment not found")
    _write_log(incident_id, "assessment", assessment_id, "archived",
               f"Assessment archived: {result.get('title')}")


# ===========================================================================
# INTEL LOG
# ===========================================================================

@router.get("/incidents/{incident_id}/intel/log")
def get_intel_log(
    incident_id: str,
    entity_type: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    since: Optional[str] = Query(None),   # ISO datetime string
    until: Optional[str] = Query(None),
    limit: int = Query(200),
):
    log_col = _col(incident_id, IncidentCollections.INTEL_LOG)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if entity_type:
        q["entity_type"] = entity_type
    if event_type:
        q["event_type"] = event_type
    time_filter: Dict[str, str] = {}
    if since:
        time_filter["$gte"] = since
    if until:
        time_filter["$lte"] = until
    if time_filter:
        q["logged_at"] = time_filter
    docs = list(log_col.find(q).sort("logged_at", -1).limit(limit))
    return [
        {
            "id": d.get("_id"),
            "incident_id": d.get("incident_id"),
            "entity_type": d.get("entity_type"),
            "entity_id": d.get("entity_id"),
            "event_type": d.get("event_type"),
            "summary": d.get("summary"),
            "actor": d.get("actor"),
            "logged_at": d.get("logged_at"),
        }
        for d in docs
    ]


# ===========================================================================
# LEGACY — retained for backward compatibility
# Clues, env-snapshots, and form-entries from the pre-redesign module.
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
    doc = {"_id": _new_id(), "int_id": int_id, "incident_id": incident_id,
           **data.model_dump(), "created_at": now, "updated_at": now}
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
def update_clue(incident_id: str, clue_id: int, data: ClueCreate):
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
