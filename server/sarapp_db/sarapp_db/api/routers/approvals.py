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

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.notification_service import emit_notification

from .incident_org import _assignments_from_position, _org_repo, _person_name

router = APIRouter()
logger = logging.getLogger(__name__)

# Human-readable name per entity_type, for notification text.
_ENTITY_LABELS: dict[str, str] = {
    "ics_205": "the ICS-205 Communications Plan",
    "ics_206": "the ICS-206 Medical Plan",
    "iwi_report": "an IWI report",
    "iap": "the IAP",
}

_VALID_ACTIONS = {"approved", "rejected", "acknowledged"}

# Maps entity_type -> (collection_name, id_field, status_field) so the service can write
# approval_status back to the entity's own record when the chain completes.
# Extend this as new approvable entity types are wired up.
_ENTITY_COLLECTIONS: dict[str, tuple[str, str, str]] = {
    "ics_205": (IncidentCollections.COMMUNICATIONS_PLAN, "plan_id", "approval_status"),
    # One approval chain per ICS-206 version; entity_id is the medical_plan `plan_id`.
    "ics_206": (IncidentCollections.MEDICAL_PLAN, "plan_id", "approval_status"),
    "iwi_report": (IncidentCollections.IWI_REPORTS, "id", "approval_status"),
    "iap": (IncidentCollections.IAP_PACKAGES, "op_number", "status"),
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


def _iap_precondition(incident_id: str, entity_id: str) -> bool:
    class _IAPRepository(BaseRepository):
        collection_name = IncidentCollections.IAP_PACKAGES
        soft_deletes = False

    try:
        op_number = int(entity_id)
    except ValueError:
        return False
    package = _IAPRepository(get_incident_db(incident_id)).find_one(
        {"incident_id": incident_id, "op_number": op_number}
    )
    forms = (package or {}).get("forms") or []
    return bool(forms) and all(str(form.get("status") or "").lower() == "approved" for form in forms)


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


class StartRequest(BaseModel):
    # step_id -> person_record the submitter confirmed or chose, for whatever
    # step(s) are about to activate. Omitting a step_id falls back to normal
    # role resolution for that step.
    assign_actors: dict[str, int] = {}


class SignRequest(BaseModel):
    step_id: str
    actor_id: Optional[int] = None
    session_id: Optional[str] = None
    action: str
    notes: Optional[str] = None
    # Same idea as StartRequest.assign_actors, for whatever step(s) activate
    # as a result of this sign.
    assign_actors: dict[str, int] = {}


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
    payload = {key: value for key, value in instance.items() if key != "_id"}
    repo.upsert_one(query, {**payload, **query})


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


def _resolve_step_actor(incident_id: str, step: dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
    """What the engine would pick for this step on its own, before any
    submitter override — the escalation chain's automatic answer."""
    if step["kind"] in ("ack", "flexible") or not step["role"]:
        return None, None
    return _resolve_actor(incident_id, step["role"])


def _activate_step(
    incident_id: str,
    entity_type: str,
    entity_id: str,
    step: dict[str, Any],
    assign_actors: dict[str, int],
) -> None:
    step["status"] = "active"
    step["activated_at"] = _utc_now()
    if step["kind"] == "ack":
        return

    actor_id, resolved_role = _resolve_step_actor(incident_id, step)
    # The submitter can confirm or override the automatic pick — for a
    # "flexible" step (no role at all) or a role that came up vacant all the
    # way to the Incident Commander, this is the only way it ever gets
    # anyone; for a normally-resolved step, it's "submit to X instead?".
    override = assign_actors.get(step["step_id"])
    if override is not None and override != actor_id:
        actor_id = override
        resolved_role = "Selected by submitter"

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


def _waiting_at_min_order(instance: dict[str, Any]) -> list[dict[str, Any]]:
    waiting = [s for s in instance["steps"] if s["status"] == "waiting"]
    if not waiting:
        return []
    min_order = min(s["order"] for s in waiting)
    return [s for s in waiting if s["order"] == min_order]


def _activate_next_steps(
    incident_id: str, instance: dict[str, Any], assign_actors: Optional[dict[str, int]] = None
) -> None:
    for step in _waiting_at_min_order(instance):
        _activate_step(incident_id, instance["entity_type"], instance["entity_id"], step, assign_actors or {})


def _advance(
    incident_id: str, instance: dict[str, Any], now: str, assign_actors: Optional[dict[str, int]] = None
) -> None:
    active_remaining = [s for s in instance["steps"] if s["status"] == "active"]
    waiting_remaining = [s for s in instance["steps"] if s["status"] == "waiting"]
    if not active_remaining and not waiting_remaining:
        instance["status"] = "approved"
        instance["completed_at"] = now
    elif not active_remaining:
        _activate_next_steps(incident_id, instance, assign_actors)


def _write_status_to_entity(incident_id: str, instance: dict[str, Any]) -> None:
    if instance["status"] not in ("approved", "rejected"):
        return
    entry = _ENTITY_COLLECTIONS.get(instance["entity_type"])
    if entry is None:
        return
    collection_name, id_field, status_field = entry

    class _EntityRepository(BaseRepository):
        pass

    _EntityRepository.collection_name = collection_name
    _EntityRepository.soft_deletes = False
    repo = _EntityRepository(get_incident_db(incident_id))
    entity_id: Any = instance["entity_id"]
    if instance["entity_type"] == "iap":
        entity_id = int(entity_id)
    existing = repo.find_one({"incident_id": incident_id, id_field: entity_id})
    if existing is not None:
        repo.update_one(existing["_id"], {status_field: instance["status"]})


@router.get("/{incident_id}/approvals/{entity_type}/{entity_id}/start/preview")
def preview_start(incident_id: str, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    """What `start` would do on its own — the step(s) that would activate
    and who each would resolve to — without creating or saving anything.
    Lets a client show "Submit to <name>?" before the submitter commits."""
    spec = _get_spec(entity_type)
    steps = [_new_step(s) for s in spec.steps]
    fake_instance = {"entity_type": entity_type, "entity_id": entity_id, "steps": steps}
    # "ack" steps have nothing to confirm — anyone can acknowledge them.
    return [_preview_row(incident_id, s) for s in _waiting_at_min_order(fake_instance) if s["kind"] != "ack"]


def _preview_row(incident_id: str, step: dict[str, Any]) -> dict[str, Any]:
    actor_id, resolved_role = _resolve_step_actor(incident_id, step)
    return {
        "step_id": step["step_id"],
        "label": step["label"],
        "kind": step["kind"],
        "resolved_actor_id": actor_id,
        "resolved_actor_name": _person_name(actor_id) if actor_id is not None else None,
        "resolved_role": resolved_role,
    }


@router.post("/{incident_id}/approvals/{entity_type}/{entity_id}/start")
def start_instance(incident_id: str, entity_type: str, entity_id: str, body: StartRequest = StartRequest()) -> dict[str, Any]:
    spec = _get_spec(entity_type)
    existing = _instances_repo(incident_id).find_one(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id}
    )
    if existing is not None:
        raise HTTPException(409, "Approval workflow already exists for this record")
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
    _activate_next_steps(incident_id, instance, body.assign_actors)
    _save_instance(incident_id, instance)
    return instance


@router.get("/{incident_id}/approvals/{entity_type}/{entity_id}/sign/preview")
def preview_sign(incident_id: str, entity_type: str, entity_id: str, step_id: str) -> list[dict[str, Any]]:
    """What completing `step_id` would activate next, and who each newly
    active step would resolve to — without saving anything. Lets a client
    show "this will go to <name> next — change?" before the signer commits."""
    import copy

    repo = _instances_repo(incident_id)
    instance = repo.find_one(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id}
    )
    if instance is None:
        raise HTTPException(404, "Approval instance not found")
    sim = copy.deepcopy(instance)
    step = next((s for s in sim["steps"] if s["step_id"] == step_id), None)
    if step is None:
        raise HTTPException(404, f"Step not found: {step_id}")
    step["status"] = "completed"
    active_remaining = [s for s in sim["steps"] if s["status"] == "active"]
    if active_remaining:
        return []  # other steps still pending — nothing new activates yet
    return [_preview_row(incident_id, s) for s in _waiting_at_min_order(sim) if s["kind"] != "ack"]


@router.post("/{incident_id}/approvals/{entity_type}/{entity_id}/sign")
def sign_instance(
    incident_id: str,
    entity_type: str,
    entity_id: str,
    body: SignRequest,
    authorization: Optional[str] = Header(None),
) -> dict[str, Any]:
    from sarapp_db.api.routers.auth_sessions import resolve_request_person

    actor_id = resolve_request_person(
        authorization=authorization,
        session_id=body.session_id,
        claimed_person_record=body.actor_id,
    )
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

    assignment_type = _assignment_type_for(incident_id, actor_id)
    if step["kind"] != "ack":
        if step.get("resolved_actor_id") is None:
            raise HTTPException(
                400, "Nobody is assigned to this step yet — assign someone before signing."
            )
        if step["resolved_actor_id"] != actor_id:
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
        "actor_id": str(actor_id),
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
        _advance(incident_id, instance, now, body.assign_actors)

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
    step["resolved_role"] = "Selected by submitter"
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
    collection_name, id_field, status_field = entry

    class _EntityRepository(BaseRepository):
        pass

    _EntityRepository.collection_name = collection_name
    _EntityRepository.soft_deletes = False
    repo = _EntityRepository(get_incident_db(incident_id))
    lookup_id: Any = int(entity_id) if entity_type == "iap" else entity_id
    existing = repo.find_one({"incident_id": incident_id, id_field: lookup_id})
    if existing is None:
        raise HTTPException(404, f"{entity_type} {entity_id} not found")
    repo.update_one(existing["_id"], {status_field: body.approval_status})
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
