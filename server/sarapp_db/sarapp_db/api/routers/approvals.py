"""Approval instances, records, and workflow API.

The workflow logic (who can act on a step, escalation when a seat is
vacant, activating/advancing the chain, writing terminal status back to the
entity) lives here rather than in any one client, so every client (desktop,
web) drives the same approval chains through the same endpoints instead of
each re-implementing escalation/advancement locally.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.notification_service import emit_notification

from .incident_org import _assignments_from_position, _org_repo

router = APIRouter()
logger = logging.getLogger(__name__)

# Human-readable name per entity_type, for notification text.
_ENTITY_LABELS: dict[str, str] = {
    "ics_205": "the ICS-205 Communications Plan",
    "ics_206": "the ICS-206 Medical Plan",
    "iwi_report": "an IWI report",
    "iap": "the IAP",
    "interview": "an interview record",
}

_VALID_ACTIONS = {"approved", "rejected", "acknowledged"}

# Maps entity_type -> (collection_name, id_field) so the service can write
# approval_status back to the entity's own record when the chain completes.
# Extend this as new approvable entity types are wired up.
_ENTITY_COLLECTIONS: dict[str, tuple[str, str]] = {
    "ics_205": (IncidentCollections.COMMUNICATIONS_PLAN, "plan_id"),
    # One approval chain per ICS-206 version; entity_id is the medical_plan `plan_id`.
    "ics_206": (IncidentCollections.MEDICAL_PLAN, "plan_id"),
    "iwi_report": (IncidentCollections.IWI_REPORTS, "id"),
    "iap": (IncidentCollections.FORMS, "id"),
}


# ---------------------------------------------------------------------------
# Spec layer — which steps an entity type's approval chain has, and who can
# act on each one. Canonical here; clients don't keep their own copy.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalStepSpec:
    step_id: str
    label: str
    role: str
    kind: str = "sequential"  # "sequential" | "parallel" | "ack"
    acceptable_types: tuple[str, ...] = ()
    order: int = 0


@dataclass(frozen=True)
class ApprovalSpec:
    entity_type: str
    steps: tuple[ApprovalStepSpec, ...]
    precondition: Optional[Callable[[str, str], bool]] = None


def _iap_precondition(_incident_id: str, _entity_id: str) -> bool:
    # IAP sign-off requires every constituent document to be approved first.
    # Not wired up yet (no readiness aggregation exists) — fail closed.
    return False


_SPECS: dict[str, ApprovalSpec] = {
    "ics_205": ApprovalSpec(
        entity_type="ics_205",
        steps=(
            ApprovalStepSpec(
                step_id="coml_signoff",
                label="Communications Unit Leader",
                role="Communications Unit Leader",
                kind="sequential",
                acceptable_types=("primary", "deputy", "trainee"),
                order=0,
            ),
        ),
    ),
    "ics_206": ApprovalSpec(
        entity_type="ics_206",
        steps=(
            ApprovalStepSpec(
                step_id="medl_approval",
                label="Medical Unit Leader",
                role="Medical Unit Leader",
                kind="sequential",
                acceptable_types=("primary", "deputy", "trainee"),
                order=0,
            ),
            ApprovalStepSpec(
                step_id="sofr_approval",
                label="Safety Officer",
                role="Safety Officer",
                kind="sequential",
                acceptable_types=("primary", "deputy"),
                order=1,
            ),
        ),
    ),
    "iwi_report": ApprovalSpec(
        entity_type="iwi_report",
        # Safety Officer and IC sign in parallel — both required, order doesn't matter.
        steps=(
            ApprovalStepSpec(
                step_id="sofr_signoff",
                label="Safety Officer",
                role="Safety Officer",
                kind="parallel",
                acceptable_types=("primary", "deputy"),
                order=0,
            ),
            ApprovalStepSpec(
                step_id="ic_signoff",
                label="Incident Commander",
                role="Incident Commander",
                kind="parallel",
                acceptable_types=("primary", "deputy"),
                order=0,
            ),
        ),
    ),
    "iap": ApprovalSpec(
        entity_type="iap",
        steps=(
            ApprovalStepSpec(
                step_id="ic_approval",
                label="Incident Commander / Unified Command",
                role="Incident Commander",
                kind="sequential",
                acceptable_types=("primary", "deputy"),
                order=0,
            ),
        ),
        precondition=_iap_precondition,
    ),
    "interview": ApprovalSpec(
        entity_type="interview",
        # Acknowledgment-only: confirms the interview was conducted/documented.
        steps=(
            ApprovalStepSpec(
                step_id="interviewer_ack",
                label="Interviewer",
                role="",
                kind="ack",
                acceptable_types=(),
                order=0,
            ),
        ),
    ),
}

# ICS standard escalation chains. Key: position title (must match org chart
# position titles exactly). Value: ordered fallback titles to try if the
# primary is vacant. Walked until a filled position is found.
_ESCALATION: dict[str, list[str]] = {
    "Incident Commander": [],
    "Deputy Incident Commander": ["Incident Commander"],
    "Safety Officer": ["Incident Commander"],
    "Public Information Officer": ["Incident Commander"],
    "Liaison Officer": ["Incident Commander"],
    "Operations Section Chief": ["Incident Commander"],
    "Deputy Operations Section Chief": ["Operations Section Chief", "Incident Commander"],
    "Staging Area Manager": ["Operations Section Chief", "Incident Commander"],
    "Planning Section Chief": ["Incident Commander"],
    "Resources Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Situation Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Documentation Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Demobilization Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Logistics Section Chief": ["Incident Commander"],
    "Service Branch Director": ["Logistics Section Chief", "Incident Commander"],
    "Support Branch Director": ["Logistics Section Chief", "Incident Commander"],
    "Communications Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Medical Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Food Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Supply Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Facilities Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Ground Support Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Finance/Administration Section Chief": ["Incident Commander"],
    "Time Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
    "Procurement Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
    "Compensation/Claims Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
    "Cost Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
}


def _escalation_chain(role: str) -> list[str]:
    return [role] + _ESCALATION.get(role, ["Incident Commander"])


def _resolve_actor(incident_id: str, role: str) -> tuple[Optional[int], Optional[str]]:
    """Walk the escalation chain for `role`, returning the first filled position's actor."""
    repo = _org_repo(incident_id)
    positions = repo.find_many({})
    for candidate_role in _escalation_chain(role):
        position = next((p for p in positions if p.get("title") == candidate_role), None)
        if position is None:
            continue
        assignments = [
            a for a in _assignments_from_position(position) if a.get("end_time") is None
        ]
        if assignments:
            return assignments[0]["person_record"], candidate_role
    return None, None


def _assignment_type_for(incident_id: str, person_record: int) -> str:
    repo = _org_repo(incident_id)
    for position in repo.find_many({}):
        for assignment in _assignments_from_position(position):
            if assignment.get("end_time") is None and assignment.get("person_record") == person_record:
                return assignment.get("assignment_type", "primary")
    return "primary"


def _held_roles(incident_id: str, person_record: int) -> set[str]:
    repo = _org_repo(incident_id)
    roles: set[str] = set()
    for position in repo.find_many({}):
        for assignment in _assignments_from_position(position):
            if assignment.get("end_time") is None and assignment.get("person_record") == person_record:
                roles.add(position.get("title", ""))
    return roles


class ApprovalInstancesRepository(BaseRepository):
    collection_name = IncidentCollections.APPROVAL_INSTANCES
    soft_deletes = False


class ApprovalRecordsRepository(BaseRepository):
    collection_name = IncidentCollections.APPROVAL_RECORDS
    soft_deletes = False


def _instances_repo(incident_id: str) -> ApprovalInstancesRepository:
    return ApprovalInstancesRepository(get_incident_db(incident_id))


def _records_repo(incident_id: str) -> ApprovalRecordsRepository:
    return ApprovalRecordsRepository(get_incident_db(incident_id))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _strip_id(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SaveRecordRequest(BaseModel):
    entity_type: str
    entity_id: str
    step_id: str
    actor_id: str
    role_at_time: str
    assignment_type_at_time: str
    action: str
    timestamp: Optional[str] = None
    notes: Optional[str] = None


class SignRequest(BaseModel):
    step_id: str
    actor_id: int
    action: str
    notes: Optional[str] = None


class EntityStatusRequest(BaseModel):
    approval_status: str


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/approvals/instances/{entity_type}/{entity_id}")
def get_instance(incident_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    repo = _instances_repo(incident_id)
    doc = repo.find_one({
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
    })
    if not doc:
        raise HTTPException(404, "Approval instance not found")
    return _strip_id(doc)


def _save_instance(incident_id: str, instance: dict[str, Any]) -> None:
    repo = _instances_repo(incident_id)
    query = {
        "incident_id": incident_id,
        "entity_type": instance["entity_type"],
        "entity_id": instance["entity_id"],
    }
    # Atomic upsert by compound key (not by `_id`) — not expressible via
    # BaseRepository's generic methods, so we drop to the raw collection
    # and broadcast the change ourselves, mirroring update_one's pattern.
    repo._col.replace_one(query, {**instance, **query}, upsert=True)
    doc = repo._col.find_one(query)
    if doc:
        repo._broadcast("updated", doc["_id"], doc)


# ---------------------------------------------------------------------------
# Workflow — start a chain, sign a step, advance/close it out
# ---------------------------------------------------------------------------

def _get_spec(entity_type: str) -> ApprovalSpec:
    spec = _SPECS.get(entity_type)
    if spec is None:
        raise HTTPException(400, f"No approval spec registered for: {entity_type}")
    return spec


def _new_step(step: ApprovalStepSpec) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "role": step.role,
        "label": step.label,
        "kind": step.kind,
        "order": step.order,
        "status": "waiting",
        "resolved_actor_id": None,
        "resolved_role": None,
        "activated_at": None,
        "completed_at": None,
    }


def _activate_step(incident_id: str, entity_type: str, entity_id: str, step: dict[str, Any]) -> None:
    step["status"] = "active"
    step["activated_at"] = _utc_now()
    # "flexible" steps have no role to resolve — they wait for someone to be
    # picked explicitly via the assign-step endpoint below. A role-based step
    # that resolves to nobody (role vacant, and so is everything above it up
    # to the Incident Commander) ends up in the same waiting-for-a-pick state.
    if step["kind"] not in ("ack", "flexible") and step["role"]:
        actor_id, resolved_role = _resolve_actor(incident_id, step["role"])
        step["resolved_actor_id"] = actor_id
        step["resolved_role"] = resolved_role
        if actor_id is not None:
            _notify_step_awaiting(incident_id, entity_type, entity_id, step)


def _notify_step_awaiting(incident_id: str, entity_type: str, entity_id: str, step: dict[str, Any]) -> None:
    """Tell the resolved actor their signature is needed, via the shared
    server-side notification system (persisted + pushed to mobile) — not a
    client-local popup, so it reaches them no matter which app they're on."""
    label = _ENTITY_LABELS.get(entity_type, entity_type)
    try:
        emit_notification(
            incident_id,
            title="Approval needed",
            message=f"{step['label']} sign-off is needed on {label}.",
            source_type="approval_step",
            source_id=f"{entity_type}:{entity_id}:{step['step_id']}",
            source_label=step["label"],
            severity="priority",
            category="administrative",
            audience_user_id=step["resolved_actor_id"],
        )
    except Exception:
        logger.exception(
            "Failed to notify person_record=%s of approval step %s on %s/%s",
            step["resolved_actor_id"], step["step_id"], entity_type, entity_id,
        )


def _activate_next_steps(incident_id: str, instance: dict[str, Any]) -> None:
    waiting = [s for s in instance["steps"] if s["status"] == "waiting"]
    if not waiting:
        return
    min_order = min(s["order"] for s in waiting)
    for step in waiting:
        if step["order"] == min_order:
            _activate_step(incident_id, instance["entity_type"], instance["entity_id"], step)


def _advance(incident_id: str, instance: dict[str, Any], now: str) -> None:
    active_remaining = [s for s in instance["steps"] if s["status"] == "active"]
    waiting_remaining = [s for s in instance["steps"] if s["status"] == "waiting"]
    if not active_remaining and not waiting_remaining:
        instance["status"] = "approved"
        instance["completed_at"] = now
    elif not active_remaining:
        _activate_next_steps(incident_id, instance)


def _write_status_to_entity(incident_id: str, instance: dict[str, Any]) -> None:
    if instance["status"] not in ("approved", "rejected"):
        return
    entry = _ENTITY_COLLECTIONS.get(instance["entity_type"])
    if entry is None:
        return
    collection_name, id_field = entry

    class _EntityRepository(BaseRepository):
        pass

    _EntityRepository.collection_name = collection_name
    _EntityRepository.soft_deletes = False
    repo = _EntityRepository(get_incident_db(incident_id))
    existing = repo.find_one({"incident_id": incident_id, id_field: instance["entity_id"]})
    if existing is not None:
        repo.update_one(existing["_id"], {"approval_status": instance["status"]})


@router.post("/{incident_id}/approvals/{entity_type}/{entity_id}/start")
def start_instance(incident_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    spec = _get_spec(entity_type)
    if spec.precondition and not spec.precondition(incident_id, entity_id):
        raise HTTPException(
            400, "Preconditions not met — not all required approvals are complete."
        )
    instance: dict[str, Any] = {
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "status": "pending",
        "steps": [_new_step(s) for s in spec.steps],
        "started_at": _utc_now(),
        "completed_at": None,
    }
    _activate_next_steps(incident_id, instance)
    _save_instance(incident_id, instance)
    return instance


@router.post("/{incident_id}/approvals/{entity_type}/{entity_id}/sign")
def sign_instance(
    incident_id: str, entity_type: str, entity_id: str, body: SignRequest
) -> dict[str, Any]:
    if body.action not in _VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action: {body.action}")
    repo = _instances_repo(incident_id)
    instance = repo.find_one(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id}
    )
    if instance is None:
        raise HTTPException(404, "Approval instance not found")
    step = next((s for s in instance["steps"] if s["step_id"] == body.step_id), None)
    if step is None:
        raise HTTPException(404, f"Step not found: {body.step_id}")
    if step["status"] != "active":
        raise HTTPException(400, f"Step is not active: {body.step_id} ({step['status']})")

    assignment_type = _assignment_type_for(incident_id, body.actor_id)
    if step["kind"] != "ack":
        if step.get("resolved_actor_id") is None:
            raise HTTPException(
                400, "Nobody is assigned to this step yet — assign someone before signing."
            )
        if step["resolved_actor_id"] != body.actor_id:
            raise HTTPException(403, "You are not able to act on this approval step.")
        spec = _SPECS.get(entity_type)
        spec_step = next((s for s in (spec.steps if spec else ()) if s.step_id == body.step_id), None)
        if spec_step and spec_step.acceptable_types and assignment_type not in spec_step.acceptable_types:
            raise HTTPException(403, "You are not able to act on this approval step.")

    now = _utc_now()
    step["status"] = "completed"
    step["completed_at"] = now

    records_repo = _records_repo(incident_id)
    records_repo.insert_one({
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "step_id": body.step_id,
        "actor_id": str(body.actor_id),
        "role_at_time": step.get("resolved_role") or step.get("role", ""),
        "assignment_type_at_time": assignment_type,
        "action": body.action,
        "timestamp": now,
        "notes": body.notes,
    })

    if body.action == "rejected":
        instance["status"] = "rejected"
        instance["completed_at"] = now
    else:
        _advance(incident_id, instance, now)

    _save_instance(incident_id, instance)
    _write_status_to_entity(incident_id, instance)
    return _strip_id(instance)


class AssignStepRequest(BaseModel):
    step_id: str
    actor_id: int


@router.post("/{incident_id}/approvals/{entity_type}/{entity_id}/assign-step")
def assign_step(
    incident_id: str, entity_type: str, entity_id: str, body: AssignStepRequest
) -> dict[str, Any]:
    """Manually pick who should act on a step nobody is resolved for yet —
    either a "flexible" step by design, or a role-based step whose whole
    chain of command up to the Incident Commander came up vacant. Usable any
    time the step is active and unresolved, not just at start/sign."""
    repo = _instances_repo(incident_id)
    instance = repo.find_one(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id}
    )
    if instance is None:
        raise HTTPException(404, "Approval instance not found")
    step = next((s for s in instance["steps"] if s["step_id"] == body.step_id), None)
    if step is None:
        raise HTTPException(404, f"Step not found: {body.step_id}")
    if step["status"] != "active":
        raise HTTPException(400, f"Step is not active: {body.step_id} ({step['status']})")
    if step.get("resolved_actor_id") is not None:
        raise HTTPException(400, "This step already has someone assigned.")
    step["resolved_actor_id"] = body.actor_id
    step["resolved_role"] = "Manually assigned"
    _save_instance(incident_id, instance)
    _notify_step_awaiting(incident_id, entity_type, entity_id, step)
    return _strip_id(instance)


# ---------------------------------------------------------------------------
# Entity status writeback
# ---------------------------------------------------------------------------

@router.patch("/{incident_id}/approvals/entity-status/{entity_type}/{entity_id}")
def update_entity_status(
    incident_id: str, entity_type: str, entity_id: str, body: EntityStatusRequest
) -> dict[str, Any]:
    entry = _ENTITY_COLLECTIONS.get(entity_type)
    if entry is None:
        raise HTTPException(400, f"Unknown entity type: {entity_type}")
    collection_name, id_field = entry

    class _EntityRepository(BaseRepository):
        pass

    _EntityRepository.collection_name = collection_name
    _EntityRepository.soft_deletes = False
    repo = _EntityRepository(get_incident_db(incident_id))
    existing = repo.find_one({"incident_id": incident_id, id_field: entity_id})
    if existing is None:
        raise HTTPException(404, f"{entity_type} {entity_id} not found")
    repo.update_one(existing["_id"], {"approval_status": body.approval_status})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@router.post("/{incident_id}/approvals/records", status_code=201)
def save_record(incident_id: str, body: SaveRecordRequest) -> dict[str, Any]:
    if body.action not in _VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action: {body.action}")
    repo = _records_repo(incident_id)
    repo.insert_one({
        "incident_id": incident_id,
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "step_id": body.step_id,
        "actor_id": body.actor_id,
        "role_at_time": body.role_at_time,
        "assignment_type_at_time": body.assignment_type_at_time,
        "action": body.action,
        "timestamp": body.timestamp or _utc_now(),
        "notes": body.notes,
    })
    return {"ok": True}


@router.get("/{incident_id}/approvals/records")
def get_records(
    incident_id: str,
    entity_type: str,
    entity_id: str,
) -> list[dict[str, Any]]:
    repo = _records_repo(incident_id)
    docs = repo.find_many(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id},
        sort=[("timestamp", 1)],
    )
    return [_strip_id(d) for d in docs]


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/approvals/pending/{person_record}")
def pending_for_person(incident_id: str, person_record: int) -> list[dict[str, Any]]:
    """Active steps where this person is the resolved actor, or holds the step's role."""
    roles = _held_roles(incident_id, person_record)
    repo = _instances_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id, "status": "pending"})
    results: list[dict[str, Any]] = []
    for doc in docs:
        for step in doc.get("steps", []):
            if step.get("status") != "active":
                continue
            resolved = step.get("resolved_actor_id")
            role = step.get("role", "")
            if resolved == person_record or role in roles:
                results.append({
                    "entity_type": doc["entity_type"],
                    "entity_id": doc["entity_id"],
                    "step_id": step.get("step_id"),
                    "label": step.get("label"),
                    "role": role,
                    "resolved_actor_id": resolved,
                    "activated_at": step.get("activated_at"),
                })
    return results
