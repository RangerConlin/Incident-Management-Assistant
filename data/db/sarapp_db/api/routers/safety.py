"""Safety and CAP ORM API router backed by per-incident MongoDB collections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Body, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()

RISK_LEVELS = ("L", "M", "H", "EH")
RISK_ORDER = {level: index for index, level in enumerate(RISK_LEVELS)}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _next_id(col, incident_id: str) -> int:
    doc = col.find_one(
        {"incident_id": incident_id, "id": {"$exists": True}},
        sort=[("id", -1)],
        projection={"id": 1},
    )
    return int((doc or {}).get("id") or 0) + 1


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _clean_doc(doc: dict[str, Any]) -> dict[str, Any]:
    data = dict(doc)
    data.pop("_id", None)
    return data


def _collection(incident_id: str, name: str):
    return get_incident_db(incident_id)[name]


def _insert_incident_doc(incident_id: str, collection_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    col = _collection(incident_id, collection_name)
    now = _utcnow()
    doc = {
        "_id": _new_uuid(),
        "id": _next_id(col, incident_id),
        "incident_id": incident_id,
        **payload,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    return _clean_doc(doc)


def _query_incident_docs(incident_id: str, collection_name: str, query: dict[str, Any] | None = None):
    base = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if query:
        base.update(query)
    return _collection(incident_id, collection_name).find(base, {"_id": 0}).sort("id", 1)


# ---------------------------------------------------------------------------
# Safety reports
# ---------------------------------------------------------------------------


class SafetyReportRequest(BaseModel):
    time: datetime
    location: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None
    flagged: bool = False
    reported_by: Optional[str] = None


@router.get("/incidents/{incident_id}/safety/reports")
def list_safety_reports(
    incident_id: str,
    severity: Optional[str] = None,
    flagged: Optional[bool] = None,
    q: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if severity:
        query["severity"] = severity
    if flagged is not None:
        query["flagged"] = flagged
    if start or end:
        bounds: dict[str, str] = {}
        if start:
            bounds["$gte"] = start.isoformat()
        if end:
            bounds["$lte"] = end.isoformat()
        query["time"] = bounds
    if q:
        query["notes"] = {"$regex": q, "$options": "i"}
    return list(_query_incident_docs(incident_id, IncidentCollections.SAFETY_REPORTS, query))


@router.post("/incidents/{incident_id}/safety/reports", status_code=201)
def create_safety_report(incident_id: str, body: SafetyReportRequest) -> dict[str, Any]:
    payload = body.model_dump()
    payload["time"] = _iso(payload["time"])
    return _insert_incident_doc(incident_id, IncidentCollections.SAFETY_REPORTS, payload)


# ---------------------------------------------------------------------------
# Medical incidents / triage
# ---------------------------------------------------------------------------


class MedicalIncidentRequest(BaseModel):
    person_id: Optional[str] = None
    type: Optional[str] = None
    time: Optional[datetime] = None
    description: Optional[str] = None
    treatment_given: Optional[str] = None
    evac_required: bool = False
    reported_by: Optional[str] = None


@router.get("/incidents/{incident_id}/medical/incidents")
def list_medical_incidents(incident_id: str) -> list[dict[str, Any]]:
    return list(_query_incident_docs(incident_id, IncidentCollections.MEDICAL_INCIDENTS))


@router.post("/incidents/{incident_id}/medical/incidents", status_code=201)
def create_medical_incident(incident_id: str, body: MedicalIncidentRequest) -> dict[str, Any]:
    payload = body.model_dump()
    payload["time"] = _iso(payload.get("time"))
    return _insert_incident_doc(incident_id, IncidentCollections.MEDICAL_INCIDENTS, payload)


class TriageEntryRequest(BaseModel):
    patient_tag: Optional[str] = None
    location: Optional[str] = None
    triage_level: Optional[str] = None
    time_found: Optional[datetime] = None
    treated_by: Optional[str] = None
    notes: Optional[str] = None
    disposition: Optional[str] = None


@router.get("/incidents/{incident_id}/medical/triage")
def list_triage_entries(incident_id: str) -> list[dict[str, Any]]:
    return list(_query_incident_docs(incident_id, IncidentCollections.TRIAGE_ENTRIES))


@router.post("/incidents/{incident_id}/medical/triage", status_code=201)
def create_triage_entry(incident_id: str, body: TriageEntryRequest) -> dict[str, Any]:
    payload = body.model_dump()
    payload["time_found"] = _iso(payload.get("time_found"))
    return _insert_incident_doc(incident_id, IncidentCollections.TRIAGE_ENTRIES, payload)


# ---------------------------------------------------------------------------
# Hazard zones / legacy CAP ORM summary records / ICS 206 builds
# ---------------------------------------------------------------------------


class HazardZoneRequest(BaseModel):
    name: Optional[str] = None
    coordinates_json: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None


@router.get("/incidents/{incident_id}/safety/zones")
def list_hazard_zones(incident_id: str) -> list[dict[str, Any]]:
    return list(_query_incident_docs(incident_id, IncidentCollections.HAZARD_ZONES))


@router.post("/incidents/{incident_id}/safety/zones", status_code=201)
def create_hazard_zone(incident_id: str, body: HazardZoneRequest) -> dict[str, Any]:
    return _insert_incident_doc(
        incident_id,
        IncidentCollections.HAZARD_ZONES,
        body.model_dump(),
    )


class CapOrmSummaryRequest(BaseModel):
    form_type: Optional[str] = None
    activity: Optional[str] = None
    participants_json: Optional[str] = None
    hazards_json: Optional[str] = None
    mitigations_json: Optional[str] = None
    residual_risk: Optional[str] = None
    created_by: Optional[str] = None


@router.post("/incidents/{incident_id}/safety/caporm", status_code=201)
def create_cap_orm_summary(incident_id: str, body: CapOrmSummaryRequest) -> dict[str, Any]:
    return _insert_incident_doc(
        incident_id,
        IncidentCollections.CAP_ORM_SUMMARIES,
        body.model_dump(),
    )


@router.post("/incidents/{incident_id}/safety/ics206/build", status_code=201)
def build_ics206(incident_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _insert_incident_doc(
        incident_id,
        IncidentCollections.ICS_206_BUILDS,
        dict(payload),
    )


# ---------------------------------------------------------------------------
# CAP ORM detailed workflow
# ---------------------------------------------------------------------------


class FormUpdate(BaseModel):
    op_period: int = Field(ge=1)
    activity: Optional[str] = None
    prepared_by_id: Optional[int] = None
    date_iso: Optional[str] = None


class ApproveRequest(BaseModel):
    op_period: int = Field(ge=1)


class HazardRequest(BaseModel):
    op_period: int = Field(ge=1)
    sub_activity: str
    hazard_outcome: str
    initial_risk: str
    control_text: str
    residual_risk: str
    implement_how: Optional[str] = None
    implement_who: Optional[str] = None


class HazardUpdate(BaseModel):
    sub_activity: str
    hazard_outcome: str
    initial_risk: str
    control_text: str
    residual_risk: str
    implement_how: Optional[str] = None
    implement_who: Optional[str] = None


def _form_col(incident_id: str):
    return _collection(incident_id, IncidentCollections.CAP_ORM_FORMS)


def _hazard_col(incident_id: str):
    return _collection(incident_id, IncidentCollections.CAP_ORM_HAZARDS)


def _audit_col(incident_id: str):
    return _collection(incident_id, IncidentCollections.CAP_ORM_AUDIT)


def _form_query(incident_id: str, op_period: int) -> dict[str, Any]:
    return {"incident_id": incident_id, "op_period": op_period, "deleted": {"$ne": True}}


def _ensure_form(incident_id: str, op_period: int) -> dict[str, Any]:
    col = _form_col(incident_id)
    doc = col.find_one(_form_query(incident_id, op_period), {"_id": 0})
    if doc:
        return doc
    now = _utcnow()
    doc = {
        "_id": _new_uuid(),
        "id": _next_id(col, incident_id),
        "incident_id": incident_id,
        "op_period": op_period,
        "activity": None,
        "prepared_by_id": None,
        "date_iso": None,
        "highest_residual_risk": "L",
        "status": "draft",
        "approval_blocked": False,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    _log_audit(incident_id, "orm_form", doc["id"], "create", None, None, {"op_period": op_period})
    return _clean_doc(doc)


def _hazards_for_form(incident_id: str, form_id: int) -> list[dict[str, Any]]:
    return list(
        _hazard_col(incident_id)
        .find({"incident_id": incident_id, "form_id": form_id, "deleted": {"$ne": True}}, {"_id": 0})
        .sort("id", 1)
    )


def _highest_residual(hazards: list[dict[str, Any]]) -> str:
    highest_index = 0
    for hazard in hazards:
        highest_index = max(highest_index, RISK_ORDER.get(hazard.get("residual_risk"), 0))
    return RISK_LEVELS[highest_index]


def _recompute_form_state(incident_id: str, form: dict[str, Any]) -> dict[str, Any]:
    hazards = _hazards_for_form(incident_id, int(form["id"]))
    highest = _highest_residual(hazards)
    blocked = highest in {"H", "EH"}
    current_status = form.get("status") or "draft"
    status_value = "pending_mitigation" if blocked else ("draft" if current_status == "pending_mitigation" else current_status)
    update = {
        "highest_residual_risk": highest,
        "approval_blocked": blocked,
        "status": status_value,
        "updated_at": _utcnow(),
    }
    _form_col(incident_id).update_one({"id": form["id"], "incident_id": incident_id}, {"$set": update})
    refreshed = _form_col(incident_id).find_one({"id": form["id"], "incident_id": incident_id}, {"_id": 0})
    return refreshed or {**form, **update}


def _log_audit(
    incident_id: str,
    entity: str,
    entity_id: int | None,
    action: str,
    field: str | None,
    old_value: Any,
    new_value: Any,
) -> None:
    _audit_col(incident_id).insert_one(
        {
            "_id": _new_uuid(),
            "incident_id": incident_id,
            "entity": entity,
            "entity_id": entity_id,
            "action": action,
            "field": field,
            "old_value": None if old_value is None else str(old_value),
            "new_value": None if new_value is None else str(new_value),
            "ts_iso": _utcnow(),
        }
    )


@router.get("/incidents/{incident_id}/safety/orm/form")
def get_orm_form(incident_id: str, op: int = Query(..., ge=1)) -> dict[str, Any]:
    return _ensure_form(incident_id, op)


@router.put("/incidents/{incident_id}/safety/orm/form")
def update_orm_form(incident_id: str, body: FormUpdate) -> dict[str, Any]:
    form = _ensure_form(incident_id, body.op_period)
    updates = {
        key: value
        for key, value in body.model_dump(exclude={"op_period"}).items()
        if value is not None
    }
    if updates:
        updates["updated_at"] = _utcnow()
        _form_col(incident_id).update_one(
            {"id": form["id"], "incident_id": incident_id},
            {"$set": updates},
        )
        for key, value in updates.items():
            if key != "updated_at" and form.get(key) != value:
                _log_audit(incident_id, "orm_form", form["id"], "update", key, form.get(key), value)
    return _form_col(incident_id).find_one({"id": form["id"], "incident_id": incident_id}, {"_id": 0}) or form


@router.get("/incidents/{incident_id}/safety/orm/hazards")
def list_orm_hazards(incident_id: str, op: int = Query(..., ge=1)) -> list[dict[str, Any]]:
    form = _ensure_form(incident_id, op)
    return _hazards_for_form(incident_id, int(form["id"]))


@router.post("/incidents/{incident_id}/safety/orm/hazards", status_code=201)
def create_orm_hazard(incident_id: str, body: HazardRequest) -> dict[str, Any]:
    form = _ensure_form(incident_id, body.op_period)
    col = _hazard_col(incident_id)
    now = _utcnow()
    payload = body.model_dump(exclude={"op_period"})
    doc = {
        "_id": _new_uuid(),
        "id": _next_id(col, incident_id),
        "incident_id": incident_id,
        "form_id": form["id"],
        **payload,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    _log_audit(incident_id, "orm_hazard", doc["id"], "create", None, None, payload)
    _recompute_form_state(incident_id, form)
    return _clean_doc(doc)


@router.put("/incidents/{incident_id}/safety/orm/hazards/{hazard_id}")
def update_orm_hazard(
    incident_id: str,
    hazard_id: int,
    body: HazardUpdate,
    op: int = Query(..., ge=1),
) -> dict[str, Any]:
    form = _ensure_form(incident_id, op)
    col = _hazard_col(incident_id)
    old = col.find_one({"id": hazard_id, "incident_id": incident_id, "form_id": form["id"], "deleted": {"$ne": True}})
    if not old:
        raise HTTPException(status_code=404, detail="Hazard not found")
    updates = {**body.model_dump(), "updated_at": _utcnow()}
    col.update_one({"id": hazard_id, "incident_id": incident_id}, {"$set": updates})
    for key, value in body.model_dump().items():
        if old.get(key) != value:
            _log_audit(incident_id, "orm_hazard", hazard_id, "update", key, old.get(key), value)
    _recompute_form_state(incident_id, form)
    return col.find_one({"id": hazard_id, "incident_id": incident_id}, {"_id": 0}) or {}


@router.delete("/incidents/{incident_id}/safety/orm/hazards/{hazard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_orm_hazard(
    incident_id: str,
    hazard_id: int,
    op: int = Query(..., ge=1),
) -> Response:
    form = _ensure_form(incident_id, op)
    col = _hazard_col(incident_id)
    old = col.find_one({"id": hazard_id, "incident_id": incident_id, "form_id": form["id"], "deleted": {"$ne": True}})
    if old:
        col.update_one({"id": hazard_id, "incident_id": incident_id}, {"$set": {"deleted": True, "updated_at": _utcnow()}})
        _log_audit(incident_id, "orm_hazard", hazard_id, "delete", None, old, None)
        _recompute_form_state(incident_id, form)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/incidents/{incident_id}/safety/orm/approve")
def approve_orm_form(incident_id: str, body: ApproveRequest):
    form = _recompute_form_state(incident_id, _ensure_form(incident_id, body.op_period))
    if form.get("approval_blocked"):
        _log_audit(
            incident_id,
            "orm_form",
            form.get("id"),
            "approval_attempt_blocked",
            "highest_residual_risk",
            form.get("highest_residual_risk"),
            form.get("highest_residual_risk"),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "approval_blocked",
                "reason": "highest_residual_risk_h_or_eh",
                "highest_residual_risk": form.get("highest_residual_risk"),
                "message": "Approval is blocked until highest residual risk is Medium or Low.",
            },
        )
    updates = {"status": "approved", "approval_blocked": False, "updated_at": _utcnow()}
    if not form.get("date_iso"):
        updates["date_iso"] = _utcnow()
    _form_col(incident_id).update_one(
        {"id": form["id"], "incident_id": incident_id},
        {"$set": updates},
    )
    _log_audit(incident_id, "orm_form", form["id"], "approve", "status", form.get("status"), "approved")
    return _form_col(incident_id).find_one({"id": form["id"], "incident_id": incident_id}, {"_id": 0}) or {}


# ---------------------------------------------------------------------------
# IWI — Safety Incident (Incident Within Incident) Reports
# ---------------------------------------------------------------------------

from sarapp_db.mongo.collection_names import IncidentCollections as _IC  # noqa: E402


# ---------------------------------------------------------------------------
# ICS-208 — Safety Message (upsert per incident + op period)
# ---------------------------------------------------------------------------

class ICS208Body(BaseModel):
    op_period: int = Field(ge=1)
    op_period_from: Optional[str] = None
    op_period_to: Optional[str] = None
    safety_message: Optional[str] = None
    site_safety_plan_required: bool = False
    site_safety_plan_location: Optional[str] = None
    prepared_by_name: Optional[str] = None
    prepared_by_position: Optional[str] = None
    prepared_by_datetime: Optional[str] = None


@router.get("/incidents/{incident_id}/safety/ics208")
def get_ics208(incident_id: str, op: int = Query(..., ge=1)) -> dict[str, Any]:
    col = _collection(incident_id, _IC.ICS_208_INSTANCES)
    doc = col.find_one({"incident_id": incident_id, "op_period": op}, {"_id": 0})
    if not doc:
        return {"incident_id": incident_id, "op_period": op}
    return doc


@router.put("/incidents/{incident_id}/safety/ics208")
def upsert_ics208(incident_id: str, body: ICS208Body) -> dict[str, Any]:
    col = _collection(incident_id, _IC.ICS_208_INSTANCES)
    now = _utcnow()
    updates = {**body.model_dump(), "incident_id": incident_id, "updated_at": now}
    col.update_one(
        {"incident_id": incident_id, "op_period": body.op_period},
        {"$set": updates, "$setOnInsert": {"_id": _new_uuid(), "created_at": now}},
        upsert=True,
    )
    return col.find_one({"incident_id": incident_id, "op_period": body.op_period}, {"_id": 0}) or updates


def _iwi_col(incident_id: str):
    return _collection(incident_id, _IC.IWI_REPORTS)


def _next_form_number(incident_id: str) -> int:
    doc = _iwi_col(incident_id).find_one(
        {"incident_id": incident_id},
        sort=[("form_number", -1)],
        projection={"form_number": 1},
    )
    return int((doc or {}).get("form_number") or 0) + 1


class IWICreate(BaseModel):
    op_period: Optional[int] = None
    date_of_occurrence: Optional[str] = None
    day_of_event: Optional[int] = None
    time_of_occurrence: Optional[str] = None
    time_reported: Optional[str] = None
    reported_by: Optional[str] = None
    location_general: Optional[str] = None
    location_zone: Optional[str] = None
    location_sector: Optional[str] = None
    location_specific: Optional[str] = None
    incident_types: list[str] = Field(default_factory=list)
    incident_type_other: Optional[str] = None
    actual_outcome: Optional[str] = None
    actual_severity: Optional[str] = None
    activity_impact: Optional[str] = None
    activity_suspension_ref: Optional[str] = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    persons_involved: list[dict[str, Any]] = Field(default_factory=list)
    injury_details: list[dict[str, Any]] = Field(default_factory=list)
    equipment: dict[str, Any] = Field(default_factory=dict)
    sequence_of_events: list[dict[str, Any]] = Field(default_factory=list)
    narrative: Optional[str] = None
    contributing_factors: dict[str, Any] = Field(default_factory=dict)
    immediate_actions: Optional[str] = None
    notifications: list[dict[str, Any]] = Field(default_factory=list)
    corrective_actions: list[dict[str, Any]] = Field(default_factory=list)
    escalation_decision: Optional[str] = None
    escalation_rationale: Optional[str] = None
    witnesses: list[dict[str, Any]] = Field(default_factory=list)
    prepared_by: Optional[str] = None


class IWISignoff(BaseModel):
    role: str  # reporter | supervisor | ops_chief | ic | safety_officer
    name: str


@router.get("/incidents/{incident_id}/safety/iwi")
def list_iwi_reports(
    incident_id: str,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if severity:
        query["actual_severity"] = severity
    if status:
        query["status"] = status
    return list(_query_incident_docs(incident_id, _IC.IWI_REPORTS, query))


@router.post("/incidents/{incident_id}/safety/iwi", status_code=201)
def create_iwi_report(incident_id: str, body: IWICreate) -> dict[str, Any]:
    col = _iwi_col(incident_id)
    now = _utcnow()
    doc = {
        "_id": _new_uuid(),
        "id": _next_id(col, incident_id),
        "form_number": _next_form_number(incident_id),
        "incident_id": incident_id,
        "status": "draft",
        **body.model_dump(),
        "signoffs": {
            "reporter": None,
            "supervisor": None,
            "ops_chief": None,
            "ic": None,
            "safety_officer": None,
        },
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    return _clean_doc(doc)


@router.get("/incidents/{incident_id}/safety/iwi/{report_id}")
def get_iwi_report(incident_id: str, report_id: str) -> dict[str, Any]:
    doc = _iwi_col(incident_id).find_one(
        {"_id": report_id, "incident_id": incident_id, "deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="IWI report not found")
    return doc


@router.put("/incidents/{incident_id}/safety/iwi/{report_id}")
def update_iwi_report(incident_id: str, report_id: str, body: IWICreate) -> dict[str, Any]:
    col = _iwi_col(incident_id)
    existing = col.find_one({"_id": report_id, "incident_id": incident_id, "deleted": {"$ne": True}})
    if not existing:
        raise HTTPException(status_code=404, detail="IWI report not found")
    updates = {**body.model_dump(), "updated_at": _utcnow()}
    col.update_one({"_id": report_id}, {"$set": updates})
    return col.find_one({"_id": report_id}, {"_id": 0}) or {}


@router.post("/incidents/{incident_id}/safety/iwi/{report_id}/signoff")
def signoff_iwi_report(incident_id: str, report_id: str, body: IWISignoff) -> dict[str, Any]:
    col = _iwi_col(incident_id)
    existing = col.find_one({"_id": report_id, "incident_id": incident_id, "deleted": {"$ne": True}})
    if not existing:
        raise HTTPException(status_code=404, detail="IWI report not found")
    now = _utcnow()
    signoff_entry = {"name": body.name, "signed_at": now}
    new_status = existing.get("status", "draft")
    if body.role == "reporter" and new_status == "draft":
        new_status = "submitted"
    elif body.role == "safety_officer" and new_status == "submitted":
        new_status = "reviewed"
    elif body.role == "ic" and new_status == "reviewed":
        new_status = "closed"
    col.update_one(
        {"_id": report_id},
        {"$set": {f"signoffs.{body.role}": signoff_entry, "status": new_status, "updated_at": now}},
    )
    return col.find_one({"_id": report_id}, {"_id": 0}) or {}


@router.delete("/incidents/{incident_id}/safety/iwi/{report_id}", status_code=204)
def delete_iwi_report(incident_id: str, report_id: str) -> Response:
    _iwi_col(incident_id).update_one(
        {"_id": report_id, "incident_id": incident_id},
        {"$set": {"deleted": True, "updated_at": _utcnow()}},
    )
    return Response(status_code=204)
