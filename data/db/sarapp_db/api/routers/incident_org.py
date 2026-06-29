"""FastAPI router — incident organization (ICS 203) CRUD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from modules.command.incident_organization.models import normalize_assignment_type
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class OrgPositionsRepository(BaseRepository):
    collection_name = IncidentCollections.ORG_POSITIONS
    soft_deletes = False


class OrgTemplatesRepository(BaseRepository):
    collection_name = IncidentCollections.ORG_TEMPLATES
    soft_deletes = False


class OrgAssignmentsRepository(BaseRepository):
    collection_name = IncidentCollections.ORG_ASSIGNMENTS
    soft_deletes = False


class OrgHistoryRepository(BaseRepository):
    collection_name = IncidentCollections.ORG_HISTORY
    soft_deletes = False


class OrgSnapshotsRepository(BaseRepository):
    collection_name = IncidentCollections.ORG_SNAPSHOTS
    soft_deletes = False


def _positions_repo(incident_id: str) -> OrgPositionsRepository:
    return OrgPositionsRepository(get_incident_db(incident_id))


def _templates_repo(incident_id: str) -> OrgTemplatesRepository:
    return OrgTemplatesRepository(get_incident_db(incident_id))


def _assignments_repo(incident_id: str) -> OrgAssignmentsRepository:
    return OrgAssignmentsRepository(get_incident_db(incident_id))


def _history_repo(incident_id: str) -> OrgHistoryRepository:
    return OrgHistoryRepository(get_incident_db(incident_id))


def _snapshots_repo(incident_id: str) -> OrgSnapshotsRepository:
    return OrgSnapshotsRepository(get_incident_db(incident_id))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _next_int_id(repo: BaseRepository, id_field: str) -> int:
    docs = repo.find_many({}, sort=None)
    ids = [doc[id_field] for doc in docs if isinstance(doc.get(id_field), int)]
    return max(ids, default=0) + 1


# ---------------------------------------------------------------------------
# Position models
# ---------------------------------------------------------------------------

class UpsertPositionRequest(BaseModel):
    position_id: Optional[int] = None
    title: str
    classification: str = "position"
    parent_position_id: Optional[int] = None
    operational_period: Optional[str] = None
    required_qualifications: List[str] = []
    is_critical: bool = False
    is_custom: bool = False
    is_air_ops: bool = False
    status: str = "active"
    sort_order: int = 0
    notes: Optional[str] = None


class MovePositionRequest(BaseModel):
    parent_position_id: Optional[int] = None


class ReplaceRequirementsRequest(BaseModel):
    qualifications: List[str]


def _pos_to_dict(doc: dict) -> dict[str, Any]:
    return {
        "id": doc["position_id"],
        "position_id": doc["position_id"],
        "incident_id": doc["incident_id"],
        "title": doc.get("title", ""),
        "classification": doc.get("classification", "position"),
        "parent_position_id": doc.get("parent_position_id"),
        "operational_period": doc.get("operational_period"),
        "required_qualifications": doc.get("required_qualifications", []),
        "is_critical": bool(doc.get("is_critical", False)),
        "is_custom": bool(doc.get("is_custom", False)),
        "is_air_ops": bool(doc.get("is_air_ops", False)),
        "status": doc.get("status", "active"),
        "sort_order": doc.get("sort_order", 0),
        "notes": doc.get("notes"),
    }


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/org/positions")
def list_positions(incident_id: str, include_inactive: bool = False) -> list[dict[str, Any]]:
    repo = _positions_repo(incident_id)
    filt: dict[str, Any] = {"incident_id": incident_id}
    if not include_inactive:
        filt["status"] = "active"
    docs = repo.find_many(filt, sort=[
        ("parent_position_id", 1),
        ("sort_order", 1),
        ("title", 1),
    ])
    return [_pos_to_dict(d) for d in docs]


@router.post("/{incident_id}/org/positions", status_code=201)
def upsert_position(incident_id: str, body: UpsertPositionRequest) -> dict[str, Any]:
    repo = _positions_repo(incident_id)
    if body.is_air_ops:
        existing_air_ops = repo.find_one({
            "incident_id": incident_id,
            "is_air_ops": True,
            "status": "active",
            "position_id": {"$ne": body.position_id} if body.position_id is not None else {"$exists": True},
        })
        if existing_air_ops:
            raise HTTPException(
                400,
                "An Air Operations Branch already exists for this incident "
                f"(position {existing_air_ops['position_id']}). There can only be one.",
            )
    if body.position_id is None:
        pid = _next_int_id(repo, "position_id")
        doc = {
            "position_id": pid,
            "incident_id": incident_id,
            "title": body.title.strip(),
            "classification": body.classification.strip() or "position",
            "parent_position_id": body.parent_position_id,
            "operational_period": body.operational_period,
            "required_qualifications": [q.strip() for q in body.required_qualifications if q.strip()],
            "is_critical": body.is_critical,
            "is_custom": body.is_custom,
            "is_air_ops": body.is_air_ops,
            "status": body.status or "active",
            "sort_order": body.sort_order,
            "notes": body.notes,
        }
        repo.insert_one(doc)
        return {"position_id": pid}
    existing = repo.find_one({"incident_id": incident_id, "position_id": body.position_id})
    if not existing:
        raise HTTPException(404, f"Position {body.position_id} not found")
    repo.update_one(existing["_id"], {
        "title": body.title.strip(),
        "classification": body.classification.strip() or "position",
        "parent_position_id": body.parent_position_id,
        "operational_period": body.operational_period,
        "required_qualifications": [q.strip() for q in body.required_qualifications if q.strip()],
        "is_critical": body.is_critical,
        "is_custom": body.is_custom,
        "is_air_ops": body.is_air_ops,
        "status": body.status or "active",
        "sort_order": body.sort_order,
        "notes": body.notes,
    })
    return {"position_id": body.position_id}


@router.get("/{incident_id}/org/positions/{position_id}")
def get_position(incident_id: str, position_id: int) -> dict[str, Any]:
    repo = _positions_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "position_id": position_id})
    if not doc:
        raise HTTPException(404, f"Position {position_id} not found")
    return _pos_to_dict(doc)


@router.patch("/{incident_id}/org/positions/{position_id}/move")
def move_position(incident_id: str, position_id: int, body: MovePositionRequest) -> dict[str, Any]:
    repo = _positions_repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id, "position_id": position_id})
    if not existing:
        raise HTTPException(404, f"Position {position_id} not found")
    repo.update_one(existing["_id"], {"parent_position_id": body.parent_position_id})
    return {"ok": True}


@router.delete("/{incident_id}/org/positions/{position_id}")
def deactivate_position(incident_id: str, position_id: int) -> dict[str, Any]:
    repo = _positions_repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id, "position_id": position_id})
    if not existing:
        raise HTTPException(404, f"Position {position_id} not found")
    repo.update_one(existing["_id"], {"status": "inactive"})
    return {"ok": True}


@router.put("/{incident_id}/org/positions/{position_id}/requirements")
def replace_requirements(
    incident_id: str, position_id: int, body: ReplaceRequirementsRequest
) -> dict[str, Any]:
    clean = [q.strip() for q in body.qualifications if q.strip()]
    repo = _positions_repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id, "position_id": position_id})
    if not existing:
        raise HTTPException(404, f"Position {position_id} not found")
    repo.update_one(existing["_id"], {"required_qualifications": clean})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Operational units
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/org/units")
def list_units(
    incident_id: str,
    classifications: Optional[str] = None,
) -> list[dict[str, Any]]:
    repo = _positions_repo(incident_id)
    default_classifications = {"branch", "division", "group", "staging_area"}
    cls_set = set(classifications.split(",")) if classifications else default_classifications
    docs = repo.find_many(
        {"incident_id": incident_id, "status": "active", "classification": {"$in": list(cls_set)}},
        sort=[("sort_order", 1), ("title", 1)],
    )
    return [_pos_to_dict(d) for d in docs]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class SaveTemplateRequest(BaseModel):
    template_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    payload: List[dict] = []


class ApplyTemplateRequest(BaseModel):
    payload: List[dict]


def _template_to_dict(doc: dict) -> dict[str, Any]:
    return {
        "id": doc.get("template_id"),
        "template_id": doc.get("template_id"),
        "incident_id": doc.get("incident_id"),
        "name": doc.get("name", ""),
        "description": doc.get("description"),
        "payload": doc.get("payload", []),
    }


def _builtin_templates() -> list[dict[str, Any]]:
    """Return the default built-in ICS templates as dicts."""
    try:
        from modules.command.incident_organization.repository import (
            _default_organization_templates,
        )
        templates = _default_organization_templates()
        result = []
        for i, t in enumerate(templates):
            result.append({
                "id": -(i + 1),
                "template_id": -(i + 1),
                "incident_id": None,
                "name": t.name,
                "description": t.description,
                "payload": t.payload,
            })
        return result
    except Exception:
        return []


@router.get("/{incident_id}/org/templates")
def list_templates(incident_id: str) -> list[dict[str, Any]]:
    repo = _templates_repo(incident_id)
    custom = [_template_to_dict(d) for d in repo.find_many({"incident_id": incident_id})]
    return _builtin_templates() + custom


@router.get("/{incident_id}/org/templates/by-name")
def get_template_by_name(incident_id: str, name: str) -> dict[str, Any]:
    repo = _templates_repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "name": name})
    if doc:
        return _template_to_dict(doc)
    for t in _builtin_templates():
        if t["name"] == name:
            return t
    raise HTTPException(404, f"Template '{name}' not found")


@router.post("/{incident_id}/org/templates", status_code=201)
def save_template(incident_id: str, body: SaveTemplateRequest) -> dict[str, Any]:
    repo = _templates_repo(incident_id)
    if body.template_id is None or body.template_id < 0:
        tid = _next_int_id(repo, "template_id")
        repo.insert_one({
            "template_id": tid,
            "incident_id": incident_id,
            "name": body.name,
            "description": body.description,
            "payload": body.payload,
        })
        return {"template_id": tid}
    existing = repo.find_one({"incident_id": incident_id, "template_id": body.template_id})
    if not existing:
        raise HTTPException(404, f"Template {body.template_id} not found")
    repo.update_one(existing["_id"], {"name": body.name, "description": body.description, "payload": body.payload})
    return {"template_id": body.template_id}


@router.post("/{incident_id}/org/templates/apply", status_code=201)
def apply_template_payload(incident_id: str, body: ApplyTemplateRequest) -> list[int]:
    """Create missing positions from a template payload; return position IDs."""
    pos_repo = _positions_repo(incident_id)
    key_to_id: dict[str, int] = {}
    applied_ids: list[int] = []
    for index, raw in enumerate(body.payload):
        if not isinstance(raw, dict):
            raise HTTPException(400, "Payload entries must be objects")
        key = str(raw.get("key") or f"item_{index}").strip() or f"item_{index}"
        if key in key_to_id:
            raise HTTPException(400, f"Duplicate template key: {key}")
        parent_key = raw.get("parent_key")
        parent_id: Optional[int] = None
        if parent_key:
            parent_id = key_to_id.get(str(parent_key))
            if parent_id is None:
                raise HTTPException(400, f"Entry '{key}' references unknown parent '{parent_key}'")
        title = str(raw.get("title", "")).strip()
        if not title:
            raise HTTPException(400, "Template position title is required")
        classification = str(raw.get("classification", "position")).strip() or "position"
        status = str(raw.get("status", "active") or "active").strip().lower()
        if status not in {"active", "inactive"}:
            status = "active"
        qualifications = raw.get("required_qualifications") or []
        if isinstance(qualifications, str):
            qualifications = [q.strip() for q in qualifications.split(",") if q.strip()]
        is_air_ops = bool(raw.get("is_air_ops", False))
        # Idempotent: find existing active position with same title+classification+parent
        existing = pos_repo.find_one({
            "incident_id": incident_id,
            "title": title,
            "classification": classification,
            "parent_position_id": parent_id,
            "status": "active",
        })
        if not existing and is_air_ops:
            # There can only be one Air Operations Branch per incident -
            # reuse whichever one already exists (even under a different
            # title/parent) instead of creating a second, conflicting one.
            existing = pos_repo.find_one({
                "incident_id": incident_id,
                "is_air_ops": True,
                "status": "active",
            })
        if existing:
            pid = existing["position_id"]
        else:
            pid = _next_int_id(pos_repo, "position_id")
            pos_repo.insert_one({
                "position_id": pid,
                "incident_id": incident_id,
                "title": title,
                "classification": classification,
                "parent_position_id": parent_id,
                "operational_period": raw.get("operational_period"),
                "required_qualifications": [str(q) for q in qualifications],
                "is_critical": bool(raw.get("is_critical", False)),
                "is_custom": bool(raw.get("is_custom", False)),
                "is_air_ops": bool(raw.get("is_air_ops", False)),
                "status": status,
                "sort_order": int(raw.get("sort_order", 0) or 0),
                "notes": raw.get("notes"),
            })
        key_to_id[key] = pid
        applied_ids.append(pid)
    return applied_ids


# ---------------------------------------------------------------------------
# Assignment models
# ---------------------------------------------------------------------------

class AddAssignmentRequest(BaseModel):
    position_id: int
    personnel_id: Optional[str] = None
    display_name: str
    assignment_type: str = "primary"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    operational_period: Optional[str] = None
    assigned_by: Optional[str] = None
    notes: Optional[str] = None


class EndAssignmentRequest(BaseModel):
    end_time: Optional[str] = None
    changed_by: Optional[str] = None
    notes: Optional[str] = None


def _assignment_to_dict(doc: dict) -> dict[str, Any]:
    assignment_type = normalize_assignment_type(doc.get("assignment_type", "primary"))
    return {
        "id": doc["assignment_id"],
        "assignment_id": doc["assignment_id"],
        "incident_id": doc["incident_id"],
        "position_id": doc["position_id"],
        "personnel_id": doc.get("personnel_id"),
        "display_name": doc.get("display_name", ""),
        "assignment_type": assignment_type,
        "start_time": doc.get("start_time"),
        "end_time": doc.get("end_time"),
        "operational_period": doc.get("operational_period"),
        "assigned_by": doc.get("assigned_by"),
        "notes": doc.get("notes"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

_VALID_ASSIGNMENT_TYPES = {"primary", "deputy", "assistant", "staff_assistant", "trainee", "relief"}


@router.post("/{incident_id}/org/assignments", status_code=201)
def add_assignment(incident_id: str, body: AddAssignmentRequest) -> dict[str, Any]:
    atype = normalize_assignment_type(body.assignment_type)
    if atype not in _VALID_ASSIGNMENT_TYPES:
        raise HTTPException(400, f"Invalid assignment type: {body.assignment_type}")
    asgn_repo = _assignments_repo(incident_id)
    hist_repo = _history_repo(incident_id)
    now = _utc_now()
    start = body.start_time or now
    aid = _next_int_id(asgn_repo, "assignment_id")
    asgn_repo.insert_one({
        "assignment_id": aid,
        "incident_id": incident_id,
        "position_id": body.position_id,
        "personnel_id": body.personnel_id,
        "display_name": body.display_name,
        "assignment_type": atype,
        "start_time": start,
        "end_time": body.end_time,
        "operational_period": body.operational_period,
        "assigned_by": body.assigned_by,
        "notes": body.notes,
    })
    hid = _next_int_id(hist_repo, "history_id")
    hist_repo.insert_one({
        "history_id": hid,
        "incident_id": incident_id,
        "assignment_id": aid,
        "position_id": body.position_id,
        "personnel_id": body.personnel_id,
        "display_name": body.display_name,
        "assignment_type": atype,
        "action": "assigned",
        "effective_time": start,
        "operational_period": body.operational_period,
        "changed_by": body.assigned_by,
        "notes": body.notes,
    })
    return {"assignment_id": aid}


@router.patch("/{incident_id}/org/assignments/{assignment_id}/end")
def end_assignment(incident_id: str, assignment_id: int, body: EndAssignmentRequest) -> dict[str, Any]:
    asgn_repo = _assignments_repo(incident_id)
    hist_repo = _history_repo(incident_id)
    doc = asgn_repo.find_one({"incident_id": incident_id, "assignment_id": assignment_id})
    if not doc:
        return {"ok": True}
    effective = body.end_time or _utc_now()
    updates: dict[str, Any] = {"end_time": effective}
    if body.notes:
        updates["notes"] = body.notes
    asgn_repo.update_one(doc["_id"], updates)
    hid = _next_int_id(hist_repo, "history_id")
    hist_repo.insert_one({
        "history_id": hid,
        "incident_id": incident_id,
        "assignment_id": assignment_id,
        "position_id": doc["position_id"],
        "personnel_id": doc.get("personnel_id"),
        "display_name": doc.get("display_name", ""),
        "assignment_type": doc.get("assignment_type", "primary"),
        "action": "removed",
        "effective_time": effective,
        "operational_period": doc.get("operational_period"),
        "changed_by": body.changed_by,
        "notes": body.notes,
    })
    return {"ok": True}


@router.get("/{incident_id}/org/assignments")
def list_assignments(
    incident_id: str,
    position_id: Optional[int] = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    repo = _assignments_repo(incident_id)
    filt: dict[str, Any] = {"incident_id": incident_id}
    if position_id is not None:
        filt["position_id"] = position_id
    if active_only:
        filt["end_time"] = None
    docs = repo.find_many(filt, sort=[("position_id", 1), ("start_time", 1), ("assignment_id", 1)])
    return [_assignment_to_dict(d) for d in docs]


@router.get("/{incident_id}/org/assignments/by-person/{personnel_id}")
def list_assignments_for_person(
    incident_id: str,
    personnel_id: str,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    repo = _assignments_repo(incident_id)
    filt: dict[str, Any] = {"incident_id": incident_id, "personnel_id": personnel_id}
    if active_only:
        filt["end_time"] = None
    docs = repo.find_many(filt, sort=[("position_id", 1), ("start_time", 1)])
    return [_assignment_to_dict(d) for d in docs]


@router.get("/{incident_id}/org/history")
def list_assignment_history(
    incident_id: str, position_id: Optional[int] = None
) -> list[dict[str, Any]]:
    repo = _history_repo(incident_id)
    filt: dict[str, Any] = {"incident_id": incident_id}
    if position_id is not None:
        filt["position_id"] = position_id
    docs = repo.find_many(filt, sort=[("created_at", 1), ("history_id", 1)])
    return [
        {
            "id": d["history_id"],
            "history_id": d["history_id"],
            "incident_id": d["incident_id"],
            "assignment_id": d.get("assignment_id"),
            "position_id": d["position_id"],
            "personnel_id": d.get("personnel_id"),
            "display_name": d.get("display_name", ""),
            "assignment_type": normalize_assignment_type(d.get("assignment_type", "primary")),
            "action": d.get("action", ""),
            "effective_time": d.get("effective_time"),
            "operational_period": d.get("operational_period"),
            "changed_by": d.get("changed_by"),
            "notes": d.get("notes"),
        }
        for d in docs
    ]


# ---------------------------------------------------------------------------
# Generated form snapshots
# ---------------------------------------------------------------------------

class SaveSnapshotRequest(BaseModel):
    form_type: str
    generated_at: str
    operational_period: Optional[str] = None
    source_version: Optional[str] = None
    payload: dict = {}


@router.post("/{incident_id}/org/snapshots", status_code=201)
def save_snapshot(incident_id: str, body: SaveSnapshotRequest) -> dict[str, Any]:
    repo = _snapshots_repo(incident_id)
    sid = _next_int_id(repo, "snapshot_id")
    repo.insert_one({
        "snapshot_id": sid,
        "incident_id": incident_id,
        "form_type": body.form_type,
        "generated_at": body.generated_at,
        "operational_period": body.operational_period,
        "source_version": body.source_version,
        "payload": body.payload,
    })
    return {"snapshot_id": sid}
