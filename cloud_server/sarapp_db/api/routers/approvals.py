"""Approval instances and records API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db

router = APIRouter()

_VALID_ACTIONS = {"approved", "rejected", "acknowledged"}

# Maps entity_type -> (collection_name, id_field) so the service can write
# approval_status back to the entity's own record when the chain completes.
# Extend this as new approvable entity types are wired up.
_ENTITY_COLLECTIONS: dict[str, tuple[str, str]] = {
    "ics_205": (IncidentCollections.ICS_205_INSTANCES, "id"),
    "ics_206": (IncidentCollections.ICS_206_BUILDS, "id"),
    "iwi_report": (IncidentCollections.IWI_REPORTS, "id"),
    "iap": (IncidentCollections.FORMS, "id"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _db(incident_id: str):
    return get_incident_db(incident_id)


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


class PendingRequest(BaseModel):
    roles: list[str]
    personnel_id: str


class EntityStatusRequest(BaseModel):
    approval_status: str


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/approvals/instances/{entity_type}/{entity_id}")
def get_instance(incident_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    col = _db(incident_id)[IncidentCollections.APPROVAL_INSTANCES]
    doc = col.find_one({
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
    })
    if not doc:
        raise HTTPException(404, "Approval instance not found")
    return _strip_id(doc)


@router.put("/{incident_id}/approvals/instances/{entity_type}/{entity_id}")
def upsert_instance(
    incident_id: str, entity_type: str, entity_id: str, body: dict
) -> dict[str, Any]:
    col = _db(incident_id)[IncidentCollections.APPROVAL_INSTANCES]
    col.replace_one(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id},
        {**body, "incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id},
        upsert=True,
    )
    return {"ok": True}


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
    col = _db(incident_id)[collection_name]
    result = col.update_one(
        {"incident_id": incident_id, id_field: entity_id},
        {"$set": {"approval_status": body.approval_status, "updated_at": _utc_now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, f"{entity_type} {entity_id} not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@router.post("/{incident_id}/approvals/records", status_code=201)
def save_record(incident_id: str, body: SaveRecordRequest) -> dict[str, Any]:
    if body.action not in _VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action: {body.action}")
    col = _db(incident_id)[IncidentCollections.APPROVAL_RECORDS]
    col.insert_one({
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
    col = _db(incident_id)[IncidentCollections.APPROVAL_RECORDS]
    docs = list(col.find(
        {"incident_id": incident_id, "entity_type": entity_type, "entity_id": entity_id},
        sort=[("timestamp", 1)],
    ))
    return [_strip_id(d) for d in docs]


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@router.post("/{incident_id}/approvals/pending")
def pending_for_roles(incident_id: str, body: PendingRequest) -> list[dict[str, Any]]:
    """Return active steps where resolved_actor_id matches or role is held by this person."""
    col = _db(incident_id)[IncidentCollections.APPROVAL_INSTANCES]
    docs = list(col.find({"incident_id": incident_id, "status": "pending"}))
    results: list[dict[str, Any]] = []
    for doc in docs:
        for step in doc.get("steps", []):
            if step.get("status") != "active":
                continue
            resolved = step.get("resolved_actor_id")
            role = step.get("role", "")
            if resolved == body.personnel_id or role in body.roles:
                results.append({
                    "entity_type": doc["entity_type"],
                    "entity_id": doc["entity_id"],
                    "step_id": step.get("step_id"),
                    "label": step.get("label"),
                    "role": role,
                    "resolved_actor_id": resolved,
                })
    return results
