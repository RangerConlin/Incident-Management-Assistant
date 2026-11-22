"""Checklist instances — incident-scoped, or standalone with no incident.

A checklist instance is either created from a `checklist_templates.py`
catalog template (its sections/items are snapshotted in, so later template
edits/deletes never change this instance) or created blank, with its own
caller-supplied sections/items. Either way, this router — and the shared
rules in `sarapp_db.services.checklist_service` — is the only place that
knows how to record a response, validate it, compute progress, or move a
checklist through its lifecycle. No other module may add its own
checklist/response storage; a module that wants checklists calls this API.

Incident association is optional per instance. Every operation is
implemented once, in the `_impl` functions below, parameterized by
``incident_id: Optional[str]``, and exposed under two URL families that
share that implementation:
  - ``/api/incidents/{incident_id}/checklists...`` — incident-scoped,
    stored in that incident's own per-incident database
    (`get_incident_db`), matching every other incident-scoped router.
  - ``/api/checklists...`` — standalone, stored in the shared
    `sarapp_master` database (`MasterCollections.CHECKLISTS`), the same
    "not tied to one incident" pattern `push_tokens.py` already uses for
    master-scoped-but-not-a-catalog data.
Both URL families persist the same document shape and go through the same
validation/progress/lifecycle rules; only which database holds the
document differs.

Authorization model: like the rest of this API (see `auth_sessions.py`'s
module docstring), there is no repo-wide role/permission layer yet. What
this router *does* enforce, consistently, is authenticated attribution —
every write that the product spec requires to be attributed to a real
person (creating an instance, recording/updating a response, changing
status) resolves the caller through `auth_sessions.resolve_request_person`
(a signed web bearer token or an active desktop/mobile session), the same
mechanism `approvals.py` already uses for signing an approval step. Read
endpoints are open, matching every other incident-scoped router
(`facilities.py`, `meetings.py`, ...) — there is no broader access-control
layer in this codebase yet to apply to reads specifically.

Incident scoping follows the established pattern for the incident-scoped
family: every document lives in the caller's own per-incident database
and every read double-checks `doc["incident_id"] == incident_id` before
returning it, so a checklist id from a different incident 404s instead of
leaking across incidents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.api.routers.checklist_templates import (
    ChecklistTemplateSection,
    ChecklistTemplatesRepository,
)
from sarapp_db.api.routers.checklist_templates import _record_field as _template_record_field
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services import checklist_service as svc

router = APIRouter()


class ChecklistsRepository(BaseRepository):
    collection_name = IncidentCollections.CHECKLISTS
    soft_deletes = False


class StandaloneChecklistsRepository(BaseRepository):
    collection_name = MasterCollections.CHECKLISTS
    soft_deletes = False


def _repo(incident_id: Optional[str]):
    if incident_id:
        return ChecklistsRepository(get_incident_db(incident_id))
    return StandaloneChecklistsRepository(get_master_db())


def _next_int_id(repo) -> int:
    row = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return int(row.get("int_id") or 0) + 1 if row else 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_actor(
    authorization: Optional[str], session_id: Optional[str], claimed_actor_id: Optional[int]
) -> int:
    from sarapp_db.api.routers.auth_sessions import resolve_request_person

    return resolve_request_person(
        authorization=authorization, session_id=session_id, claimed_person_record=claimed_actor_id
    )


def _get_checklist_or_404(repo, incident_id: Optional[str], checklist_id: str) -> Dict[str, Any]:
    doc = repo.find_by_id(checklist_id)
    doc_incident_id = doc.get("incident_id") if doc else None
    if not doc or (str(doc_incident_id) if doc_incident_id else None) != incident_id:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return doc


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id") or ""),
        "int_id": doc.get("int_id"),
        "incident_id": doc.get("incident_id"),
        "name": str(doc.get("name") or ""),
        "description": str(doc.get("description") or ""),
        "instructions": str(doc.get("instructions") or ""),
        "template_id": doc.get("template_id"),
        "owner_person_record": doc.get("owner_person_record"),
        "linked_record": doc.get("linked_record"),
        "status": str(doc.get("status") or svc.NOT_STARTED),
        "sections": doc.get("sections") or [],
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
        "created_by": doc.get("created_by"),
        "completed_at": doc.get("completed_at"),
        "archived_at": doc.get("archived_at"),
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LinkedRecordPayload(BaseModel):
    """A stable reference to another SARApp record, not a database foreign
    key — this collection never joins against the referenced record, so it
    has no dependency on what that record's module is (Planned Events or
    anything else)."""

    record_type: str
    record_id: str


class CreateBlankChecklistRequest(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    sections: list[ChecklistTemplateSection] = Field(min_length=1)
    owner_person_record: Optional[int] = None
    linked_record: Optional[LinkedRecordPayload] = None
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class CreateFromTemplateRequest(BaseModel):
    template_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    owner_person_record: Optional[int] = None
    linked_record: Optional[LinkedRecordPayload] = None
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class RecordResponseRequest(BaseModel):
    value: Any = None
    na: bool = False
    notes: str = ""
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class StatusUpdateRequest(BaseModel):
    status: str
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def _create_blank_impl(
    incident_id: Optional[str], body: CreateBlankChecklistRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    sections = [section.model_dump() for section in body.sections]
    try:
        svc.validate_template_shape(sections)
        for section in sections:
            for item in section.get("items") or []:
                if item["item_type"] not in svc.ITEM_TYPES:
                    raise svc.ChecklistValidationError(f"Unknown item_type: {item['item_type']!r}")
    except svc.ChecklistValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    sections = svc.snapshot_sections(sections)

    repo = _repo(incident_id)
    now = _utcnow()
    doc = repo.insert_one(
        {
            "incident_id": incident_id,
            "int_id": _next_int_id(repo),
            "name": body.name.strip(),
            "description": body.description.strip(),
            "instructions": body.instructions.strip(),
            "template_id": None,
            "owner_person_record": body.owner_person_record,
            "linked_record": body.linked_record.model_dump() if body.linked_record else None,
            "status": svc.NOT_STARTED,
            "sections": sections,
            "created_by": actor_id,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "archived_at": None,
        }
    )
    return _serialize(doc)


@router.post("/incidents/{incident_id}/checklists", status_code=201)
def create_blank_checklist(
    incident_id: str,
    body: CreateBlankChecklistRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _create_blank_impl(incident_id, body, authorization)


@router.post("/checklists", status_code=201)
def create_blank_standalone_checklist(
    body: CreateBlankChecklistRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _create_blank_impl(None, body, authorization)


def _create_from_template_impl(
    incident_id: Optional[str], body: CreateFromTemplateRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    template_repo = ChecklistTemplatesRepository(get_master_db())
    field = _template_record_field(template_repo)
    template = template_repo.find_one({field: body.template_id})
    if template is None:
        raise HTTPException(404, "Checklist template not found")

    sections = svc.snapshot_sections(template.get("sections") or [])
    repo = _repo(incident_id)
    now = _utcnow()
    doc = repo.insert_one(
        {
            "incident_id": incident_id,
            "int_id": _next_int_id(repo),
            "name": (body.name or template.get("name") or "").strip(),
            "description": (
                body.description if body.description is not None else template.get("description") or ""
            ).strip(),
            "instructions": str(template.get("instructions") or ""),
            "template_id": body.template_id,
            "owner_person_record": body.owner_person_record,
            "linked_record": body.linked_record.model_dump() if body.linked_record else None,
            "status": svc.NOT_STARTED,
            "sections": sections,
            "created_by": actor_id,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "archived_at": None,
        }
    )
    return _serialize(doc)


@router.post("/incidents/{incident_id}/checklists/from-template", status_code=201)
def create_checklist_from_template(
    incident_id: str,
    body: CreateFromTemplateRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _create_from_template_impl(incident_id, body, authorization)


@router.post("/checklists/from-template", status_code=201)
def create_standalone_checklist_from_template(
    body: CreateFromTemplateRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _create_from_template_impl(None, body, authorization)


# ---------------------------------------------------------------------------
# List / retrieve
# ---------------------------------------------------------------------------

def _list_impl(
    incident_id: Optional[str],
    status: Optional[str],
    owner_person_record: Optional[int],
    template_id: Optional[int],
    linked_record_type: Optional[str],
    linked_record_id: Optional[str],
) -> List[Dict[str, Any]]:
    repo = _repo(incident_id)
    query: Dict[str, Any] = {"incident_id": incident_id} if incident_id else {}
    if status:
        query["status"] = status
    if owner_person_record is not None:
        query["owner_person_record"] = owner_person_record
    if template_id is not None:
        query["template_id"] = template_id
    if linked_record_type:
        query["linked_record.record_type"] = linked_record_type
    if linked_record_id:
        query["linked_record.record_id"] = linked_record_id
    rows = repo.find_many(query, sort=[("created_at", -1)])
    return [_serialize(row) for row in rows]


@router.get("/incidents/{incident_id}/checklists")
def list_checklists(
    incident_id: str,
    status: Optional[str] = Query(default=None),
    owner_person_record: Optional[int] = Query(default=None),
    template_id: Optional[int] = Query(default=None),
    linked_record_type: Optional[str] = Query(default=None),
    linked_record_id: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """List/filter checklists for this incident.

    ``linked_record_type``/``linked_record_id`` together satisfy "listing
    checklists associated with another SARApp record" — a caller in any
    module filters on its own record's type/id rather than this router
    needing a separate route per linking module.
    """

    return _list_impl(
        incident_id, status, owner_person_record, template_id, linked_record_type, linked_record_id
    )


@router.get("/checklists")
def list_standalone_checklists(
    status: Optional[str] = Query(default=None),
    owner_person_record: Optional[int] = Query(default=None),
    template_id: Optional[int] = Query(default=None),
    linked_record_type: Optional[str] = Query(default=None),
    linked_record_id: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    return _list_impl(
        None, status, owner_person_record, template_id, linked_record_type, linked_record_id
    )


@router.get("/incidents/{incident_id}/checklists/{checklist_id}")
def get_checklist(incident_id: str, checklist_id: str) -> Dict[str, Any]:
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    return _serialize(doc)


@router.get("/checklists/{checklist_id}")
def get_standalone_checklist(checklist_id: str) -> Dict[str, Any]:
    repo = _repo(None)
    doc = _get_checklist_or_404(repo, None, checklist_id)
    return _serialize(doc)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

def _record_response_impl(
    incident_id: Optional[str],
    checklist_id: str,
    item_id: str,
    body: RecordResponseRequest,
    authorization: Optional[str],
) -> Dict[str, Any]:
    """Validate and persist one item's response.

    The actual write is a targeted, atomic Mongo `$push`/`$set` against
    just this item (via `array_filters`), not a read-modify-write of the
    whole `sections` document field — so two users responding to two
    *different* items on the same checklist at the same time can never
    clobber each other's update, and a concurrent response to the *same*
    item is still an atomic append to that item's history (whichever write
    lands last simply becomes the new current response; the one it
    replaced stays in history with its own original author/timestamp).
    """

    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    if doc.get("status") == svc.ARCHIVED:
        raise HTTPException(409, "Cannot record a response on an archived checklist")

    _section, item = svc.find_item(doc.get("sections") or [], item_id)
    if item is None:
        raise HTTPException(404, "Checklist item not found")

    try:
        value, na = svc.validate_and_normalize_response(item, body.value, body.na)
    except svc.ChecklistValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    entry = svc.build_response_entry(value, na, body.notes, actor_id)

    repo.apply_update(
        checklist_id,
        {
            "$push": {"sections.$[sec].items.$[it].history": entry},
            "$set": {"sections.$[sec].items.$[it].response": entry},
        },
        array_filters=[{"sec.items.id": item_id}, {"it.id": item_id}],
    )
    # Not-started -> in-progress happens automatically on the first response,
    # as its own atomic, conditional write: it only applies while the
    # checklist is still "not_started", so it can never race a concurrent
    # explicit status change into clobbering it.
    repo.update_one(
        checklist_id, {"status": svc.IN_PROGRESS}, extra_filter={"status": svc.NOT_STARTED}
    )

    updated = repo.find_by_id(checklist_id)
    _section, updated_item = svc.find_item((updated or doc).get("sections") or [], item_id)
    return {"item": updated_item, "response": entry, "checklist": _serialize(updated or doc)}


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/items/{item_id}/responses")
def record_item_response(
    incident_id: str,
    checklist_id: str,
    item_id: str,
    body: RecordResponseRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _record_response_impl(incident_id, checklist_id, item_id, body, authorization)


@router.post("/checklists/{checklist_id}/items/{item_id}/responses")
def record_standalone_item_response(
    checklist_id: str,
    item_id: str,
    body: RecordResponseRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _record_response_impl(None, checklist_id, item_id, body, authorization)


def _item_history_impl(incident_id: Optional[str], checklist_id: str, item_id: str) -> Dict[str, Any]:
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    _section, item = svc.find_item(doc.get("sections") or [], item_id)
    if item is None:
        raise HTTPException(404, "Checklist item not found")
    return {"item_id": item_id, "history": item.get("history") or []}


@router.get("/incidents/{incident_id}/checklists/{checklist_id}/items/{item_id}/responses")
def get_item_response_history(incident_id: str, checklist_id: str, item_id: str) -> Dict[str, Any]:
    return _item_history_impl(incident_id, checklist_id, item_id)


@router.get("/checklists/{checklist_id}/items/{item_id}/responses")
def get_standalone_item_response_history(checklist_id: str, item_id: str) -> Dict[str, Any]:
    return _item_history_impl(None, checklist_id, item_id)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

def _progress_impl(incident_id: Optional[str], checklist_id: str) -> Dict[str, Any]:
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    sections = doc.get("sections") or []
    progress = svc.compute_progress(sections)

    failures = []
    for _section, item in svc.iter_items(sections):
        if item["id"] in progress["failed_items"]:
            failures.append({"item_id": item["id"], "label": item.get("label", "")})

    return {"checklist_id": checklist_id, **progress, "unresolved_failures": failures}


@router.get("/incidents/{incident_id}/checklists/{checklist_id}/progress")
def get_checklist_progress(incident_id: str, checklist_id: str) -> Dict[str, Any]:
    return _progress_impl(incident_id, checklist_id)


@router.get("/checklists/{checklist_id}/progress")
def get_standalone_checklist_progress(checklist_id: str) -> Dict[str, Any]:
    return _progress_impl(None, checklist_id)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def _update_status_impl(
    incident_id: Optional[str],
    checklist_id: str,
    body: StatusUpdateRequest,
    authorization: Optional[str],
) -> Dict[str, Any]:
    _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    current_status = doc.get("status") or svc.NOT_STARTED

    try:
        svc.apply_status_transition(current_status, body.status)
    except svc.ChecklistValidationError as exc:
        raise HTTPException(409, str(exc)) from exc

    now = _utcnow()
    updates: Dict[str, Any] = {"status": body.status}
    if body.status == svc.COMPLETED:
        updates["completed_at"] = now
    elif body.status == svc.ARCHIVED:
        updates["archived_at"] = now
    elif current_status == svc.COMPLETED and body.status == svc.IN_PROGRESS:
        # Reopening clears the prior completion stamp.
        updates["completed_at"] = None

    repo.update_one(checklist_id, updates)
    updated = repo.find_by_id(checklist_id)
    return _serialize(updated or doc)


@router.patch("/incidents/{incident_id}/checklists/{checklist_id}/status")
def update_checklist_status(
    incident_id: str,
    checklist_id: str,
    body: StatusUpdateRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _update_status_impl(incident_id, checklist_id, body, authorization)


@router.patch("/checklists/{checklist_id}/status")
def update_standalone_checklist_status(
    checklist_id: str, body: StatusUpdateRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _update_status_impl(None, checklist_id, body, authorization)
