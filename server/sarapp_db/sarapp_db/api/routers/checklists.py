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

Phase 4B adds explicit lifecycle actions — `complete`, `reopen`, `archive`
— in place of Phase 4A's generic status PATCH (removed: a bare status
write could bypass completion validation, so there is no longer any way
to set `status` except through these three guarded actions). Each action:
  - Resolves the authenticated actor the same way every other write here
    does. There is still no repo-wide role/permission layer (see the
    module-level note above) — "authorized user" here means the same
    thing Phase 4A's authorization already means: a real, signed-in
    session, never a bare client-supplied id. This is the ceiling the
    rest of this codebase has today; see `agents.md`'s constraint against
    inventing a new permissions framework.
  - Claims the transition with one atomic, conditional Mongo update keyed
    on both the expected current `status` AND an optimistic-concurrency
    counter (`lifecycle_event_seq`) — see `_claim_transition` — so two
    concurrent completion attempts can never both succeed, without real
    multi-document transactions (this deployment's MongoDB is not
    guaranteed to run as a replica set, so `session.start_transaction()`
    is not available; every write here already relies on single-document
    atomicity + unique indexes + idempotency-hash dedup instead, the same
    pattern `ics214.py`'s own `void_entry`/`_insert_entry` use).
  - Appends one `checklist_service.build_lifecycle_entry` row to the
    checklist's own `lifecycle_history` (durable, never pruned, still
    readable after archiving) and, for an incident-scoped checklist, also
    calls `mongo.audit.write_audit` into the incident's shared
    `AUDIT_LOGS` collection — reusing existing audit infrastructure rather
    than inventing a parallel one, per `plannedtoolkit.py`'s precedent.
  - For an incident-scoped checklist, writes an ICS-214 entry via
    `ics214._insert_entry` for completion/recompletion/reopening (never
    for archiving, and never for an individual item response — see
    `_write_ics214_lifecycle_entry`) using a deterministic
    `idempotency_hash` derived from the checklist id, the action, and the
    post-claim `lifecycle_event_seq`, so a retried request — or the
    `/ics214/retry` recovery endpoint below — can never produce a
    duplicate entry. A standalone checklist never writes to ICS-214; its
    lifecycle is recorded only in its own `lifecycle_history`.
  - If that ICS-214 write fails, the checklist's lifecycle transition has
    already committed (it is a legitimate state regardless of logging
    success) but the lifecycle-history entry and the checklist's own
    `ics214_pending` flag record that the write still needs retrying —
    POST `.../ics214/retry` re-attempts it with the same stored
    idempotency hash and text, so nothing is lost to an in-memory retry
    queue or process-local state.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.api.routers.checklist_templates import (
    ChecklistTemplateSection,
    ChecklistTemplatesRepository,
)
from sarapp_db.api.routers.checklist_templates import _record_field as _template_record_field
from sarapp_db.ics_reference import BUILTIN_LOG_KEYS
from sarapp_db.mongo.audit import write_audit
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.errors import AuditWriteError
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services import checklist_service as svc

logger = logging.getLogger(__name__)

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
        "linked_records": doc.get("linked_records") or [],
        "status": str(doc.get("status") or svc.NOT_STARTED),
        "sections": doc.get("sections") or [],
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
        "created_by": doc.get("created_by"),
        "completed_at": doc.get("completed_at"),
        "completed_by": doc.get("completed_by"),
        "archived_at": doc.get("archived_at"),
        "archived_by": doc.get("archived_by"),
        "lifecycle_event_seq": int(doc.get("lifecycle_event_seq") or 0),
        "ics214_stream": doc.get("ics214_stream"),
        "ics214_entry_id": doc.get("ics214_entry_id"),
        "ics214_pending": bool(doc.get("ics214_pending")),
        "lifecycle_history": doc.get("lifecycle_history") or [],
    }


def _checklist_ref(doc: Dict[str, Any]) -> str:
    """Human-readable "[identifier]" for ICS-214 text — the same int_id a
    read already shows the user, falling back to the raw id if somehow
    unset."""

    return str(doc.get("int_id") or doc.get("_id") or "")


def _actor_display(person_record: Optional[int]) -> str:
    """"F. Last"-style display name for ``person_record``, falling back to
    the raw id when no personnel record resolves (e.g. a test actor id with
    no roster entry) — never blank."""

    if person_record is None:
        return ""
    fallback = str(person_record)
    try:
        person = get_master_db()[MasterCollections.PERSONNEL].find_one(
            {"person_record": person_record}
        )
    except Exception:
        return fallback
    if not person:
        return fallback
    return svc.format_person_display(
        str(person.get("first_name") or ""), str(person.get("last_name") or ""), fallback=fallback
    )


def _write_checklist_audit(
    incident_id: Optional[str], checklist_id: str, action: str, actor_id: int, old_status: str, new_status: str
) -> None:
    """Best-effort shared-audit-log write; never blocks the lifecycle action itself."""

    if not incident_id:
        return
    try:
        write_audit(
            get_incident_db(incident_id),
            incident_id=incident_id,
            entity_type="checklist",
            entity_id=checklist_id,
            action=action,
            changed_by=str(actor_id),
            field_changes=[{"field": "status", "old_value": old_status, "new_value": new_status}],
            source_module="checklists",
        )
    except AuditWriteError:
        logger.exception("Failed to write audit record for checklist %s/%s", checklist_id, action)


def _resolve_stream(
    incident_id: str, doc: Dict[str, Any], requested: Optional["StreamSelectionPayload"]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve the ICS-214 stream for an incident-scoped lifecycle action.

    Priority, per the product spec:
      1. A stream already explicitly associated with this checklist
         (persisted on an earlier create/complete/reopen call).
      2. An associated operational record with an unambiguous section or
         unit — there is no cross-module resolver registered for this in
         the current codebase (nothing maps an arbitrary `linked_record`
         to an ICS-214 stream), so this step is a documented no-op today
         rather than a guess; a future module could register one.
      3. A stream explicitly selected by the caller on this request.

    Returns ``(stream_dict, None)`` on success or ``(None, error_detail)``
    when no stream can be resolved — the caller must then require a valid
    selection before completing or reopening, per spec, rather than
    guessing among plausible streams.
    """

    existing = doc.get("ics214_stream")
    if existing:
        return existing, None

    # Priority 2 extension point — intentionally unimplemented (see docstring).

    if requested is None:
        return None, "An ICS-214 stream must be selected before completing or reopening this checklist."

    stream = requested.model_dump()
    if not stream["log_keys"] and not stream["org_unit_ids"] and not stream["incident_wide"]:
        return None, "A stream selection must set log_keys, org_unit_ids, or incident_wide."
    unknown_keys = set(stream["log_keys"]) - BUILTIN_LOG_KEYS
    if unknown_keys:
        return None, f"Unknown ICS-214 log key(s): {', '.join(sorted(unknown_keys))}"
    if stream["org_unit_ids"]:
        org_db = get_incident_db(incident_id)
        found = {
            row["position_id"]
            for row in org_db[IncidentCollections.INCIDENT_ORG].find(
                {"position_id": {"$in": stream["org_unit_ids"]}}, {"position_id": 1}
            )
        }
        missing = set(stream["org_unit_ids"]) - found
        if missing:
            return None, (
                "org_unit_ids not found in this incident's organization: "
                f"{sorted(missing)}"
            )
    return stream, None


def _ics214_idempotency_hash(checklist_id: str, action: str, seq: int) -> str:
    import hashlib

    return hashlib.sha256(f"checklist-{action}:{checklist_id}:{seq}".encode()).hexdigest()


def _format_completion_text(
    name: str, actor_display: str, summary: Dict[str, Any], checklist_ref: str, recompletion: bool
) -> str:
    verb = "recompleted" if recompletion else "completed"
    failures = summary["unresolved_failures"]
    if failures:
        count = len(failures)
        suffix = f"; {count} unresolved failed inspection{'s' if count != 1 else ''}"
    else:
        suffix = ""
    return (
        f"{name} {verb} by {actor_display}. "
        f"{summary['answered_applicable_items']}/{summary['applicable_items']} "
        f"applicable items answered{suffix}. Checklist reference: [{checklist_ref}]."
    )


def _format_reopen_text(name: str, actor_display: str, reason: str, checklist_ref: str) -> str:
    return (
        f"{name} reopened by {actor_display}. Reason: {reason}. "
        f"Checklist reference: [{checklist_ref}]."
    )


def _write_ics214_lifecycle_entry(
    incident_id: str,
    doc: Dict[str, Any],
    text: str,
    stream: Dict[str, Any],
    idempotency_hash: str,
    actor_display: str,
) -> Dict[str, Any]:
    from sarapp_db.api.routers.ics214 import EntryCreate, SourceRecord, _insert_entry

    entry = EntryCreate(
        text=text,
        log_keys=list(stream.get("log_keys") or []),
        org_unit_ids=list(stream.get("org_unit_ids") or []),
        incident_wide=bool(stream.get("incident_wide")),
        source="checklists",
        created_by=actor_display,
        source_record=SourceRecord(collection=IncidentCollections.CHECKLISTS, record_id=str(doc["_id"])),
        idempotency_hash=idempotency_hash,
    )
    return _insert_entry(incident_id, entry)


def _claim_transition(
    repo, checklist_id: str, expected_seq: int, from_statuses: Tuple[str, ...], extra_set: Dict[str, Any]
) -> bool:
    """Atomically move the checklist into a new lifecycle state.

    Matches only when both the checklist's current `status` is still one
    of `from_statuses` AND `lifecycle_event_seq` still equals the value
    this request read earlier — the second check is what makes two
    concurrent completion attempts unable to both succeed even though
    Mongo here has no multi-document transactions: whichever request's
    conditional update lands first increments the counter, so the loser's
    update matches zero documents and gets a 409 instead of a second,
    conflicting completion.
    """

    return repo.apply_update(
        checklist_id,
        {"$set": extra_set, "$inc": {"lifecycle_event_seq": 1}},
        extra_filter={"status": {"$in": list(from_statuses)}, "lifecycle_event_seq": expected_seq},
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LinkedRecordPayload(BaseModel):
    """A stable reference to another SARApp record, not a database foreign
    key — this collection never joins against the referenced record, so it
    has no dependency on what that record's module is (Planned Events or
    anything else). ``record_type`` must be one of `_LINKABLE_RECORD_RESOLVERS`
    (Phase 4D) — the one place this module knows about specific other
    modules' record shapes, kept intentionally small and closed rather than
    a generic cross-module relationship framework."""

    record_type: str
    record_id: str


class LinkRecordRequest(LinkedRecordPayload):
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


# A checklist's `linked_records` entries reference one of these record
# types. Each maps to the (collection, id_field) that type's owning router
# already uses, so existence/incident-scope validation re-queries that same
# collection rather than trusting a client-submitted id — see
# `_validate_linkable_record`. Adding a new linkable type means adding one
# entry here, not a new framework.
_LINKABLE_RECORD_RESOLVERS: Dict[str, Tuple[str, str]] = {
    "planned_schedule_item": (IncidentCollections.PLANNED_EVENT_SCHEDULES, "schedule_id"),
    "planned_quick_assignment": (IncidentCollections.PLANNED_QUICK_ASSIGNMENTS, "quick_assignment_id"),
    "operations_task": (IncidentCollections.OPERATIONS_TASKS, "task_id"),
}


def _validate_linkable_record(incident_id: str, record_type: str, record_id: str) -> Optional[str]:
    """Returns an error message, or None if ``record_type``/``record_id``
    is a real record in this incident.

    Every target collection's documents carry their own `incident_id`
    field (the same convention `plannedtoolkit.py`'s own
    `_find_by_compound_id` relies on), so checking both the id field and
    `incident_id` in one query validates existence and incident-ownership
    together — never trusting a client-submitted id or label on faith.
    """

    resolver = _LINKABLE_RECORD_RESOLVERS.get(record_type)
    if resolver is None:
        return f"Unknown record_type: {record_type!r}"
    collection_name, id_field = resolver
    db = get_incident_db(incident_id)
    doc = db[collection_name].find_one({id_field: record_id, "incident_id": incident_id})
    if doc is None:
        return f"No {record_type} {record_id!r} was found in this incident"
    return None


class StreamSelectionPayload(BaseModel):
    """An ICS-214 "stream" is a set of membership tags on an entry, not a
    stored stream object (see `ics214.py`'s own module docstring) — this is
    the same `log_keys`/`org_unit_ids`/`incident_wide` shape `EntryCreate`
    accepts, reused here rather than inventing a second section/unit
    hierarchy. At least one of the three must be set."""

    log_keys: list[str] = Field(default_factory=list)
    org_unit_ids: list[int] = Field(default_factory=list)
    incident_wide: bool = False


class CreateBlankChecklistRequest(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    sections: list[ChecklistTemplateSection] = Field(min_length=1)
    owner_person_record: Optional[int] = None
    linked_records: list[LinkedRecordPayload] = Field(default_factory=list)
    stream: Optional[StreamSelectionPayload] = None
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class CreateFromTemplateRequest(BaseModel):
    template_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    owner_person_record: Optional[int] = None
    linked_records: list[LinkedRecordPayload] = Field(default_factory=list)
    stream: Optional[StreamSelectionPayload] = None
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class RecordResponseRequest(BaseModel):
    value: Any = None
    na: bool = False
    notes: str = ""
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class ValidateCompletionRequest(BaseModel):
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class CompleteChecklistRequest(BaseModel):
    acknowledge_failures: bool = False
    stream: Optional[StreamSelectionPayload] = None
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class ReopenChecklistRequest(BaseModel):
    reason: str
    stream: Optional[StreamSelectionPayload] = None
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class ArchiveChecklistRequest(BaseModel):
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


class Ics214RetryRequest(BaseModel):
    session_id: Optional[str] = None
    actor_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def _new_doc_lifecycle_fields(
    incident_id: Optional[str], actor_id: int, stream: Optional[StreamSelectionPayload], now: str
) -> Dict[str, Any]:
    """Fields every new checklist (blank or from-template) starts with.

    A caller may explicitly associate an ICS-214 stream at creation time
    (priority 1 of the stream-resolution order in the module docstring);
    an unvalidated, syntactically-empty selection is simply not persisted
    rather than rejected, since a stream is only required at completion/
    reopening time, not at creation.
    """

    stream_dict = None
    if incident_id and stream is not None:
        candidate = stream.model_dump()
        if candidate["log_keys"] or candidate["org_unit_ids"] or candidate["incident_wide"]:
            unknown_keys = set(candidate["log_keys"]) - BUILTIN_LOG_KEYS
            if unknown_keys:
                raise HTTPException(422, f"Unknown ICS-214 log key(s): {', '.join(sorted(unknown_keys))}")
            stream_dict = candidate

    actor_display = _actor_display(actor_id)
    created_entry = svc.build_lifecycle_entry(
        action=svc.ACTION_CREATED,
        from_status=None,
        to_status=svc.NOT_STARTED,
        actor_id=actor_id,
        actor_display=actor_display,
        timestamp=now,
    )
    return {
        "status": svc.NOT_STARTED,
        "created_by": actor_id,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "completed_by": None,
        "archived_at": None,
        "archived_by": None,
        "lifecycle_event_seq": 0,
        "ics214_stream": stream_dict,
        "ics214_entry_id": None,
        "ics214_pending": False,
        "lifecycle_history": [created_entry],
    }


def _resolve_linked_records_for_create(
    incident_id: Optional[str], payloads: list[LinkedRecordPayload]
) -> list[Dict[str, Any]]:
    """Validate and normalize `linked_records` supplied at creation time.

    A standalone checklist (``incident_id`` is None) has no incident whose
    records it could validate against, so it may only be created with an
    empty list — per the product spec, a standalone checklist must not be
    linked to an incident-specific record without first establishing a
    valid incident association through an explicitly supported workflow,
    which does not exist yet.
    """

    if not payloads:
        return []
    if not incident_id:
        raise HTTPException(400, "A standalone checklist cannot be linked to incident-specific records")
    resolved: list[Dict[str, Any]] = []
    for payload in payloads:
        error = _validate_linkable_record(incident_id, payload.record_type, payload.record_id)
        if error:
            raise HTTPException(422, error)
        resolved.append(payload.model_dump())
    return resolved


def _create_blank_impl(
    incident_id: Optional[str], body: CreateBlankChecklistRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    linked_records = _resolve_linked_records_for_create(incident_id, body.linked_records)
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
            "linked_records": linked_records,
            "sections": sections,
            **_new_doc_lifecycle_fields(incident_id, actor_id, body.stream, now),
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
    linked_records = _resolve_linked_records_for_create(incident_id, body.linked_records)
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
            "linked_records": linked_records,
            "sections": sections,
            **_new_doc_lifecycle_fields(incident_id, actor_id, body.stream, now),
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
    if linked_record_type or linked_record_id:
        elem_match: Dict[str, Any] = {}
        if linked_record_type:
            elem_match["record_type"] = linked_record_type
        if linked_record_id:
            elem_match["record_id"] = linked_record_id
        # $elemMatch (not two top-level dotted conditions) so a checklist
        # linked to {type A, id 1} and {type B, id 2} doesn't falsely match
        # a filter for {type A, id 2} by satisfying each half from a
        # different array entry.
        query["linked_records"] = {"$elemMatch": elem_match}
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
# Associated records (Phase 4D)
#
# A checklist's `linked_records` is a flat list of {record_type, record_id}
# — the reverse direction of the exact same reference every
# `linked_record_type`/`linked_record_id` list filter already reads
# (see `_list_impl`). Linking/unlinking happens here rather than through
# the generic create/update payload so a caller (Planned Events' Schedule
# or Assignment "Checklists" section today) can associate or remove a
# link against an existing checklist without resubmitting its sections.
# ---------------------------------------------------------------------------

def _add_link_impl(
    incident_id: Optional[str], checklist_id: str, body: LinkRecordRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)

    if not incident_id:
        raise HTTPException(400, "A standalone checklist cannot be linked to incident-specific records")
    error = _validate_linkable_record(incident_id, body.record_type, body.record_id)
    if error:
        raise HTTPException(422, error)

    existing_links = doc.get("linked_records") or []
    if any(
        link.get("record_type") == body.record_type and link.get("record_id") == body.record_id
        for link in existing_links
    ):
        raise HTTPException(409, "This checklist is already linked to that record")

    link = {"record_type": body.record_type, "record_id": body.record_id}
    repo.apply_update(checklist_id, {"$push": {"linked_records": link}})
    updated = repo.find_by_id(checklist_id)
    return _serialize(updated or doc)


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/links", status_code=201)
def add_checklist_link(
    incident_id: str,
    checklist_id: str,
    body: LinkRecordRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _add_link_impl(incident_id, checklist_id, body, authorization)


@router.post("/checklists/{checklist_id}/links", status_code=201)
def add_standalone_checklist_link(
    checklist_id: str, body: LinkRecordRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _add_link_impl(None, checklist_id, body, authorization)


def _remove_link_impl(
    incident_id: Optional[str], checklist_id: str, body: LinkRecordRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    link = {"record_type": body.record_type, "record_id": body.record_id}
    repo.apply_update(checklist_id, {"$pull": {"linked_records": link}})
    updated = repo.find_by_id(checklist_id)
    return _serialize(updated or doc)


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/links/remove")
def remove_checklist_link(
    incident_id: str,
    checklist_id: str,
    body: LinkRecordRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _remove_link_impl(incident_id, checklist_id, body, authorization)


@router.post("/checklists/{checklist_id}/links/remove")
def remove_standalone_checklist_link(
    checklist_id: str, body: LinkRecordRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _remove_link_impl(None, checklist_id, body, authorization)


def propagate_link_to_promoted_task(
    incident_id: str, old_record_type: str, old_record_id: str, new_record_type: str, new_record_id: str
) -> int:
    """Add ``{new_record_type, new_record_id}`` to every checklist already
    linked to ``{old_record_type, old_record_id}``, without removing the
    original link.

    For another router (`plannedtoolkit.py`'s Assignment-promotion
    endpoint) to call directly after creating the formal Operations task,
    so a checklist linked to a promoted planned-event Assignment gains a
    second link to the resulting task — never a second checklist instance,
    never losing the original Assignment association. Idempotent: a
    checklist that already carries the new link is left alone, so a
    promotion retry can call this again safely. Returns how many
    checklists were updated, for the caller's own logging.
    """

    repo = _repo(incident_id)
    candidates = repo.find_many(
        {
            "incident_id": incident_id,
            "linked_records": {"$elemMatch": {"record_type": old_record_type, "record_id": old_record_id}},
        }
    )
    updated_count = 0
    new_link = {"record_type": new_record_type, "record_id": new_record_id}
    for candidate in candidates:
        already_linked = any(
            link.get("record_type") == new_record_type and link.get("record_id") == new_record_id
            for link in candidate.get("linked_records") or []
        )
        if already_linked:
            continue
        repo.apply_update(str(candidate["_id"]), {"$push": {"linked_records": new_link}})
        updated_count += 1
    return updated_count


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
    current_status = doc.get("status") or svc.NOT_STARTED
    if current_status in (svc.COMPLETED, svc.ARCHIVED):
        raise HTTPException(
            409, f"Cannot record a response on a {current_status.replace('_', ' ')} checklist"
        )

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
# Completion validation (Stage 1)
# ---------------------------------------------------------------------------

def _validate_completion_impl(
    incident_id: Optional[str], checklist_id: str, body: ValidateCompletionRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    """Stage 1 of the two-stage completion workflow: a read-only dry run.

    Returns the same structured fields `complete` itself re-checks at
    finalization time — this response is advisory only and is never relied
    on as still accurate by `complete`, which revalidates independently
    (other users may have changed responses in between).
    """

    _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    current_status = doc.get("status") or svc.NOT_STARTED
    status_permits_completion = current_status in (svc.NOT_STARTED, svc.IN_PROGRESS)
    validation = svc.validate_completion(doc.get("sections") or [])

    ics214_stream_required = False
    ics214_stream_error = None
    if incident_id and not doc.get("ics214_stream"):
        _stream, ics214_stream_error = _resolve_stream(incident_id, doc, None)
        ics214_stream_required = True

    return {
        "checklist_id": checklist_id,
        "current_status": current_status,
        "status_permits_completion": status_permits_completion,
        **validation,
        "can_complete": validation["can_complete"] and status_permits_completion,
        "ics214_stream_required": ics214_stream_required,
        "ics214_stream_error": ics214_stream_error,
    }


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/validate-completion")
def validate_checklist_completion(
    incident_id: str,
    checklist_id: str,
    body: ValidateCompletionRequest = ValidateCompletionRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _validate_completion_impl(incident_id, checklist_id, body, authorization)


@router.post("/checklists/{checklist_id}/validate-completion")
def validate_standalone_checklist_completion(
    checklist_id: str,
    body: ValidateCompletionRequest = ValidateCompletionRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _validate_completion_impl(None, checklist_id, body, authorization)


# ---------------------------------------------------------------------------
# Complete (Stage 2 finalization)
# ---------------------------------------------------------------------------

def _complete_impl(
    incident_id: Optional[str], checklist_id: str, body: CompleteChecklistRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    current_status = doc.get("status") or svc.NOT_STARTED

    if current_status not in (svc.NOT_STARTED, svc.IN_PROGRESS):
        raise HTTPException(409, f"Cannot complete a checklist from status '{current_status}'")

    sections = doc.get("sections") or []
    validation = svc.validate_completion(sections)
    if validation["missing_required"] or validation["invalid_responses"]:
        raise HTTPException(422, {"detail": "Checklist is not ready to complete", **validation})
    if validation["requires_acknowledgment"] and not body.acknowledge_failures:
        raise HTTPException(
            409, {"detail": "Unresolved failures require explicit acknowledgment", **validation}
        )

    stream: Optional[Dict[str, Any]] = None
    if incident_id:
        stream, stream_error = _resolve_stream(incident_id, doc, body.stream)
        if stream_error:
            raise HTTPException(422, {"detail": stream_error, "ics214_stream_required": True})

    recompletion = bool(doc.get("completed_at"))
    action = svc.ACTION_RECOMPLETED if recompletion else svc.ACTION_COMPLETED
    expected_seq = int(doc.get("lifecycle_event_seq") or 0)
    now = _utcnow()
    actor_display = _actor_display(actor_id)
    summary = svc.build_completion_summary(sections)

    # Revalidate-then-claim: this `_claim_transition` is the actual
    # concurrency guard (see its docstring) — the validation above can be
    # stale by the time this runs, but a losing concurrent request simply
    # gets a 409 here and must re-validate/retry, never a second
    # completion of the same state.
    claimed = _claim_transition(
        repo,
        checklist_id,
        expected_seq,
        (svc.NOT_STARTED, svc.IN_PROGRESS),
        {
            "status": svc.COMPLETED,
            "completed_at": now,
            "completed_by": actor_id,
            "ics214_stream": stream,
        },
    )
    if not claimed:
        raise HTTPException(
            409, "This checklist was changed by another request; re-validate and retry completion"
        )
    new_seq = expected_seq + 1

    ics214_entry_id: Optional[str] = None
    ics214_pending = False
    ics214_text: Optional[str] = None
    idempotency_hash: Optional[str] = None
    if incident_id:
        checklist_ref = _checklist_ref(doc)
        ics214_text = _format_completion_text(
            doc.get("name") or "", actor_display, summary, checklist_ref, recompletion
        )
        idempotency_hash = _ics214_idempotency_hash(checklist_id, action, new_seq)
        try:
            entry = _write_ics214_lifecycle_entry(incident_id, doc, ics214_text, stream, idempotency_hash, actor_display)
            ics214_entry_id = entry.get("id")
        except Exception:
            logger.exception("ICS-214 completion entry failed for checklist %s; marked pending", checklist_id)
            ics214_pending = True

    lifecycle_entry = svc.build_lifecycle_entry(
        action=action,
        from_status=current_status,
        to_status=svc.COMPLETED,
        actor_id=actor_id,
        actor_display=actor_display,
        timestamp=now,
        acknowledged_failures=bool(validation["requires_acknowledgment"]) or None,
        summary=summary,
        ics214_text=ics214_text,
        ics214_stream=stream,
        ics214_idempotency_hash=idempotency_hash,
        ics214_entry_id=ics214_entry_id,
        ics214_pending=ics214_pending,
    )
    repo.apply_update(
        checklist_id,
        {
            "$push": {"lifecycle_history": lifecycle_entry},
            "$set": {"ics214_entry_id": ics214_entry_id, "ics214_pending": ics214_pending},
        },
    )
    _write_checklist_audit(incident_id, checklist_id, action, actor_id, current_status, svc.COMPLETED)

    updated = repo.find_by_id(checklist_id)
    return {
        "checklist": _serialize(updated or doc),
        "summary": summary,
        "ics214_entry_id": ics214_entry_id,
        "ics214_pending": ics214_pending,
    }


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/complete")
def complete_checklist(
    incident_id: str,
    checklist_id: str,
    body: CompleteChecklistRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _complete_impl(incident_id, checklist_id, body, authorization)


@router.post("/checklists/{checklist_id}/complete")
def complete_standalone_checklist(
    checklist_id: str, body: CompleteChecklistRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _complete_impl(None, checklist_id, body, authorization)


# ---------------------------------------------------------------------------
# Reopen
# ---------------------------------------------------------------------------

def _reopen_impl(
    incident_id: Optional[str], checklist_id: str, body: ReopenChecklistRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    current_status = doc.get("status") or svc.NOT_STARTED

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(422, "A reason is required to reopen a checklist")
    # Reopen is deliberately narrower than the bare state machine: only a
    # Completed checklist can be reopened (an Archived one cannot — Phase
    # 4B does not implement unarchiving, and Not Started/In Progress are
    # already open for responses).
    if current_status != svc.COMPLETED:
        raise HTTPException(409, f"Only a completed checklist can be reopened (current: {current_status})")

    stream: Optional[Dict[str, Any]] = None
    if incident_id:
        stream, stream_error = _resolve_stream(incident_id, doc, body.stream)
        if stream_error:
            raise HTTPException(422, {"detail": stream_error, "ics214_stream_required": True})

    expected_seq = int(doc.get("lifecycle_event_seq") or 0)
    now = _utcnow()
    actor_display = _actor_display(actor_id)

    claimed = _claim_transition(
        repo,
        checklist_id,
        expected_seq,
        (svc.COMPLETED,),
        {"status": svc.IN_PROGRESS, "ics214_stream": stream},
    )
    if not claimed:
        raise HTTPException(409, "This checklist was changed by another request; retry reopening")
    new_seq = expected_seq + 1

    ics214_entry_id: Optional[str] = None
    ics214_pending = False
    ics214_text: Optional[str] = None
    idempotency_hash: Optional[str] = None
    if incident_id:
        ics214_text = _format_reopen_text(doc.get("name") or "", actor_display, reason, _checklist_ref(doc))
        idempotency_hash = _ics214_idempotency_hash(checklist_id, svc.ACTION_REOPENED, new_seq)
        try:
            entry = _write_ics214_lifecycle_entry(
                incident_id, doc, ics214_text, stream, idempotency_hash, actor_display
            )
            ics214_entry_id = entry.get("id")
        except Exception:
            logger.exception("ICS-214 reopen entry failed for checklist %s; marked pending", checklist_id)
            ics214_pending = True

    lifecycle_entry = svc.build_lifecycle_entry(
        action=svc.ACTION_REOPENED,
        from_status=current_status,
        to_status=svc.IN_PROGRESS,
        actor_id=actor_id,
        actor_display=actor_display,
        timestamp=now,
        reason=reason,
        ics214_text=ics214_text,
        ics214_stream=stream,
        ics214_idempotency_hash=idempotency_hash,
        ics214_entry_id=ics214_entry_id,
        ics214_pending=ics214_pending,
    )
    repo.apply_update(
        checklist_id,
        {
            "$push": {"lifecycle_history": lifecycle_entry},
            "$set": {"ics214_entry_id": ics214_entry_id, "ics214_pending": ics214_pending},
        },
    )
    _write_checklist_audit(incident_id, checklist_id, svc.ACTION_REOPENED, actor_id, current_status, svc.IN_PROGRESS)

    updated = repo.find_by_id(checklist_id)
    return {
        "checklist": _serialize(updated or doc),
        "ics214_entry_id": ics214_entry_id,
        "ics214_pending": ics214_pending,
    }


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/reopen")
def reopen_checklist(
    incident_id: str,
    checklist_id: str,
    body: ReopenChecklistRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _reopen_impl(incident_id, checklist_id, body, authorization)


@router.post("/checklists/{checklist_id}/reopen")
def reopen_standalone_checklist(
    checklist_id: str, body: ReopenChecklistRequest, authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    return _reopen_impl(None, checklist_id, body, authorization)


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------

def _archive_impl(
    incident_id: Optional[str], checklist_id: str, body: ArchiveChecklistRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    actor_id = _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    current_status = doc.get("status") or svc.NOT_STARTED

    try:
        svc.apply_status_transition(current_status, svc.ARCHIVED)
    except svc.ChecklistValidationError as exc:
        raise HTTPException(409, str(exc)) from exc

    expected_seq = int(doc.get("lifecycle_event_seq") or 0)
    now = _utcnow()
    actor_display = _actor_display(actor_id)

    claimed = _claim_transition(
        repo,
        checklist_id,
        expected_seq,
        (svc.NOT_STARTED, svc.IN_PROGRESS, svc.COMPLETED),
        {"status": svc.ARCHIVED, "archived_at": now, "archived_by": actor_id},
    )
    if not claimed:
        raise HTTPException(409, "This checklist was changed by another request; retry archiving")

    # Archiving is read-only going forward, not a second completion path —
    # no ICS-214 entry is written here (the spec's logging list is
    # completion/recompletion/reopening only).
    lifecycle_entry = svc.build_lifecycle_entry(
        action=svc.ACTION_ARCHIVED,
        from_status=current_status,
        to_status=svc.ARCHIVED,
        actor_id=actor_id,
        actor_display=actor_display,
        timestamp=now,
    )
    repo.apply_update(checklist_id, {"$push": {"lifecycle_history": lifecycle_entry}})
    _write_checklist_audit(incident_id, checklist_id, svc.ACTION_ARCHIVED, actor_id, current_status, svc.ARCHIVED)

    updated = repo.find_by_id(checklist_id)
    return _serialize(updated or doc)


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/archive")
def archive_checklist(
    incident_id: str,
    checklist_id: str,
    body: ArchiveChecklistRequest = ArchiveChecklistRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _archive_impl(incident_id, checklist_id, body, authorization)


@router.post("/checklists/{checklist_id}/archive")
def archive_standalone_checklist(
    checklist_id: str,
    body: ArchiveChecklistRequest = ArchiveChecklistRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _archive_impl(None, checklist_id, body, authorization)


# ---------------------------------------------------------------------------
# Lifecycle history / completion summary (read)
# ---------------------------------------------------------------------------

def _lifecycle_history_impl(
    incident_id: Optional[str], checklist_id: str, authorization: Optional[str], session_id: Optional[str], actor_id: Optional[int]
) -> Dict[str, Any]:
    # "Viewing checklist history" is one of the actions the spec calls out
    # for permission enforcement, so — unlike the open reads elsewhere in
    # this router — this requires the same authenticated-actor check as a
    # write. See the module docstring's note on this codebase's authorization
    # ceiling: there is no finer-grained role check to add on top of it.
    _resolve_actor(authorization, session_id, actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    return {"checklist_id": checklist_id, "history": doc.get("lifecycle_history") or []}


@router.get("/incidents/{incident_id}/checklists/{checklist_id}/lifecycle-history")
def get_checklist_lifecycle_history(
    incident_id: str,
    checklist_id: str,
    authorization: Optional[str] = Header(None),
    session_id: Optional[str] = Query(default=None),
    actor_id: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    return _lifecycle_history_impl(incident_id, checklist_id, authorization, session_id, actor_id)


@router.get("/checklists/{checklist_id}/lifecycle-history")
def get_standalone_checklist_lifecycle_history(
    checklist_id: str,
    authorization: Optional[str] = Header(None),
    session_id: Optional[str] = Query(default=None),
    actor_id: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    return _lifecycle_history_impl(None, checklist_id, authorization, session_id, actor_id)


def _completion_summary_impl(incident_id: Optional[str], checklist_id: str) -> Dict[str, Any]:
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)
    summary = svc.build_completion_summary(doc.get("sections") or [])
    history = doc.get("lifecycle_history") or []
    last_completion = next(
        (entry for entry in reversed(history) if entry.get("action") in (svc.ACTION_COMPLETED, svc.ACTION_RECOMPLETED)),
        None,
    )
    return {"checklist_id": checklist_id, **summary, "last_completion": last_completion}


@router.get("/incidents/{incident_id}/checklists/{checklist_id}/completion-summary")
def get_checklist_completion_summary(incident_id: str, checklist_id: str) -> Dict[str, Any]:
    return _completion_summary_impl(incident_id, checklist_id)


@router.get("/checklists/{checklist_id}/completion-summary")
def get_standalone_checklist_completion_summary(checklist_id: str) -> Dict[str, Any]:
    return _completion_summary_impl(None, checklist_id)


# ---------------------------------------------------------------------------
# ICS-214 durable retry (recovery mechanism for a lifecycle action whose
# ICS-214 write failed — see the module docstring)
# ---------------------------------------------------------------------------

def _retry_ics214_impl(
    incident_id: Optional[str], checklist_id: str, body: Ics214RetryRequest, authorization: Optional[str]
) -> Dict[str, Any]:
    if not incident_id:
        raise HTTPException(400, "Standalone checklists never write ICS-214 entries")
    _resolve_actor(authorization, body.session_id, body.actor_id)
    repo = _repo(incident_id)
    doc = _get_checklist_or_404(repo, incident_id, checklist_id)

    pending = [
        entry for entry in (doc.get("lifecycle_history") or []) if entry.get("ics214_pending")
    ]
    retried_entry_ids: List[str] = []
    for entry in pending:
        try:
            result = _write_ics214_lifecycle_entry(
                incident_id,
                doc,
                entry.get("ics214_text") or "",
                entry.get("ics214_stream") or {},
                entry["ics214_idempotency_hash"],
                entry.get("actor_display") or "",
            )
        except Exception:
            logger.exception(
                "Retry of pending ICS-214 entry %s failed for checklist %s", entry["event_id"], checklist_id
            )
            continue
        entry_id = result.get("id")
        repo.apply_update(
            checklist_id,
            {
                "$set": {
                    "lifecycle_history.$[e].ics214_entry_id": entry_id,
                    "lifecycle_history.$[e].ics214_pending": False,
                }
            },
            array_filters=[{"e.event_id": entry["event_id"]}],
        )
        retried_entry_ids.append(entry_id)

    updated = repo.find_by_id(checklist_id) or doc
    still_pending = any(entry.get("ics214_pending") for entry in updated.get("lifecycle_history") or [])
    latest_entry_id = next(
        (
            entry.get("ics214_entry_id")
            for entry in reversed(updated.get("lifecycle_history") or [])
            if entry.get("ics214_entry_id")
        ),
        None,
    )
    repo.update_one(checklist_id, {"ics214_pending": still_pending, "ics214_entry_id": latest_entry_id})

    return {
        "checklist_id": checklist_id,
        "retried": retried_entry_ids,
        "ics214_pending": still_pending,
    }


@router.post("/incidents/{incident_id}/checklists/{checklist_id}/ics214/retry")
def retry_checklist_ics214_entries(
    incident_id: str,
    checklist_id: str,
    body: Ics214RetryRequest = Ics214RetryRequest(),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    return _retry_ics214_impl(incident_id, checklist_id, body, authorization)
