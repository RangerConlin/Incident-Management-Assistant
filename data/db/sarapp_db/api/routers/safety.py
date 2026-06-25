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
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

RISK_LEVELS = ("L", "M", "H", "EH")
RISK_ORDER = {level: index for index, level in enumerate(RISK_LEVELS)}


class SafetyReportsRepository(BaseRepository):
    collection_name = IncidentCollections.SAFETY_REPORTS


class MedicalIncidentsRepository(BaseRepository):
    collection_name = IncidentCollections.MEDICAL_INCIDENTS


class TriageEntriesRepository(BaseRepository):
    collection_name = IncidentCollections.TRIAGE_ENTRIES


class HazardZonesRepository(BaseRepository):
    collection_name = IncidentCollections.HAZARD_ZONES


class CapOrmSummariesRepository(BaseRepository):
    collection_name = IncidentCollections.CAP_ORM_SUMMARIES


class Ics206BuildsRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_206_BUILDS


class CapOrmFormsRepository(BaseRepository):
    collection_name = IncidentCollections.CAP_ORM_FORMS


class CapOrmHazardsRepository(BaseRepository):
    collection_name = IncidentCollections.CAP_ORM_HAZARDS


class CapOrmAuditRepository(BaseRepository):
    # Audit entries are append-only and never carry a `deleted` field.
    collection_name = IncidentCollections.CAP_ORM_AUDIT
    soft_deletes = False


class Ics208InstancesRepository(BaseRepository):
    collection_name = IncidentCollections.ICS_208_INSTANCES


class IwiReportsRepository(BaseRepository):
    collection_name = IncidentCollections.IWI_REPORTS


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _next_id(repo: BaseRepository, incident_id: str) -> int:
    docs = repo.find_many(
        {"incident_id": incident_id, "id": {"$exists": True}},
        sort=[("id", -1)],
        limit=1,
    )
    return int((docs[0] if docs else {}).get("id") or 0) + 1


def _insert_incident_doc(repo: BaseRepository, incident_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "id": _next_id(repo, incident_id),
        "incident_id": incident_id,
        **payload,
    }
    return repo.insert_one(doc)


def _query_incident_docs(repo: BaseRepository, incident_id: str, query: dict[str, Any] | None = None):
    base: dict[str, Any] = {"incident_id": incident_id}
    if query:
        base.update(query)
    return repo.find_many(base, sort=[("id", 1)])


def _find_by_int_id(repo: BaseRepository, incident_id: str, int_id: int) -> Optional[dict[str, Any]]:
    return repo.find_one({"incident_id": incident_id, "id": int_id})


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
    team_id: Optional[int] = None


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
    repo = SafetyReportsRepository(get_incident_db(incident_id))
    return _query_incident_docs(repo, incident_id, query)


@router.post("/incidents/{incident_id}/safety/reports", status_code=201)
def create_safety_report(incident_id: str, body: SafetyReportRequest) -> dict[str, Any]:
    payload = body.model_dump()
    payload["time"] = _iso(payload["time"])
    repo = SafetyReportsRepository(get_incident_db(incident_id))
    return _insert_incident_doc(repo, incident_id, payload)


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
    team_id: Optional[int] = None


@router.get("/incidents/{incident_id}/medical/incidents")
def list_medical_incidents(incident_id: str) -> list[dict[str, Any]]:
    repo = MedicalIncidentsRepository(get_incident_db(incident_id))
    return _query_incident_docs(repo, incident_id)


@router.post("/incidents/{incident_id}/medical/incidents", status_code=201)
def create_medical_incident(incident_id: str, body: MedicalIncidentRequest) -> dict[str, Any]:
    payload = body.model_dump()
    payload["time"] = _iso(payload.get("time"))
    repo = MedicalIncidentsRepository(get_incident_db(incident_id))
    return _insert_incident_doc(repo, incident_id, payload)


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
    repo = TriageEntriesRepository(get_incident_db(incident_id))
    return _query_incident_docs(repo, incident_id)


@router.post("/incidents/{incident_id}/medical/triage", status_code=201)
def create_triage_entry(incident_id: str, body: TriageEntryRequest) -> dict[str, Any]:
    payload = body.model_dump()
    payload["time_found"] = _iso(payload.get("time_found"))
    repo = TriageEntriesRepository(get_incident_db(incident_id))
    return _insert_incident_doc(repo, incident_id, payload)


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
    repo = HazardZonesRepository(get_incident_db(incident_id))
    return _query_incident_docs(repo, incident_id)


@router.post("/incidents/{incident_id}/safety/zones", status_code=201)
def create_hazard_zone(incident_id: str, body: HazardZoneRequest) -> dict[str, Any]:
    repo = HazardZonesRepository(get_incident_db(incident_id))
    return _insert_incident_doc(repo, incident_id, body.model_dump())


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
    repo = CapOrmSummariesRepository(get_incident_db(incident_id))
    return _insert_incident_doc(repo, incident_id, body.model_dump())


@router.post("/incidents/{incident_id}/safety/ics206/build", status_code=201)
def build_ics206(incident_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = Ics206BuildsRepository(get_incident_db(incident_id))
    return _insert_incident_doc(repo, incident_id, dict(payload))


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


def _forms_repo(incident_id: str) -> CapOrmFormsRepository:
    return CapOrmFormsRepository(get_incident_db(incident_id))


def _hazards_repo(incident_id: str) -> CapOrmHazardsRepository:
    return CapOrmHazardsRepository(get_incident_db(incident_id))


def _audit_repo(incident_id: str) -> CapOrmAuditRepository:
    return CapOrmAuditRepository(get_incident_db(incident_id))


def _log_audit(
    incident_id: str,
    entity: str,
    entity_id: int | None,
    action: str,
    field: str | None,
    old_value: Any,
    new_value: Any,
) -> None:
    _audit_repo(incident_id).insert_one(
        {
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


def _ensure_form(incident_id: str, op_period: int) -> dict[str, Any]:
    repo = _forms_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "op_period": op_period})
    if doc:
        return doc
    form_id = _next_id(repo, incident_id)
    doc = repo.insert_one(
        {
            "id": form_id,
            "incident_id": incident_id,
            "op_period": op_period,
            "activity": None,
            "prepared_by_id": None,
            "date_iso": None,
            "highest_residual_risk": "L",
            "status": "draft",
            "approval_blocked": False,
        }
    )
    _log_audit(incident_id, "orm_form", form_id, "create", None, None, {"op_period": op_period})
    return doc


def _hazards_for_form(incident_id: str, form_id: int) -> list[dict[str, Any]]:
    return _hazards_repo(incident_id).find_many(
        {"incident_id": incident_id, "form_id": form_id}, sort=[("id", 1)]
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
    }
    repo = _forms_repo(incident_id)
    repo.update_one(form["_id"], update)
    return repo.find_by_id(form["_id"]) or {**form, **update}


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
        repo = _forms_repo(incident_id)
        repo.update_one(form["_id"], updates)
        for key, value in updates.items():
            if form.get(key) != value:
                _log_audit(incident_id, "orm_form", form["id"], "update", key, form.get(key), value)
        return repo.find_by_id(form["_id"]) or form
    return form


@router.get("/incidents/{incident_id}/safety/orm/hazards")
def list_orm_hazards(incident_id: str, op: int = Query(..., ge=1)) -> list[dict[str, Any]]:
    form = _ensure_form(incident_id, op)
    return _hazards_for_form(incident_id, int(form["id"]))


@router.post("/incidents/{incident_id}/safety/orm/hazards", status_code=201)
def create_orm_hazard(incident_id: str, body: HazardRequest) -> dict[str, Any]:
    form = _ensure_form(incident_id, body.op_period)
    repo = _hazards_repo(incident_id)
    payload = body.model_dump(exclude={"op_period"})
    hazard_id = _next_id(repo, incident_id)
    doc = repo.insert_one(
        {
            "id": hazard_id,
            "incident_id": incident_id,
            "form_id": form["id"],
            **payload,
        }
    )
    _log_audit(incident_id, "orm_hazard", hazard_id, "create", None, None, payload)
    _recompute_form_state(incident_id, form)
    return doc


@router.put("/incidents/{incident_id}/safety/orm/hazards/{hazard_id}")
def update_orm_hazard(
    incident_id: str,
    hazard_id: int,
    body: HazardUpdate,
    op: int = Query(..., ge=1),
) -> dict[str, Any]:
    form = _ensure_form(incident_id, op)
    repo = _hazards_repo(incident_id)
    old = _find_by_int_id(repo, incident_id, hazard_id)
    if not old or old.get("form_id") != form["id"]:
        raise HTTPException(status_code=404, detail="Hazard not found")
    updates = body.model_dump()
    repo.update_one(old["_id"], updates)
    for key, value in updates.items():
        if old.get(key) != value:
            _log_audit(incident_id, "orm_hazard", hazard_id, "update", key, old.get(key), value)
    _recompute_form_state(incident_id, form)
    return repo.find_by_id(old["_id"]) or {}


@router.delete("/incidents/{incident_id}/safety/orm/hazards/{hazard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_orm_hazard(
    incident_id: str,
    hazard_id: int,
    op: int = Query(..., ge=1),
) -> Response:
    form = _ensure_form(incident_id, op)
    repo = _hazards_repo(incident_id)
    old = _find_by_int_id(repo, incident_id, hazard_id)
    if old and old.get("form_id") == form["id"]:
        repo.soft_delete(old["_id"])
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
    repo = _forms_repo(incident_id)
    updates: dict[str, Any] = {"status": "approved", "approval_blocked": False}
    if not form.get("date_iso"):
        updates["date_iso"] = _utcnow()
    repo.update_one(form["_id"], updates)
    _log_audit(incident_id, "orm_form", form["id"], "approve", "status", form.get("status"), "approved")
    return repo.find_by_id(form["_id"]) or {}


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
    repo = Ics208InstancesRepository(get_incident_db(incident_id))
    doc = repo.find_one({"incident_id": incident_id, "op_period": op})
    if not doc:
        return {"incident_id": incident_id, "op_period": op}
    return doc


@router.put("/incidents/{incident_id}/safety/ics208")
def upsert_ics208(incident_id: str, body: ICS208Body) -> dict[str, Any]:
    repo = Ics208InstancesRepository(get_incident_db(incident_id))
    existing = repo.find_one({"incident_id": incident_id, "op_period": body.op_period})
    updates = {**body.model_dump(), "incident_id": incident_id}
    if existing:
        repo.update_one(existing["_id"], updates)
        return repo.find_by_id(existing["_id"]) or updates
    return repo.insert_one(updates)


def _iwi_repo(incident_id: str) -> IwiReportsRepository:
    return IwiReportsRepository(get_incident_db(incident_id))


def _next_form_number(incident_id: str) -> int:
    docs = _iwi_repo(incident_id).find_many(
        {"incident_id": incident_id}, sort=[("form_number", -1)], limit=1
    )
    return int((docs[0] if docs else {}).get("form_number") or 0) + 1


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
    repo = _iwi_repo(incident_id)
    return _query_incident_docs(repo, incident_id, query)


@router.post("/incidents/{incident_id}/safety/iwi", status_code=201)
def create_iwi_report(incident_id: str, body: IWICreate) -> dict[str, Any]:
    repo = _iwi_repo(incident_id)
    doc = {
        "id": _next_id(repo, incident_id),
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
    }
    return repo.insert_one(doc)


@router.get("/incidents/{incident_id}/safety/iwi/{report_id}")
def get_iwi_report(incident_id: str, report_id: str) -> dict[str, Any]:
    repo = _iwi_repo(incident_id)
    doc = repo.find_one({"_id": report_id, "incident_id": incident_id})
    if not doc:
        raise HTTPException(status_code=404, detail="IWI report not found")
    return doc


@router.put("/incidents/{incident_id}/safety/iwi/{report_id}")
def update_iwi_report(incident_id: str, report_id: str, body: IWICreate) -> dict[str, Any]:
    repo = _iwi_repo(incident_id)
    existing = repo.find_one({"_id": report_id, "incident_id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="IWI report not found")
    repo.update_one(report_id, body.model_dump())
    return repo.find_by_id(report_id) or {}


@router.post("/incidents/{incident_id}/safety/iwi/{report_id}/signoff")
def signoff_iwi_report(incident_id: str, report_id: str, body: IWISignoff) -> dict[str, Any]:
    repo = _iwi_repo(incident_id)
    existing = repo.find_one({"_id": report_id, "incident_id": incident_id})
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
    signoffs = dict(existing.get("signoffs") or {})
    signoffs[body.role] = signoff_entry
    repo.update_one(report_id, {"signoffs": signoffs, "status": new_status})
    return repo.find_by_id(report_id) or {}


@router.delete("/incidents/{incident_id}/safety/iwi/{report_id}", status_code=204)
def delete_iwi_report(incident_id: str, report_id: str) -> Response:
    repo = _iwi_repo(incident_id)
    repo.soft_delete(report_id)
    return Response(status_code=204)
