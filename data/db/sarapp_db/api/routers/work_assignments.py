"""Work Assignments router — per-incident, mirrors WorkAssignmentRepository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.db_manager import DatabaseManager
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.int_id import _ensure_int_ids, next_int_id

router = APIRouter()

COL = IncidentCollections.WORK_ASSIGNMENTS
OUTPUT_TYPE_VALUES = ["ICS 204", "ICS 215", "ICS 215A", "Briefing Sheet"]


def _col(incident_id: str):
    return DatabaseManager().get_incident_db(incident_id)[COL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


def _next_sub_id(items: list) -> int:
    if not items:
        return 1
    return max(i.get("id", 0) for i in items) + 1


def _wa_out(doc: dict) -> dict:
    return {
        "id": doc.get("int_id"),
        "assignment_number": doc.get("assignment_number", ""),
        "assignment_name": doc.get("assignment_name", ""),
        "objective_id": doc.get("objective_id"),
        "operational_period_id": doc.get("operational_period_id"),
        "branch": doc.get("branch", ""),
        "division_group": doc.get("division_group", ""),
        "location": doc.get("location", ""),
        "location_facility_id": doc.get("location_facility_id", ""),
        "assignment_kind": doc.get("assignment_kind", "Ground"),
        "priority": doc.get("priority", "Normal"),
        "planning_status": doc.get("planning_status", "Draft"),
        "safety_status": doc.get("safety_status", "Unchecked"),
        "resource_status": doc.get("resource_status", "Unreviewed"),
        "description": doc.get("description", ""),
        "tactics_summary": doc.get("tactics_summary", ""),
        "special_instructions": doc.get("special_instructions", ""),
        "prepared_by": doc.get("prepared_by"),
        "approved_by": doc.get("approved_by"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "created_by": doc.get("created_by"),
        "updated_by": doc.get("updated_by"),
        "is_archived": bool(doc.get("is_archived", False)),
        "notes": doc.get("notes", ""),
        "resources": [_req_out(r) for r in doc.get("resources", [])],
        "hazards": [_hazard_out(h) for h in doc.get("hazards", [])],
        "comms": [_comms_out(c) for c in doc.get("comms", [])],
        "task_links": [_link_out(t) for t in doc.get("task_links", [])],
        "log_entries": [_log_out(l) for l in doc.get("log_entries", [])],
        "outputs": [_output_out(o) for o in doc.get("outputs", [])],
    }


def _req_out(r: dict) -> dict:
    return {
        "id": r.get("id"),
        "resource_type_id": r.get("resource_type_id"),
        "resource_type_text": r.get("resource_type_text", ""),
        "capability_id": r.get("capability_id"),
        "capability_text": r.get("capability_text", ""),
        "quantity_required": r.get("quantity_required", 1),
        "quantity_assigned": r.get("quantity_assigned", 0),
        "quantity_available": r.get("quantity_available", 0),
        "quantity_gap": r.get("quantity_gap", 0),
        "unit": r.get("unit", ""),
        "priority": r.get("priority", "Normal"),
        "source_note": r.get("source_note", ""),
        "logistics_request_id": r.get("logistics_request_id"),
        "notes": r.get("notes", ""),
        "created_at": r.get("created_at", ""),
        "updated_at": r.get("updated_at", ""),
        "assignments": [_ra_out(a) for a in r.get("assignments", [])],
    }


def _ra_out(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "resource_kind": a.get("resource_kind", ""),
        "resource_id": a.get("resource_id", ""),
        "display_name": a.get("display_name", ""),
        "status": a.get("status", "Planned"),
        "assigned_at": a.get("assigned_at"),
        "released_at": a.get("released_at"),
        "notes": a.get("notes", ""),
    }


def _hazard_out(h: dict) -> dict:
    return {
        "id": h.get("id"),
        "hazard_type_id": h.get("hazard_type_id"),
        "hazard_type_text": h.get("hazard_type_text", ""),
        "category": h.get("category", ""),
        "risk_level": h.get("risk_level", "Unknown"),
        "likelihood": h.get("likelihood", "Unknown"),
        "severity": h.get("severity", "Unknown"),
        "control_measure": h.get("control_measure", ""),
        "mitigation_text": h.get("mitigation_text", ""),
        "ppe_text": h.get("ppe_text", ""),
        "safety_message": h.get("safety_message", ""),
        "source": h.get("source", ""),
        "is_resolved": bool(h.get("is_resolved", False)),
        "notes": h.get("notes", ""),
        "created_at": h.get("created_at", ""),
        "updated_at": h.get("updated_at", ""),
    }


def _comms_out(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "channel_id": c.get("channel_id"),
        "channel_name": c.get("channel_name", ""),
        "function": c.get("function", ""),
        "zone": c.get("zone", ""),
        "channel_number": c.get("channel_number", ""),
        "rx_freq": c.get("rx_freq", ""),
        "rx_tone": c.get("rx_tone", ""),
        "tx_freq": c.get("tx_freq", ""),
        "tx_tone": c.get("tx_tone", ""),
        "mode": c.get("mode", ""),
        "remarks": c.get("remarks", ""),
        "is_primary": bool(c.get("is_primary", False)),
        "notes": c.get("notes", ""),
        "created_at": c.get("created_at", ""),
        "updated_at": c.get("updated_at", ""),
    }


def _link_out(t: dict) -> dict:
    return {
        "id": t.get("id"),
        "task_id": t.get("task_id"),
        "link_type": t.get("link_type", "Linked Existing"),
        "created_at": t.get("created_at", ""),
        "notes": t.get("notes", ""),
    }


def _log_out(l: dict) -> dict:
    return {
        "id": l.get("id"),
        "timestamp": l.get("timestamp", ""),
        "entry_type": l.get("entry_type", "Note"),
        "entry_text": l.get("entry_text", ""),
        "critical": bool(l.get("critical", False)),
        "entered_by": l.get("entered_by"),
    }


def _output_out(o: dict) -> dict:
    return {
        "id": o.get("id"),
        "output_type": o.get("output_type", ""),
        "status": o.get("status", "Not Started"),
        "generated_file_path": o.get("generated_file_path"),
        "generated_at": o.get("generated_at"),
        "generated_by": o.get("generated_by"),
        "notes": o.get("notes", ""),
    }


def _get_doc(incident_id: str, wa_id: int) -> dict:
    col = _col(incident_id)
    _ensure_int_ids(col)
    doc = col.find_one({"incident_id": incident_id, "int_id": wa_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Work assignment not found")
    return doc


# -------------------------------------------------------------------------
# Work assignment CRUD
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments")
def list_work_assignments(
    incident_id: str,
    search: Optional[str] = None,
    planning_status: Optional[str] = None,
    safety_status: Optional[str] = None,
    resource_status: Optional[str] = None,
    branch: Optional[str] = None,
    division_group: Optional[str] = None,
    op_period_id: Optional[int] = None,
    objective_id: Optional[str] = None,
    show_archived: bool = False,
) -> List[Dict[str, Any]]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    q: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if not show_archived:
        q["is_archived"] = {"$ne": True}
    if planning_status:
        q["planning_status"] = planning_status
    if safety_status:
        q["safety_status"] = safety_status
    if resource_status:
        q["resource_status"] = resource_status
    if branch:
        q["branch"] = branch
    if division_group:
        q["division_group"] = division_group
    if op_period_id is not None:
        q["operational_period_id"] = op_period_id
    if objective_id is not None:
        q["objective_id"] = objective_id
    docs = list(col.find(q, sort=[("updated_at", -1)]))
    if search:
        s = search.lower()
        docs = [d for d in docs if s in (d.get("assignment_name") or "").lower() or s in (d.get("assignment_number") or "").lower()]
    return [_wa_out(d) for d in docs]


@router.post("/incidents/{incident_id}/planning/work-assignments", status_code=201)
def create_work_assignment(incident_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    now = _utcnow()
    new_id = next_int_id(col)
    initial_outputs = [{"id": i + 1, "output_type": ot, "status": "Not Started"} for i, ot in enumerate(OUTPUT_TYPE_VALUES)]
    doc = {
        "_id": str(uuid.uuid4()),
        "int_id": new_id,
        "incident_id": incident_id,
        "assignment_number": body.get("assignment_number") or f"ST-{new_id}",
        "assignment_name": str(body.get("assignment_name") or ""),
        "objective_id": body.get("objective_id"),
        "operational_period_id": body.get("operational_period_id"),
        "branch": str(body.get("branch") or ""),
        "division_group": str(body.get("division_group") or ""),
        "location": str(body.get("location") or ""),
        "location_facility_id": str(body.get("location_facility_id") or ""),
        "assignment_kind": str(body.get("assignment_kind") or "Ground"),
        "priority": str(body.get("priority") or "Normal"),
        "planning_status": str(body.get("planning_status") or "Draft"),
        "safety_status": str(body.get("safety_status") or "Unchecked"),
        "resource_status": str(body.get("resource_status") or "Unreviewed"),
        "description": str(body.get("description") or ""),
        "tactics_summary": str(body.get("tactics_summary") or ""),
        "special_instructions": str(body.get("special_instructions") or ""),
        "prepared_by": body.get("prepared_by"),
        "approved_by": body.get("approved_by"),
        "created_at": now,
        "updated_at": now,
        "created_by": body.get("created_by"),
        "updated_by": body.get("updated_by"),
        "is_archived": False,
        "notes": str(body.get("notes") or ""),
        "resources": [],
        "hazards": [],
        "comms": [],
        "task_links": [],
        "log_entries": [],
        "outputs": initial_outputs,
    }
    col.insert_one(doc)
    return _wa_out(doc)


@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}")
def get_work_assignment(incident_id: str, wa_id: int) -> Dict[str, Any]:
    return _wa_out(_get_doc(incident_id, wa_id))


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}")
def update_work_assignment(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    updatable = {
        "assignment_number", "assignment_name", "objective_id", "operational_period_id",
        "branch", "division_group", "location", "location_facility_id", "assignment_kind", "priority",
        "planning_status", "safety_status", "resource_status", "description",
        "tactics_summary", "special_instructions", "prepared_by", "approved_by",
        "updated_by", "notes",
    }
    upd = {k: v for k, v in body.items() if k in updatable}
    if not upd:
        return get_work_assignment(incident_id, wa_id)
    upd["updated_at"] = _utcnow()
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": upd})
    return get_work_assignment(incident_id, wa_id)


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}/archive")
def archive_work_assignment(incident_id: str, wa_id: int) -> Dict[str, Any]:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"is_archived": True, "updated_at": _utcnow()}})
    return get_work_assignment(incident_id, wa_id)


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}/restore")
def restore_work_assignment(incident_id: str, wa_id: int) -> Dict[str, Any]:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"is_archived": False, "updated_at": _utcnow()}})
    return get_work_assignment(incident_id, wa_id)


@router.delete("/incidents/{incident_id}/planning/work-assignments/{wa_id}", status_code=204)
def delete_work_assignment(incident_id: str, wa_id: int) -> None:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"deleted": True}})


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/clone", status_code=201)
def clone_work_assignment(incident_id: str, wa_id: int) -> Dict[str, Any]:
    doc = _get_doc(incident_id, wa_id)
    body = {k: doc.get(k) for k in (
        "assignment_name", "objective_id", "operational_period_id", "branch", "division_group",
        "location", "location_facility_id", "assignment_kind", "priority", "planning_status", "safety_status",
        "resource_status", "description", "tactics_summary", "special_instructions", "notes",
    )}
    body["assignment_name"] = f"{doc.get('assignment_name', '')} (Copy)"
    body["assignment_number"] = ""
    body["planning_status"] = "Draft"
    return create_work_assignment(incident_id, body)


# -------------------------------------------------------------------------
# Status board
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignment-status-rows")
def list_status_rows(incident_id: str) -> List[Dict[str, Any]]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id, "is_archived": {"$ne": True}, "deleted": {"$ne": True}},
                         sort=[("updated_at", -1)]))
    return [{
        "id": d.get("int_id"),
        "assignment_number": d.get("assignment_number", ""),
        "assignment_name": d.get("assignment_name", ""),
        "planning_status": d.get("planning_status", "Draft"),
        "resource_status": d.get("resource_status", "Unreviewed"),
        "safety_status": d.get("safety_status", "Unchecked"),
    } for d in docs]


# -------------------------------------------------------------------------
# Resources (requirements + actual assignments) — embedded
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/resources")
def list_resources(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    return [_req_out(r) for r in _get_doc(incident_id, wa_id).get("resources", [])]


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/resources", status_code=201)
def add_resource(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    now = _utcnow()
    qty = max(1, int(body.get("quantity_required") or 1))
    new_id = _next_sub_id(doc.get("resources", []))
    req = {
        "id": new_id,
        "resource_type_id": body.get("resource_type_id"),
        "resource_type_text": str(body.get("resource_type_text") or ""),
        "capability_id": body.get("capability_id"),
        "capability_text": str(body.get("capability_text") or ""),
        "quantity_required": qty,
        "quantity_assigned": 0,
        "quantity_available": 0,
        "quantity_gap": qty,
        "unit": str(body.get("unit") or ""),
        "priority": str(body.get("priority") or "Normal"),
        "source_note": str(body.get("source_note") or ""),
        "logistics_request_id": body.get("logistics_request_id"),
        "notes": str(body.get("notes") or ""),
        "created_at": now,
        "updated_at": now,
        "assignments": [],
    }
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"resources": req}})
    return _req_out(req)


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}/resources/{req_id}")
def update_resource(incident_id: str, wa_id: int, req_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    resources = doc.get("resources", [])
    updatable = {"resource_type_id", "resource_type_text", "capability_id", "capability_text",
                 "quantity_required", "quantity_assigned", "quantity_available", "quantity_gap",
                 "unit", "priority", "source_note", "logistics_request_id", "notes"}
    for i, r in enumerate(resources):
        if r.get("id") == req_id:
            for k in updatable:
                if k in body:
                    resources[i][k] = body[k]
            resources[i]["updated_at"] = _utcnow()
            # Recalculate gap
            gap = max(int(resources[i].get("quantity_required", 1)) - int(resources[i].get("quantity_assigned", 0)), 0)
            resources[i]["quantity_gap"] = gap
            col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"resources": resources}})
            return _req_out(resources[i])
    raise HTTPException(status_code=404, detail="Resource requirement not found")


@router.delete("/incidents/{incident_id}/planning/work-assignments/{wa_id}/resources/{req_id}", status_code=204)
def remove_resource(incident_id: str, wa_id: int, req_id: int) -> None:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$pull": {"resources": {"id": req_id}}})


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/resources/{req_id}/assignments", status_code=201)
def assign_resource(incident_id: str, wa_id: int, req_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    resources = doc.get("resources", [])
    for i, r in enumerate(resources):
        if r.get("id") == req_id:
            new_id = _next_sub_id(r.get("assignments", []))
            assignment = {
                "id": new_id,
                "resource_kind": str(body.get("resource_kind") or ""),
                "resource_id": str(body.get("resource_id") or ""),
                "display_name": str(body.get("display_name") or ""),
                "status": "Planned",
                "assigned_at": _utcnow(),
                "released_at": None,
                "notes": str(body.get("notes") or ""),
            }
            resources[i].setdefault("assignments", []).append(assignment)
            resources[i]["quantity_assigned"] = len(resources[i]["assignments"])
            resources[i]["quantity_gap"] = max(int(resources[i].get("quantity_required", 1)) - resources[i]["quantity_assigned"], 0)
            resources[i]["updated_at"] = _utcnow()
            col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"resources": resources}})
            return _ra_out(assignment)
    raise HTTPException(status_code=404, detail="Resource requirement not found")


# -------------------------------------------------------------------------
# Hazards — embedded
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/hazards")
def list_hazards(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    return [_hazard_out(h) for h in _get_doc(incident_id, wa_id).get("hazards", [])]


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/hazards", status_code=201)
def add_hazard(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    now = _utcnow()
    new_id = _next_sub_id(doc.get("hazards", []))
    hazard = {
        "id": new_id,
        "hazard_type_id": body.get("hazard_type_id"),
        "hazard_type_text": str(body.get("hazard_type_text") or ""),
        "category": str(body.get("category") or ""),
        "risk_level": str(body.get("risk_level") or "Unknown"),
        "likelihood": str(body.get("likelihood") or "Unknown"),
        "severity": str(body.get("severity") or "Unknown"),
        "control_measure": str(body.get("control_measure") or ""),
        "mitigation_text": str(body.get("mitigation_text") or ""),
        "ppe_text": str(body.get("ppe_text") or ""),
        "safety_message": str(body.get("safety_message") or ""),
        "source": str(body.get("source") or ""),
        "is_resolved": False,
        "notes": str(body.get("notes") or ""),
        "created_at": now,
        "updated_at": now,
    }
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"hazards": hazard}})
    return _hazard_out(hazard)


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}/hazards/{hazard_id}")
def update_hazard(incident_id: str, wa_id: int, hazard_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    hazards = doc.get("hazards", [])
    updatable = {"hazard_type_id", "hazard_type_text", "category", "risk_level", "likelihood",
                 "severity", "control_measure", "mitigation_text", "ppe_text", "safety_message",
                 "source", "is_resolved", "notes"}
    for i, h in enumerate(hazards):
        if h.get("id") == hazard_id:
            for k in updatable:
                if k in body:
                    hazards[i][k] = body[k]
            hazards[i]["updated_at"] = _utcnow()
            col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"hazards": hazards}})
            return _hazard_out(hazards[i])
    raise HTTPException(status_code=404, detail="Hazard not found")


@router.delete("/incidents/{incident_id}/planning/work-assignments/{wa_id}/hazards/{hazard_id}", status_code=204)
def remove_hazard(incident_id: str, wa_id: int, hazard_id: int) -> None:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$pull": {"hazards": {"id": hazard_id}}})


# -------------------------------------------------------------------------
# Comms — embedded
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/comms")
def list_comms(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    doc = _get_doc(incident_id, wa_id)
    comms = sorted(doc.get("comms", []), key=lambda c: (-int(bool(c.get("is_primary"))), c.get("id", 0)))
    return [_comms_out(c) for c in comms]


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/comms", status_code=201)
def add_comms(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    now = _utcnow()
    new_id = _next_sub_id(doc.get("comms", []))
    comm = {
        "id": new_id,
        "channel_id": body.get("channel_id"),
        "channel_name": str(body.get("channel_name") or ""),
        "function": str(body.get("function") or ""),
        "zone": str(body.get("zone") or ""),
        "channel_number": str(body.get("channel_number") or ""),
        "rx_freq": str(body.get("rx_freq") or ""),
        "rx_tone": str(body.get("rx_tone") or ""),
        "tx_freq": str(body.get("tx_freq") or ""),
        "tx_tone": str(body.get("tx_tone") or ""),
        "mode": str(body.get("mode") or ""),
        "remarks": str(body.get("remarks") or ""),
        "is_primary": bool(body.get("is_primary", False)),
        "notes": str(body.get("notes") or ""),
        "created_at": now,
        "updated_at": now,
    }
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"comms": comm}})
    return _comms_out(comm)


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}/comms/{comms_id}")
def update_comms(incident_id: str, wa_id: int, comms_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    comms_list = doc.get("comms", [])
    updatable = {"channel_name", "function", "zone", "channel_number", "rx_freq", "rx_tone",
                 "tx_freq", "tx_tone", "mode", "remarks", "is_primary", "notes"}
    for i, c in enumerate(comms_list):
        if c.get("id") == comms_id:
            for k in updatable:
                if k in body:
                    comms_list[i][k] = body[k]
            comms_list[i]["updated_at"] = _utcnow()
            col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"comms": comms_list}})
            return _comms_out(comms_list[i])
    raise HTTPException(status_code=404, detail="Comms channel not found")


@router.delete("/incidents/{incident_id}/planning/work-assignments/{wa_id}/comms/{comms_id}", status_code=204)
def remove_comms(incident_id: str, wa_id: int, comms_id: int) -> None:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$pull": {"comms": {"id": comms_id}}})


# -------------------------------------------------------------------------
# Task links — embedded
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/task-links")
def list_task_links(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    return [_link_out(t) for t in _get_doc(incident_id, wa_id).get("task_links", [])]


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/task-links", status_code=201)
def link_task(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    task_id = int(body.get("task_id") or 0)
    existing = [t for t in doc.get("task_links", []) if t.get("task_id") == task_id]
    if existing:
        return None
    new_id = _next_sub_id(doc.get("task_links", []))
    link = {
        "id": new_id,
        "task_id": task_id,
        "link_type": str(body.get("link_type") or "Linked Existing"),
        "created_at": _utcnow(),
        "notes": str(body.get("notes") or ""),
    }
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"task_links": link}})
    return _link_out(link)


@router.delete("/incidents/{incident_id}/planning/work-assignments/{wa_id}/task-links/{link_id}", status_code=204)
def unlink_task(incident_id: str, wa_id: int, link_id: int) -> None:
    col = _col(incident_id)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$pull": {"task_links": {"id": link_id}}})


def _agency_requests_col(incident_id: str):
    return DatabaseManager().get_incident_db(incident_id)[IncidentCollections.LIAISON_AGENCY_REQUESTS]


def _agency_request_link_out(link: dict) -> dict:
    return {
        "id": link.get("id"),
        "agency_request_id": link.get("agency_request_id"),
        "created_at": link.get("created_at", ""),
    }


@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/agency-requests")
def list_agency_request_links(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    doc = _get_doc(incident_id, wa_id)
    links = doc.get("agency_request_links", [])
    req_col = _agency_requests_col(incident_id)
    result = []
    for link in links:
        req = req_col.find_one({"incident_id": incident_id, "int_id": link.get("agency_request_id")})
        result.append({
            "link_id": link.get("id"),
            "agency_request_id": link.get("agency_request_id"),
            "agency_id": req.get("agency_id") if req else None,
            "request_summary": (req.get("description") or req.get("request_type") or "") if req else "",
            "status": req.get("status", "") if req else "",
            "created_at": link.get("created_at", ""),
        })
    return result


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/agency-requests", status_code=201)
def link_agency_request(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    agency_request_id = int(body.get("agency_request_id") or 0)
    existing = [l for l in doc.get("agency_request_links", []) if l.get("agency_request_id") == agency_request_id]
    if existing:
        return None
    req_col = _agency_requests_col(incident_id)
    req = req_col.find_one({"incident_id": incident_id, "int_id": agency_request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Agency request not found")
    new_id = _next_sub_id(doc.get("agency_request_links", []))
    link = {"id": new_id, "agency_request_id": agency_request_id, "created_at": _utcnow()}
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"agency_request_links": link}})
    reverse_link = {"id": new_id, "work_assignment_id": wa_id, "wa_link_id": new_id, "created_at": _utcnow()}
    req_col.update_one(
        {"incident_id": incident_id, "int_id": agency_request_id},
        {"$push": {"strategy_links": reverse_link}},
    )
    return _agency_request_link_out(link)


@router.delete("/incidents/{incident_id}/planning/work-assignments/{wa_id}/agency-requests/{link_id}", status_code=204)
def unlink_agency_request(incident_id: str, wa_id: int, link_id: int) -> None:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    links = doc.get("agency_request_links", [])
    target = next((l for l in links if l.get("id") == link_id), None)
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$pull": {"agency_request_links": {"id": link_id}}})
    if target:
        req_col = _agency_requests_col(incident_id)
        req_col.update_one(
            {"incident_id": incident_id, "int_id": target.get("agency_request_id")},
            {"$pull": {"strategy_links": {"wa_link_id": link_id, "work_assignment_id": wa_id}}},
        )


@router.get("/incidents/{incident_id}/planning/tasks/{task_id}/work-assignments")
def list_strategies_for_task(incident_id: str, task_id: int) -> List[Dict[str, Any]]:
    col = _col(incident_id)
    _ensure_int_ids(col)
    docs = list(col.find({"incident_id": incident_id, "task_links.task_id": task_id, "deleted": {"$ne": True}}))
    result = []
    for d in docs:
        for link in d.get("task_links", []):
            if link.get("task_id") == task_id:
                result.append({
                    "id": d.get("int_id"),
                    "assignment_number": d.get("assignment_number", ""),
                    "assignment_name": d.get("assignment_name", ""),
                    "objective_id": d.get("objective_id"),
                    "planning_status": d.get("planning_status", "Draft"),
                    "link_id": link.get("id"),
                    "link_type": link.get("link_type", ""),
                })
    return result


# -------------------------------------------------------------------------
# Log entries — embedded
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/log")
def list_log(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    doc = _get_doc(incident_id, wa_id)
    entries = sorted(doc.get("log_entries", []), key=lambda x: x.get("timestamp", ""), reverse=True)
    return [_log_out(e) for e in entries]


@router.post("/incidents/{incident_id}/planning/work-assignments/{wa_id}/log", status_code=201)
def add_log_entry(incident_id: str, wa_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    new_id = _next_sub_id(doc.get("log_entries", []))
    entry = {
        "id": new_id,
        "timestamp": body.get("timestamp") or _utcnow(),
        "entry_type": str(body.get("entry_type") or "Note"),
        "entry_text": str(body.get("entry_text") or ""),
        "critical": bool(body.get("critical", False)),
        "entered_by": body.get("entered_by"),
    }
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"log_entries": entry}})
    return _log_out(entry)


# -------------------------------------------------------------------------
# Output status — embedded
# -------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/planning/work-assignments/{wa_id}/outputs")
def list_outputs(incident_id: str, wa_id: int) -> List[Dict[str, Any]]:
    return [_output_out(o) for o in _get_doc(incident_id, wa_id).get("outputs", [])]


@router.patch("/incidents/{incident_id}/planning/work-assignments/{wa_id}/outputs/{output_type}")
def update_output(incident_id: str, wa_id: int, output_type: str, body: Dict[str, Any]) -> Dict[str, Any]:
    col = _col(incident_id)
    doc = _get_doc(incident_id, wa_id)
    outputs = doc.get("outputs", [])
    for i, o in enumerate(outputs):
        if o.get("output_type") == output_type:
            if "status" in body:
                outputs[i]["status"] = body["status"]
            if "notes" in body:
                outputs[i]["notes"] = body["notes"]
            col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$set": {"outputs": outputs}})
            return _output_out(outputs[i])
    # Not found — create it
    new_id = _next_sub_id(outputs)
    entry = {"id": new_id, "output_type": output_type, "status": body.get("status", "Not Started"), "notes": body.get("notes", "")}
    col.update_one({"incident_id": incident_id, "int_id": wa_id}, {"$push": {"outputs": entry}})
    return _output_out(entry)
