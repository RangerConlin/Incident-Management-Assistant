"""FastAPI router - incident organization (ICS 203) current state."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from modules.command.incident_organization.models import (
    ASSIGNMENT_TYPE_ASSISTANT,
    ASSIGNMENT_TYPE_DEPUTY,
    ASSIGNMENT_TYPE_PRIMARY,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
    ASSIGNMENT_TYPE_TRAINEE,
    normalize_assignment_type,
)
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class IncidentOrgRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_ORG
    soft_deletes = False


class OrgTemplatesRepository(BaseRepository):
    collection_name = IncidentCollections.ORG_TEMPLATES
    soft_deletes = False


class MasterPersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


def _org_repo(incident_id: str) -> IncidentOrgRepository:
    return IncidentOrgRepository(get_incident_db(incident_id))


def _templates_repo(incident_id: str) -> OrgTemplatesRepository:
    return OrgTemplatesRepository(get_incident_db(incident_id))


def _personnel_repo() -> MasterPersonnelRepository:
    return MasterPersonnelRepository(get_master_db())


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _next_int_id(repo: BaseRepository, id_field: str) -> int:
    docs = repo.find_many({}, sort=None)
    ids = [doc[id_field] for doc in docs if isinstance(doc.get(id_field), int)]
    return max(ids, default=0) + 1


def _require_person(person_record: int) -> dict[str, Any]:
    doc = _personnel_repo().find_one({"person_record": person_record})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Person {person_record} not found")
    return doc


def _person_name(person_record: object) -> str:
    try:
        record = int(person_record)
    except (TypeError, ValueError):
        return ""
    try:
        doc = _personnel_repo().find_one({"person_record": record})
    except Exception:
        doc = None
    return str((doc or {}).get("name") or "").strip()


def _bucket_for_assignment_type(assignment_type: str) -> tuple[str, bool] | None:
    atype = normalize_assignment_type(assignment_type)
    if atype == ASSIGNMENT_TYPE_PRIMARY:
        return "primary", False
    if atype == ASSIGNMENT_TYPE_TRAINEE:
        return "primary", True
    if atype in {ASSIGNMENT_TYPE_DEPUTY, ASSIGNMENT_TYPE_ASSISTANT}:
        return "deputies", False
    if atype == ASSIGNMENT_TYPE_STAFF_ASSISTANT:
        return "staff_assistants", False
    return None


def _assignment_type_for_bucket(bucket: str, assignment: dict[str, Any]) -> str:
    if bool(assignment.get("trainee")):
        return ASSIGNMENT_TYPE_TRAINEE
    if bucket == "deputies":
        return ASSIGNMENT_TYPE_DEPUTY
    if bucket == "staff_assistants":
        return ASSIGNMENT_TYPE_STAFF_ASSISTANT
    return ASSIGNMENT_TYPE_PRIMARY


def _assignment_key(position_id: int, bucket: str, person_record: object) -> str:
    return f"{position_id}:{bucket}:{person_record}"


def _empty_assignment_arrays() -> dict[str, list[dict[str, Any]]]:
    return {"primary": [], "deputies": [], "staff_assistants": []}


# ---------------------------------------------------------------------------
# Position models
# ---------------------------------------------------------------------------

class UpsertPositionRequest(BaseModel):
    position_id: Optional[int] = None
    title: str
    classification: str = "position"
    parent_position_id: Optional[int] = None
    sort_order: int = 0


class MovePositionRequest(BaseModel):
    parent_position_id: Optional[int] = None


def _pos_to_dict(doc: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": doc["position_id"],
        "position_id": doc["position_id"],
        "title": doc.get("title", ""),
        "classification": doc.get("classification", "position"),
        "parent_position_id": doc.get("parent_position_id"),
        "sort_order": doc.get("sort_order", 0),
        "primary": list(doc.get("primary") or []),
        "deputies": list(doc.get("deputies") or []),
        "staff_assistants": list(doc.get("staff_assistants") or []),
    }
    # Compatibility for callers that still expect these fields while the UI
    # settles on the slimmer canonical shape.
    out["incident_id"] = doc.get("incident_id", "")
    out["status"] = "active"
    out["is_air_ops"] = bool("air operations" in out["title"].casefold())
    out["operational_period"] = None
    out["required_qualifications"] = []
    out["is_critical"] = False
    out["is_custom"] = False
    out["notes"] = None
    return out


# ---------------------------------------------------------------------------
# Positions / org nodes
# ---------------------------------------------------------------------------

@router.get("/{incident_id}/org/positions")
def list_positions(incident_id: str, include_inactive: bool = False) -> list[dict[str, Any]]:
    repo = _org_repo(incident_id)
    docs = repo.find_many({}, sort=[
        ("parent_position_id", 1),
        ("sort_order", 1),
        ("title", 1),
    ])
    return [_pos_to_dict(d) for d in docs]


@router.post("/{incident_id}/org/positions", status_code=201)
def upsert_position(incident_id: str, body: UpsertPositionRequest) -> dict[str, Any]:
    repo = _org_repo(incident_id)
    if body.position_id is None:
        pid = _next_int_id(repo, "position_id")
        repo.insert_one({
            "position_id": pid,
            "incident_id": incident_id,
            "title": body.title.strip(),
            "classification": body.classification.strip() or "position",
            "parent_position_id": body.parent_position_id,
            "sort_order": body.sort_order,
            **_empty_assignment_arrays(),
        })
        return {"position_id": pid}
    existing = repo.find_one({"position_id": body.position_id})
    if not existing:
        raise HTTPException(404, f"Position {body.position_id} not found")
    repo.update_one(existing["_id"], {
        "title": body.title.strip(),
        "classification": body.classification.strip() or "position",
        "parent_position_id": body.parent_position_id,
        "sort_order": body.sort_order,
    })
    return {"position_id": body.position_id}


@router.get("/{incident_id}/org/positions/{position_id}")
def get_position(incident_id: str, position_id: int) -> dict[str, Any]:
    repo = _org_repo(incident_id)
    doc = repo.find_one({"position_id": position_id})
    if not doc:
        raise HTTPException(404, f"Position {position_id} not found")
    return _pos_to_dict(doc)


@router.patch("/{incident_id}/org/positions/{position_id}/move")
def move_position(incident_id: str, position_id: int, body: MovePositionRequest) -> dict[str, Any]:
    repo = _org_repo(incident_id)
    existing = repo.find_one({"position_id": position_id})
    if not existing:
        raise HTTPException(404, f"Position {position_id} not found")
    repo.update_one(existing["_id"], {"parent_position_id": body.parent_position_id})
    return {"ok": True}


@router.delete("/{incident_id}/org/positions/{position_id}")
def deactivate_position(incident_id: str, position_id: int) -> dict[str, Any]:
    repo = _org_repo(incident_id)
    existing = repo.find_one({"position_id": position_id})
    if not existing:
        raise HTTPException(404, f"Position {position_id} not found")
    repo.delete_one(existing["_id"])
    return {"ok": True}


@router.get("/{incident_id}/org/units")
def list_units(
    incident_id: str,
    classifications: Optional[str] = None,
) -> list[dict[str, Any]]:
    repo = _org_repo(incident_id)
    default_classifications = {"branch", "division", "group", "staging_area"}
    cls_set = set(classifications.split(",")) if classifications else default_classifications
    docs = repo.find_many(
        {"classification": {"$in": list(cls_set)}},
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
    repo = _org_repo(incident_id)
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
        existing = repo.find_one({
            "title": title,
            "classification": classification,
            "parent_position_id": parent_id,
        })
        if existing:
            pid = existing["position_id"]
        else:
            pid = _next_int_id(repo, "position_id")
            repo.insert_one({
                "position_id": pid,
                "incident_id": incident_id,
                "title": title,
                "classification": classification,
                "parent_position_id": parent_id,
                "sort_order": int(raw.get("sort_order", 0) or 0),
                **_empty_assignment_arrays(),
            })
        key_to_id[key] = pid
        applied_ids.append(pid)
    return applied_ids


# ---------------------------------------------------------------------------
# Assignments embedded on org nodes
# ---------------------------------------------------------------------------

class AddAssignmentRequest(BaseModel):
    position_id: int
    person_record: int
    assignment_type: str = "primary"
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class EndAssignmentRequest(BaseModel):
    end_time: Optional[str] = None


def _assignment_to_dict(
    position_id: int,
    bucket: str,
    assignment: dict[str, Any],
) -> dict[str, Any]:
    person_record = assignment.get("person_record")
    assignment_type = _assignment_type_for_bucket(bucket, assignment)
    key = _assignment_key(position_id, bucket, person_record)
    return {
        "id": key,
        "assignment_id": key,
        "incident_id": "",
        "position_id": position_id,
        "person_record": person_record,
        "person_name": _person_name(person_record),
        "assignment_type": assignment_type,
        "start_time": assignment.get("start_time"),
        "end_time": assignment.get("end_time"),
        "operational_period": None,
        "assigned_by": None,
        "notes": None,
        "trainee": bool(assignment.get("trainee")),
    }


def _assignments_from_position(doc: dict[str, Any]) -> list[dict[str, Any]]:
    position_id = int(doc.get("position_id", 0))
    rows: list[dict[str, Any]] = []
    for bucket in ("primary", "deputies", "staff_assistants"):
        for assignment in doc.get(bucket) or []:
            rows.append(_assignment_to_dict(position_id, bucket, assignment))
    return rows


def _all_assignment_rows(repo: IncidentOrgRepository) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in repo.find_many({}, sort=[("position_id", 1)]):
        rows.extend(_assignments_from_position(doc))
    return rows


@router.post("/{incident_id}/org/assignments", status_code=201)
def add_assignment(incident_id: str, body: AddAssignmentRequest) -> dict[str, Any]:
    bucket_spec = _bucket_for_assignment_type(body.assignment_type)
    if bucket_spec is None:
        raise HTTPException(400, f"Assignment type is not tracked: {body.assignment_type}")
    bucket, trainee = bucket_spec
    _require_person(body.person_record)
    repo = _org_repo(incident_id)
    doc = repo.find_one({"position_id": body.position_id})
    if not doc:
        raise HTTPException(404, f"Position {body.position_id} not found")
    assignments = [
        item for item in list(doc.get(bucket) or [])
        if item.get("person_record") != body.person_record
    ]
    assignments.append({
        "person_record": body.person_record,
        "start_time": body.start_time or _utc_now(),
        "end_time": body.end_time,
        "trainee": trainee,
    })
    repo.update_one(doc["_id"], {bucket: assignments})
    return {"assignment_id": _assignment_key(body.position_id, bucket, body.person_record)}


@router.patch("/{incident_id}/org/assignments/{assignment_id}/end")
def end_assignment(incident_id: str, assignment_id: str, body: EndAssignmentRequest) -> dict[str, Any]:
    try:
        raw_position_id, bucket, raw_person_record = assignment_id.split(":", 2)
        position_id = int(raw_position_id)
        person_record = int(raw_person_record)
    except ValueError:
        raise HTTPException(400, "Invalid assignment id")
    if bucket not in {"primary", "deputies", "staff_assistants"}:
        raise HTTPException(400, "Invalid assignment id")
    repo = _org_repo(incident_id)
    doc = repo.find_one({"position_id": position_id})
    if not doc:
        return {"ok": True}
    changed = False
    assignments = []
    for item in list(doc.get(bucket) or []):
        if item.get("person_record") == person_record:
            item = {**item, "end_time": body.end_time or _utc_now()}
            changed = True
        assignments.append(item)
    if changed:
        repo.update_one(doc["_id"], {bucket: assignments})
    return {"ok": True}


@router.get("/{incident_id}/org/assignments")
def list_assignments(
    incident_id: str,
    position_id: Optional[int] = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    repo = _org_repo(incident_id)
    docs = repo.find_many(
        {"position_id": position_id} if position_id is not None else {},
        sort=[("position_id", 1)],
    )
    rows: list[dict[str, Any]] = []
    for doc in docs:
        rows.extend(_assignments_from_position(doc))
    if active_only:
        rows = [row for row in rows if row.get("end_time") is None]
    return sorted(rows, key=lambda row: (row.get("position_id") or 0, row.get("start_time") or ""))


@router.get("/{incident_id}/org/assignments/by-person/{person_record}")
def list_assignments_for_person(
    incident_id: str,
    person_record: int,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    repo = _org_repo(incident_id)
    rows = [
        row for row in _all_assignment_rows(repo)
        if row.get("person_record") == person_record
    ]
    if active_only:
        rows = [row for row in rows if row.get("end_time") is None]
    return sorted(rows, key=lambda row: (row.get("position_id") or 0, row.get("start_time") or ""))
