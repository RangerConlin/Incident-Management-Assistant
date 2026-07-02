"""
Intel Module API router — Module 7 All-Hazards Information Management.

Covers: subjects, leads, intel items (with embedded observations),
assessments, intel log, reports, and the dashboard summary endpoint.

Legacy clue/env-snapshot/form-entry endpoints are retained at the bottom
for backward compatibility until they are formally decommissioned.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class IntelSubjectsRepository(BaseRepository):
    collection_name = IncidentCollections.INTEL_SUBJECTS


class IntelLeadsRepository(BaseRepository):
    collection_name = IncidentCollections.INTEL_LEADS


class IntelItemsRepository(BaseRepository):
    collection_name = IncidentCollections.INTEL_ITEMS


class IntelAssessmentsRepository(BaseRepository):
    collection_name = IncidentCollections.INTEL_ASSESSMENTS


class IntelLogRepository(BaseRepository):
    collection_name = IncidentCollections.INTEL_LOG
    soft_deletes = False


class IntelCluesRepository(BaseRepository):
    collection_name = IncidentCollections.INTEL_CLUES
    soft_deletes = False


def _subjects_repo(incident_id: str) -> IntelSubjectsRepository:
    return IntelSubjectsRepository(get_incident_db(incident_id))


def _leads_repo(incident_id: str) -> IntelLeadsRepository:
    return IntelLeadsRepository(get_incident_db(incident_id))


def _items_repo(incident_id: str) -> IntelItemsRepository:
    return IntelItemsRepository(get_incident_db(incident_id))


def _assessments_repo(incident_id: str) -> IntelAssessmentsRepository:
    return IntelAssessmentsRepository(get_incident_db(incident_id))


def _log_repo(incident_id: str) -> IntelLogRepository:
    return IntelLogRepository(get_incident_db(incident_id))


def _clues_repo(incident_id: str) -> IntelCluesRepository:
    return IntelCluesRepository(get_incident_db(incident_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_int_ids(repo: BaseRepository) -> None:
    """Lazy-migrate documents that are missing int_id (numeric surrogate key)."""
    col = repo._col
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _next_int_id(repo: BaseRepository) -> int:
    top = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


def _write_log(incident_id: str, entity_type: str, entity_id: str,
               event_type: str, summary: str, actor: str = "system") -> None:
    """Append a chronological entry to the intel activity log."""
    log_repo = _log_repo(incident_id)
    log_repo.insert_one({
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
    subjects_repo = _subjects_repo(incident_id)
    leads_repo = _leads_repo(incident_id)
    items_repo = _items_repo(incident_id)
    assessments_repo = _assessments_repo(incident_id)
    log_repo = _log_repo(incident_id)

    active_subjects = subjects_repo.count({
        "incident_id": incident_id,
        "status": {"$nin": ["Archived", "Closed"]},
    }, include_deleted=False)
    open_leads = leads_repo.count({
        "incident_id": incident_id,
        "status": {"$nin": ["Closed", "Rejected", "Converted"]},
    }, include_deleted=False)
    total_items = items_repo.count({
        "incident_id": incident_id,
        "status": {"$nin": ["Archived"]},
    }, include_deleted=False)
    critical_items = items_repo.count({
        "incident_id": incident_id,
        "priority": "Critical", "status": {"$nin": ["Archived"]},
    }, include_deleted=False)
    worsening_items = items_repo.count({
        "incident_id": incident_id,
        "trend": "Worsening", "status": {"$nin": ["Archived"]},
    }, include_deleted=False)
    improving_items = items_repo.count({
        "incident_id": incident_id,
        "trend": "Improving", "status": {"$nin": ["Archived"]},
    }, include_deleted=False)
    open_assessments = assessments_repo.count({
        "incident_id": incident_id,
        "status": {"$nin": ["Archived"]},
    }, include_deleted=False)
    # 20 most recent log entries for the Recent Activity feed
    recent = log_repo.find_many({"incident_id": incident_id}, sort=[("logged_at", -1)], limit=20)

    # Critical items list for dashboard centre panel
    critical_docs = items_repo.find_many(
        {"incident_id": incident_id, "priority": "Critical", "status": {"$nin": ["Archived"]}},
        sort=[("updated_at", -1)], limit=8,
    )

    # Open leads for dashboard snapshot panel (unresolved, priority order)
    lead_docs = leads_repo.find_many(
        {"incident_id": incident_id, "status": {"$nin": ["Closed", "Rejected", "Converted"]}},
        sort=[("updated_at", -1)], limit=8,
    )

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
        "relationship_to_incident": doc.get("relationship_to_incident"),
        # Medical
        "medical_conditions": doc.get("medical_conditions"),
        "medications": doc.get("medications"),
        "mobility_limitations": doc.get("mobility_limitations"),
        # Experience / behavior
        "outdoor_experience": doc.get("outdoor_experience"),
        "behavioral_notes": doc.get("behavioral_notes"),
        "communication_needs": doc.get("communication_needs"),
        "sensory_considerations": doc.get("sensory_considerations"),
        "routine_habits": doc.get("routine_habits"),
        "wandering_history": doc.get("wandering_history"),
        "favorite_places": doc.get("favorite_places"),
        "triggers_or_stressors": doc.get("triggers_or_stressors"),
        "recent_changes": doc.get("recent_changes"),
        "equipment_description": doc.get("equipment_description"),
        "clothing_description": doc.get("clothing_description"),
        "vehicle_description": doc.get("vehicle_description"),
        # Witness / contact specifics
        "treatment_given": doc.get("treatment_given"),
        "transport_required": doc.get("transport_required"),
        "transport_method": doc.get("transport_method"),
        "transport_destination": doc.get("transport_destination"),
        "disposition": doc.get("disposition"),
        # Vehicle-specific
        "plate": doc.get("plate"),
        "plate_state": doc.get("plate_state"),
        "make": doc.get("make"),
        "model": doc.get("model"),
        "year": doc.get("year"),
        "color": doc.get("color"),
        "vin": doc.get("vin"),
        "owner_or_operator": doc.get("owner_or_operator"),
        # Aircraft-specific
        "tail_number": doc.get("tail_number"),
        "aircraft_type": doc.get("aircraft_type"),
        "make_model": doc.get("make_model"),
        "color_markings": doc.get("color_markings"),
        "pilot_or_operator": doc.get("pilot_or_operator"),
        "route_or_last_contact": doc.get("route_or_last_contact"),
        "departure_point": doc.get("departure_point"),
        "destination": doc.get("destination"),
        "occupants": doc.get("occupants"),
        "fuel_endurance": doc.get("fuel_endurance"),
        "elt_survival_gear": doc.get("elt_survival_gear"),
        "remarks": doc.get("remarks"),
        # General description
        "description": doc.get("description"),
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
    relationship_to_incident: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    mobility_limitations: Optional[str] = None
    outdoor_experience: Optional[str] = None
    behavioral_notes: Optional[str] = None
    communication_needs: Optional[str] = None
    sensory_considerations: Optional[str] = None
    routine_habits: Optional[str] = None
    wandering_history: Optional[str] = None
    favorite_places: Optional[str] = None
    triggers_or_stressors: Optional[str] = None
    recent_changes: Optional[str] = None
    equipment_description: Optional[str] = None
    clothing_description: Optional[str] = None
    vehicle_description: Optional[str] = None
    treatment_given: Optional[str] = None
    transport_required: Optional[str] = None
    transport_method: Optional[str] = None
    transport_destination: Optional[str] = None
    disposition: Optional[str] = None
    # Vehicle-specific
    plate: Optional[str] = None
    plate_state: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    vin: Optional[str] = None
    owner_or_operator: Optional[str] = None
    # Aircraft-specific
    tail_number: Optional[str] = None
    aircraft_type: Optional[str] = None
    make_model: Optional[str] = None
    color_markings: Optional[str] = None
    pilot_or_operator: Optional[str] = None
    route_or_last_contact: Optional[str] = None
    departure_point: Optional[str] = None
    destination: Optional[str] = None
    occupants: Optional[str] = None
    fuel_endurance: Optional[str] = None
    elt_survival_gear: Optional[str] = None
    remarks: Optional[str] = None
    # General description
    description: Optional[str] = None
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
    repo = _subjects_repo(incident_id)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if subject_type:
        q["subject_type"] = subject_type
    if status:
        q["status"] = status
    docs = repo.find_many(q, sort=[("updated_at", -1)], include_deleted=include_deleted)
    return [_map_subject(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/subjects", status_code=201)
def create_subject(incident_id: str, data: SubjectCreate):
    repo = _subjects_repo(incident_id)
    doc = {
        "incident_id": incident_id,
        **data.model_dump(),
    }
    saved = repo.insert_one(doc)
    _write_log(incident_id, "subject", saved["_id"], "created",
               f"Subject created: {data.name} ({data.subject_type})", data.created_by or "system")
    return _map_subject(saved)


@router.get("/incidents/{incident_id}/intel/subjects/{subject_id}")
def get_subject(incident_id: str, subject_id: str):
    repo = _subjects_repo(incident_id)
    doc = repo.find_one({"_id": subject_id, "incident_id": incident_id}, include_deleted=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Subject not found")
    return _map_subject(doc)


@router.patch("/incidents/{incident_id}/intel/subjects/{subject_id}")
def update_subject(incident_id: str, subject_id: str, data: SubjectUpdate):
    repo = _subjects_repo(incident_id)
    existing = repo.find_one({"_id": subject_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Subject not found")
    updates = data.model_dump(exclude_unset=False)
    repo.update_one(subject_id, updates, extra_filter={"incident_id": incident_id})
    result = repo.find_by_id(subject_id, include_deleted=True)
    _write_log(incident_id, "subject", subject_id, "updated",
               f"Subject updated: {result.get('name')}", data.created_by or "system")
    return _map_subject(result)


@router.delete("/incidents/{incident_id}/intel/subjects/{subject_id}", status_code=204)
def archive_subject(incident_id: str, subject_id: str):
    repo = _subjects_repo(incident_id)
    existing = repo.find_one({"_id": subject_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Subject not found")
    repo.soft_delete(subject_id)
    _write_log(incident_id, "subject", subject_id, "archived",
               f"Subject archived: {existing.get('name')}")


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
        # Structured source fields
        "source_category": doc.get("source_category"),
        "source_display": doc.get("source_display"),
        "source_ref_type": doc.get("source_ref_type"),
        "source_ref_id": doc.get("source_ref_id"),
        "source_subject_id": doc.get("source_subject_id"),
        "source_team_id": doc.get("source_team_id"),
        "source_team_name": doc.get("source_team_name"),
        "source_staff_id": doc.get("source_staff_id"),
        "source_agency": doc.get("source_agency"),
        "source_role": doc.get("source_role"),
        "source_contact_name": doc.get("source_contact_name"),
        "source_phone": doc.get("source_phone"),
        "source_email": doc.get("source_email"),
        "source_address": doc.get("source_address"),
        "source_contact_method": doc.get("source_contact_method"),
        "source_notes": doc.get("source_notes"),
        "source_reliability": doc.get("source_reliability"),
        "information_confidence": doc.get("information_confidence"),
    }


def _next_lead_number(incident_id: str) -> int:
    repo = _leads_repo(incident_id)
    docs = repo.find_many(
        {"incident_id": incident_id, "lead_number": {"$exists": True}},
        sort=[("lead_number", -1)], limit=1, include_deleted=True,
    )
    top = docs[0] if docs else None
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
    # Structured source fields
    source_category: Optional[str] = None
    source_display: Optional[str] = None
    source_ref_type: Optional[str] = None
    source_ref_id: Optional[str] = None
    source_subject_id: Optional[str] = None
    source_team_id: Optional[int] = None
    source_team_name: Optional[str] = None
    source_staff_id: Optional[str] = None
    source_agency: Optional[str] = None
    source_role: Optional[str] = None
    source_contact_name: Optional[str] = None
    source_phone: Optional[str] = None
    source_email: Optional[str] = None
    source_address: Optional[str] = None
    source_contact_method: Optional[str] = None
    source_notes: Optional[str] = None
    source_reliability: Optional[str] = None
    information_confidence: Optional[str] = None


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
    actor: str = "system"
    # Structured source fields
    source_category: Optional[str] = None
    source_display: Optional[str] = None
    source_ref_type: Optional[str] = None
    source_ref_id: Optional[str] = None
    source_subject_id: Optional[str] = None
    source_team_id: Optional[int] = None
    source_team_name: Optional[str] = None
    source_staff_id: Optional[str] = None
    source_agency: Optional[str] = None
    source_role: Optional[str] = None
    source_contact_name: Optional[str] = None
    source_phone: Optional[str] = None
    source_email: Optional[str] = None
    source_address: Optional[str] = None
    source_contact_method: Optional[str] = None
    source_notes: Optional[str] = None
    source_reliability: Optional[str] = None
    information_confidence: Optional[str] = None


class LeadConvert(BaseModel):
    target_type: str  # "subject", "item", "assessment"
    target_id: Optional[str] = None  # id of the created target record
    actor: str = "system"


@router.get("/incidents/{incident_id}/intel/leads")
def list_leads(
    incident_id: str,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
):
    repo = _leads_repo(incident_id)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if status:
        q["status"] = status
    if priority:
        q["priority"] = priority
    if assigned_to:
        q["assigned_to"] = assigned_to
    docs = repo.find_many(q, sort=[("updated_at", -1)], include_deleted=include_deleted)
    return [_map_lead(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/leads", status_code=201)
def create_lead(incident_id: str, data: LeadCreate):
    repo = _leads_repo(incident_id)
    lead_number = _next_lead_number(incident_id)
    doc = {
        "incident_id": incident_id,
        "lead_number": lead_number,
        **data.model_dump(),
    }
    saved = repo.insert_one(doc)
    _write_log(incident_id, "lead", saved["_id"], "created",
               f"L-{lead_number:03d} created: {data.title}", data.created_by or "system")
    return _map_lead(saved)


@router.get("/incidents/{incident_id}/intel/leads/{lead_id}")
def get_lead(incident_id: str, lead_id: str):
    repo = _leads_repo(incident_id)
    doc = repo.find_one({"_id": lead_id, "incident_id": incident_id}, include_deleted=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _map_lead(doc)


@router.patch("/incidents/{incident_id}/intel/leads/{lead_id}")
def update_lead(incident_id: str, lead_id: str, data: LeadUpdate):
    repo = _leads_repo(incident_id)
    updates = {k: v for k, v in data.model_dump().items()
               if v is not None and k != "actor"}
    existing = repo.find_one({"_id": lead_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Lead not found")
    repo.update_one(lead_id, updates, extra_filter={"incident_id": incident_id})
    result = repo.find_by_id(lead_id, include_deleted=True)
    actor = data.actor or "system"
    ln = result.get("lead_number", 0)
    disp = f"L-{ln:03d}" if ln else "Lead"
    title = result.get("title", "")
    if "assigned_to" in updates and updates.get("assigned_to"):
        _write_log(incident_id, "lead", lead_id, "assigned",
                   f"{disp} assigned to {updates['assigned_to']}: {title}", actor)
    elif updates.get("status") == "Rejected":
        _write_log(incident_id, "lead", lead_id, "rejected",
                   f"{disp} rejected: {title}", actor)
    elif "status" in updates:
        _write_log(incident_id, "lead", lead_id, "status_changed",
                   f"{disp} status changed to {updates['status']}: {title}", actor)
    elif "priority" in updates:
        _write_log(incident_id, "lead", lead_id, "priority_changed",
                   f"{disp} priority changed to {updates['priority']}: {title}", actor)
    else:
        _write_log(incident_id, "lead", lead_id, "updated",
                   f"{disp} updated: {title}", actor)
    return _map_lead(result)


@router.delete("/incidents/{incident_id}/intel/leads/{lead_id}", status_code=204)
def close_lead(incident_id: str, lead_id: str):
    repo = _leads_repo(incident_id)
    existing = repo.find_one({"_id": lead_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Lead not found")
    repo.update_one(lead_id, {"deleted": True, "status": "Closed"}, extra_filter={"incident_id": incident_id})
    ln = existing.get("lead_number", 0)
    disp = f"L-{ln:03d}" if ln else "Lead"
    _write_log(incident_id, "lead", lead_id, "closed",
               f"{disp} closed: {existing.get('title', '')}")


@router.post("/incidents/{incident_id}/intel/leads/{lead_id}/convert")
def convert_lead(incident_id: str, lead_id: str, data: LeadConvert):
    """Mark lead as converted; the client is responsible for creating the target record."""
    repo = _leads_repo(incident_id)
    existing = repo.find_one({"_id": lead_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Lead not found")
    update: Dict[str, Any] = {
        "status": "Converted",
        "converted_to_type": data.target_type,
    }
    if data.target_id:
        update["converted_to_id"] = data.target_id
    repo.update_one(lead_id, update, extra_filter={"incident_id": incident_id})
    result = repo.find_by_id(lead_id, include_deleted=True)
    ln = result.get("lead_number", 0)
    disp = f"L-{ln:03d}" if ln else "Lead"
    target_labels = {"item": "Intel Item", "subject": "Subject", "assessment": "Assessment"}
    target_label = target_labels.get(data.target_type, data.target_type.title())
    _write_log(incident_id, "lead", lead_id, "converted",
               f"{disp} converted to {target_label}: {result.get('title', '')}", data.actor)
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
    repo = _items_repo(incident_id)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if item_type:
        q["item_type"] = item_type
    if status:
        q["status"] = status
    if priority:
        q["priority"] = priority
    if trend:
        q["trend"] = trend
    docs = repo.find_many(q, sort=[("updated_at", -1)], include_deleted=include_deleted)
    return [_map_item(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/items", status_code=201)
def create_item(incident_id: str, data: IntelItemCreate):
    repo = _items_repo(incident_id)
    doc = {
        "incident_id": incident_id,
        "observations": [],
        **data.model_dump(),
    }
    saved = repo.insert_one(doc)
    _write_log(incident_id, "item", saved["_id"], "created",
               f"Intel Item created: {data.title} ({data.item_type})", data.created_by or "system")
    return _map_item(saved)


@router.get("/incidents/{incident_id}/intel/items/{item_id}")
def get_item(incident_id: str, item_id: str):
    repo = _items_repo(incident_id)
    doc = repo.find_one({"_id": item_id, "incident_id": incident_id}, include_deleted=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Intel item not found")
    return _map_item(doc)


@router.patch("/incidents/{incident_id}/intel/items/{item_id}")
def update_item(incident_id: str, item_id: str, data: IntelItemUpdate):
    repo = _items_repo(incident_id)
    updates = {k: v for k, v in data.model_dump().items() if v is not None and k != "actor"}
    existing = repo.find_one({"_id": item_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Intel item not found")
    repo.update_one(item_id, updates, extra_filter={"incident_id": incident_id})
    result = repo.find_by_id(item_id, include_deleted=True)
    actor = data.actor or "system"
    title = result.get("title", "")
    item_type = result.get("item_type", "")
    if "status" in updates and updates["status"] != existing.get("status"):
        new_status = updates["status"]
        if new_status == "Archived":
            _write_log(incident_id, "item", item_id, "archived",
                       f"Intel Item archived: {title}", actor)
        else:
            _write_log(incident_id, "item", item_id, "status_changed",
                       f"Intel Item status changed to {new_status}: {title}", actor)
    elif "priority" in updates and updates["priority"] != existing.get("priority"):
        _write_log(incident_id, "item", item_id, "priority_changed",
                   f"Intel Item priority changed to {updates['priority']}: {title}", actor)
    elif "linked_subject_ids" in updates:
        _write_log(incident_id, "item", item_id, "linked",
                   f"Subject links updated on Intel Item: {title}", actor)
    elif "linked_task_ids" in updates:
        _write_log(incident_id, "item", item_id, "linked",
                   f"Task links updated on Intel Item: {title}", actor)
    else:
        _write_log(incident_id, "item", item_id, "updated",
                   f"Intel Item updated: {title} ({item_type})", actor)
    return _map_item(result)


@router.delete("/incidents/{incident_id}/intel/items/{item_id}", status_code=204)
def archive_item(incident_id: str, item_id: str):
    repo = _items_repo(incident_id)
    existing = repo.find_one({"_id": item_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Intel item not found")
    repo.update_one(item_id, {"deleted": True, "status": "Archived"}, extra_filter={"incident_id": incident_id})
    _write_log(incident_id, "item", item_id, "archived",
               f"Intel Item archived: {existing.get('title')}")


@router.post("/incidents/{incident_id}/intel/items/{item_id}/observations", status_code=201)
def add_observation(incident_id: str, item_id: str, data: ObservationCreate):
    """Append an observation to an existing intel item (items are the parent document)."""
    import uuid as _uuid
    repo = _items_repo(incident_id)
    obs = {
        "obs_id": str(_uuid.uuid4()),
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
    existing = repo.find_one({"_id": item_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Intel item not found")
    # $push to an embedded array — not expressible via BaseRepository's
    # generic methods, so we drop to the raw collection and broadcast
    # ourselves, mirroring update_one's pattern.
    repo._col.update_one(
        {"_id": item_id, "incident_id": incident_id},
        {"$push": {"observations": obs}, "$set": {"updated_at": _utcnow()}},
    )
    result = repo._col.find_one({"_id": item_id, "incident_id": incident_id})
    if result:
        repo._broadcast("updated", item_id, result)
    obs_summary = data.summary[:80] if data.summary else ""
    _write_log(incident_id, "observation", item_id, "observation_added",
               f"Observation added to Intel Item: {result.get('title', '')} — {obs_summary}", data.actor)
    return _map_item(result)


@router.patch("/incidents/{incident_id}/intel/items/{item_id}/observations/{obs_id}")
def update_observation(incident_id: str, item_id: str, obs_id: str, data: ObservationUpdate):
    """Update a single embedded observation by obs_id."""
    repo = _items_repo(incident_id)
    updates = {
        f"observations.$.{k}": v
        for k, v in data.model_dump(exclude_unset=True).items()
        if v is not None
    }
    updates["updated_at"] = _utcnow()
    # Positional `$` array update — not expressible via BaseRepository's
    # generic methods, so we drop to the raw collection and broadcast
    # ourselves, mirroring update_one's pattern.
    result = repo._col.find_one_and_update(
        {"_id": item_id, "incident_id": incident_id, "observations.obs_id": obs_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Intel item or observation not found")
    repo._broadcast("updated", item_id, result)
    obs_sum = next(
        (o.get("summary", "") for o in (result.get("observations") or []) if o.get("obs_id") == obs_id),
        "",
    )
    _write_log(incident_id, "observation", item_id, "observation_updated",
               f"Observation updated on Intel Item: {result.get('title', '')} — {obs_sum[:80]}")
    return _map_item(result)


# ===========================================================================
# ASSESSMENTS
# ===========================================================================

def _map_assessment(doc: Dict[str, Any]) -> Dict[str, Any]:
    # summary/findings/analyst are the canonical field names.
    # Fall back to legacy narrative/author for records written by older code.
    return {
        "id": doc.get("_id"),
        "incident_id": doc.get("incident_id"),
        "assessment_number": doc.get("assessment_number"),
        "title": doc.get("title", ""),
        "summary": doc.get("summary") or doc.get("narrative", ""),
        "findings": doc.get("findings", ""),
        "recommendations": doc.get("recommendations"),
        "analyst": doc.get("analyst") or doc.get("author", ""),
        "status": doc.get("status", "Draft"),
        "linked_subject_ids": doc.get("linked_subject_ids", []),
        "linked_item_ids": doc.get("linked_item_ids", []),
        "linked_task_ids": doc.get("linked_task_ids", []),
        "notes": doc.get("notes"),
        "created_by": doc.get("created_by", ""),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "deleted": doc.get("deleted", False),
    }


def _next_assessment_number(incident_id: str) -> int:
    repo = _assessments_repo(incident_id)
    docs = repo.find_many(
        {"incident_id": incident_id, "assessment_number": {"$exists": True}},
        sort=[("assessment_number", -1)], limit=1, include_deleted=True,
    )
    top = docs[0] if docs else None
    return (top["assessment_number"] + 1) if top else 1


class AssessmentCreate(BaseModel):
    title: str
    summary: str = ""
    findings: str = ""
    recommendations: Optional[str] = None
    status: str = "Draft"
    analyst: str = ""
    linked_subject_ids: List[str] = Field(default_factory=list)
    linked_item_ids: List[str] = Field(default_factory=list)
    linked_task_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: str = ""
    # Legacy field aliases kept for records written by older code
    narrative: str = ""
    author: str = ""


class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    status: Optional[str] = None
    analyst: Optional[str] = None
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
    repo = _assessments_repo(incident_id)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if status:
        q["status"] = status
    docs = repo.find_many(q, sort=[("updated_at", -1)], include_deleted=include_deleted)
    return [_map_assessment(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/assessments", status_code=201)
def create_assessment(incident_id: str, data: AssessmentCreate):
    repo = _assessments_repo(incident_id)
    num = _next_assessment_number(incident_id)
    doc = {
        "incident_id": incident_id,
        "assessment_number": num,
        **data.model_dump(),
    }
    saved = repo.insert_one(doc)
    _write_log(incident_id, "assessment", saved["_id"], "created",
               f"Assessment A-{num:03d} created: {data.title}",
               data.analyst or data.author or data.created_by or "system")
    return _map_assessment(saved)


@router.get("/incidents/{incident_id}/intel/assessments/{assessment_id}")
def get_assessment(incident_id: str, assessment_id: str):
    repo = _assessments_repo(incident_id)
    doc = repo.find_one({"_id": assessment_id, "incident_id": incident_id}, include_deleted=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _map_assessment(doc)


@router.patch("/incidents/{incident_id}/intel/assessments/{assessment_id}")
def update_assessment(incident_id: str, assessment_id: str, data: AssessmentUpdate):
    repo = _assessments_repo(incident_id)
    updates = {k: v for k, v in data.model_dump().items() if v is not None and k != "actor"}
    existing = repo.find_one({"_id": assessment_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Assessment not found")
    repo.update_one(assessment_id, updates, extra_filter={"incident_id": incident_id})
    result = repo.find_by_id(assessment_id, include_deleted=True)
    num = result.get("assessment_number", 0)
    num_str = f"A-{num:03d}"
    title = result.get("title", "")
    new_status = updates.get("status")
    old_status = existing.get("status", "")
    # Determine event type and summary
    if new_status and new_status != old_status:
        _status_lower = (new_status or "").lower()
        if _status_lower == "complete":
            event_type = "completed"
            summary = f"{num_str} marked complete: {title}"
        elif _status_lower == "archived":
            event_type = "archived"
            summary = f"{num_str} archived: {title}"
        else:
            event_type = "status_changed"
            summary = f"{num_str} status changed to {new_status}: {title}"
        _write_log(incident_id, "assessment", assessment_id, event_type, summary, data.actor)
    # Log link changes for subjects
    old_subs = set(existing.get("linked_subject_ids") or [])
    raw_subs = updates.get("linked_subject_ids")
    new_subs = set(raw_subs) if raw_subs is not None else old_subs
    for sid in new_subs - old_subs:
        _write_log(incident_id, "assessment", assessment_id, "linked",
                   f"{num_str} linked to Subject {sid}", data.actor)
    for sid in old_subs - new_subs:
        _write_log(incident_id, "assessment", assessment_id, "unlinked",
                   f"{num_str} unlinked from Subject {sid}", data.actor)
    # Log link changes for intel items
    old_items = set(existing.get("linked_item_ids") or [])
    raw_items = updates.get("linked_item_ids")
    new_items = set(raw_items) if raw_items is not None else old_items
    for iid in new_items - old_items:
        _write_log(incident_id, "assessment", assessment_id, "linked",
                   f"{num_str} linked to Intel Item {iid}", data.actor)
    for iid in old_items - new_items:
        _write_log(incident_id, "assessment", assessment_id, "unlinked",
                   f"{num_str} unlinked from Intel Item {iid}", data.actor)
    # General update log if no status change triggered a specific event
    if not new_status or new_status == old_status:
        _write_log(incident_id, "assessment", assessment_id, "updated",
                   f"{num_str} updated: {title}", data.actor)
    return _map_assessment(result)


@router.delete("/incidents/{incident_id}/intel/assessments/{assessment_id}", status_code=204)
def archive_assessment(incident_id: str, assessment_id: str):
    repo = _assessments_repo(incident_id)
    existing = repo.find_one({"_id": assessment_id, "incident_id": incident_id}, include_deleted=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Assessment not found")
    repo.update_one(assessment_id, {"deleted": True, "status": "Archived"}, extra_filter={"incident_id": incident_id})
    _write_log(incident_id, "assessment", assessment_id, "archived",
               f"Assessment archived: {existing.get('title')}")


# ===========================================================================
# INTEL LOG
# ===========================================================================

@router.get("/incidents/{incident_id}/intel/log")
def get_intel_log(
    incident_id: str,
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    since: Optional[str] = Query(None),   # ISO datetime string
    until: Optional[str] = Query(None),
    limit: int = Query(200),
):
    repo = _log_repo(incident_id)
    q: Dict[str, Any] = {"incident_id": incident_id}
    if entity_type:
        q["entity_type"] = entity_type
    if entity_id:
        q["entity_id"] = entity_id
    if event_type:
        q["event_type"] = event_type
    if actor:
        q["actor"] = actor
    time_filter: Dict[str, str] = {}
    if since:
        time_filter["$gte"] = since
    if until:
        time_filter["$lte"] = until
    if time_filter:
        q["logged_at"] = time_filter
    docs = repo.find_many(q, sort=[("logged_at", -1)], limit=limit)
    return [
        {
            "id": d.get("_id"),
            "incident_id": d.get("incident_id"),
            "entity_type": d.get("entity_type"),
            "entity_id": d.get("entity_id"),
            "event_type": d.get("event_type"),
            "summary": d.get("summary"),
            "actor": d.get("actor"),
            "timestamp": d.get("logged_at"),
        }
        for d in docs
    ]


@router.post("/incidents/{incident_id}/intel/log", status_code=201)
def write_intel_log_entry(
    incident_id: str,
    body: Dict[str, Any] = Body(...),
):
    """Write a single Intel Log entry.  Intended for client-side actions
    (e.g. file-system attachment adds/removes) that the server cannot log
    automatically."""
    entity_type = body.get("entity_type", "")
    entity_id = body.get("entity_id", "")
    event_type = body.get("event_type", "")
    summary = body.get("summary", "")
    actor = body.get("actor", "system")
    if not (entity_type and entity_id and event_type and summary):
        raise HTTPException(status_code=422, detail="entity_type, entity_id, event_type, and summary are required")
    _write_log(incident_id, entity_type, entity_id, event_type, summary, actor)
    return {"ok": True}


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
    repo = _clues_repo(incident_id)
    _ensure_int_ids(repo)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("created_at", -1)])
    return [_map_clue(d) for d in docs]


@router.post("/incidents/{incident_id}/intel/clues", status_code=201)
def add_clue(incident_id: str, data: ClueCreate):
    repo = _clues_repo(incident_id)
    _ensure_int_ids(repo)
    int_id = _next_int_id(repo)
    doc = {"int_id": int_id, "incident_id": incident_id, **data.model_dump()}
    repo.insert_one(doc)
    return _map_clue(repo.find_one({"int_id": int_id}))


@router.get("/incidents/{incident_id}/intel/clues/{clue_id}")
def get_clue(incident_id: str, clue_id: int):
    repo = _clues_repo(incident_id)
    doc = repo.find_one({"int_id": clue_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Clue not found")
    return _map_clue(doc)


@router.put("/incidents/{incident_id}/intel/clues/{clue_id}")
def update_clue(incident_id: str, clue_id: int, data: ClueCreate):
    repo = _clues_repo(incident_id)
    existing = repo.find_one({"int_id": clue_id, "incident_id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Clue not found")
    repo.update_one(existing["_id"], data.model_dump())
    result = repo.find_by_id(existing["_id"])
    return _map_clue(result)


@router.delete("/incidents/{incident_id}/intel/clues/{clue_id}", status_code=204)
def delete_clue(incident_id: str, clue_id: int):
    repo = _clues_repo(incident_id)
    existing = repo.find_one({"int_id": clue_id, "incident_id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Clue not found")
    repo.delete_one(existing["_id"])
