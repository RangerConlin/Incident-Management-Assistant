"""Meetings router — per-incident, mirrors MeetingsRepository interface."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import _ensure_int_ids, next_int_id
from sarapp_db.mongo.repository import BaseRepository

master_router = APIRouter()
incident_router = APIRouter()


class MeetingsRepository(BaseRepository):
    collection_name = IncidentCollections.MEETINGS
    # Keyed by sequential `int_id`, not `_id`; `deleted` is a plain flag
    # managed by these handlers, not via BaseRepository.soft_delete.
    soft_deletes = False


class MeetingTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.MEETING_TEMPLATES
    soft_deletes = False


def _repo(incident_id: str) -> MeetingsRepository:
    return MeetingsRepository(get_incident_db(incident_id))


def _templates_repo() -> MeetingTemplatesRepository:
    return MeetingTemplatesRepository(get_master_db())


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _j(value: Any, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _meeting_out(doc: dict) -> dict:
    return {
        "id": doc.get("int_id"),
        "incident_id": doc.get("incident_id", ""),
        "operational_period_id": doc.get("operational_period_id"),
        "template_id": doc.get("template_id"),
        "title": doc.get("title", ""),
        "meeting_date": doc.get("meeting_date", ""),
        "start_time": doc.get("start_time", ""),
        "end_time": doc.get("end_time", ""),
        "location": doc.get("location", ""),
        "virtual_link": doc.get("virtual_link", ""),
        "owner": doc.get("owner", ""),
        "status": doc.get("status", "draft"),
        "show_on_ics230": bool(doc.get("show_on_ics230", True)),
        "freeform_notes": doc.get("freeform_notes", ""),
        "notes_log_routing_status": doc.get("notes_log_routing_status", "not routed"),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
        "attendees": [_attendee_out(a) for a in doc.get("attendees", [])],
        "checklist_items": [_checklist_out(c) for c in doc.get("checklist_items", [])],
        "structured_notes": [_note_out(n) for n in doc.get("structured_notes", [])],
    }


def _attendee_out(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "meeting_id": a.get("meeting_id"),
        "display_name": a.get("display_name", ""),
        "attendee_type": a.get("attendee_type", "role"),
        "role": a.get("role", ""),
        "requirement_status": a.get("requirement_status", "required"),
        "attendance_status": a.get("attendance_status", "invited"),
    }


def _checklist_out(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "meeting_id": c.get("meeting_id"),
        "group_name": c.get("group_name", ""),
        "text": c.get("text", ""),
        "assigned_to": c.get("assigned_to", ""),
        "is_complete": bool(c.get("is_complete", False)),
        "is_not_applicable": bool(c.get("is_not_applicable", False)),
        "sort_order": c.get("sort_order", 0),
    }


def _note_out(n: dict) -> dict:
    return {
        "id": n.get("id"),
        "meeting_id": n.get("meeting_id"),
        "category": n.get("category", ""),
        "text": n.get("text", ""),
        "author": n.get("author", ""),
        "timestamp": n.get("timestamp", ""),
        "routing_status": n.get("routing_status", "draft"),
        "routed_log_refs": list(n.get("routed_log_refs", [])),
        "routed_at": n.get("routed_at"),
    }


def _template_out(t: dict) -> dict:
    name = t.get("name", "")
    if t.get("slug") == "operations-briefing":
        name = "Operational Period Briefing"
    return {
        "slug": t.get("slug", ""),
        "name": name,
        "default_duration_minutes": t.get("default_duration_minutes", 60),
        "agenda_sections": _j(t.get("agenda_sections"), []),
        "required_attendee_roles": _j(t.get("required_attendee_roles"), []),
        "optional_attendee_roles": _j(t.get("optional_attendee_roles"), []),
        "prep_checklist_items": _j(t.get("prep_checklist_items"), []),
        "agenda_checklist_items": _j(t.get("agenda_checklist_items"), []),
        "closeout_checklist_items": _j(t.get("closeout_checklist_items"), []),
        "appears_on_ics230_default": bool(t.get("appears_on_ics230_default", True)),
        "active": bool(t.get("active", True)),
}


_DEPRECATED_BUILTIN_TEMPLATE_SLUGS = {
    "pre-tactics-meeting",
    "execute-plan-and-assess",
}


def _dedupe_template_docs(docs: List[dict]) -> List[dict]:
    deduped: list[dict] = []
    seen_names: set[str] = set()
    seen_slugs: set[str] = set()
    for doc in docs:
        slug = str(doc.get("slug") or "").strip().lower()
        if slug in _DEPRECATED_BUILTIN_TEMPLATE_SLUGS:
            continue
        normalized_name = str(_template_out(doc).get("name") or "").strip().lower()
        if slug in seen_slugs or normalized_name in seen_names:
            continue
        seen_slugs.add(slug)
        seen_names.add(normalized_name)
        deduped.append(doc)
    return deduped


# -------------------------------------------------------------------------
# Template endpoints
# -------------------------------------------------------------------------

@master_router.get("")
def list_templates(active_only: bool = True) -> List[Dict[str, Any]]:
    repo = _templates_repo()
    _seed_missing_templates()
    q = {"active": True} if active_only else {}
    docs = repo.find_many(q, sort=[("name", 1)])
    docs = _dedupe_template_docs(docs)
    return [_template_out(d) for d in docs]


@master_router.get("/{slug}")
def get_template(slug: str) -> Dict[str, Any]:
    repo = _templates_repo()
    doc = repo.find_one({"slug": slug})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Meeting template not found: {slug}")
    return _template_out(doc)


@master_router.put("/{slug}")
def upsert_template(slug: str, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _templates_repo()
    upd = {
        "slug": slug,
        "name": body.get("name", slug),
        "default_duration_minutes": int(body.get("default_duration_minutes") or 60),
        "agenda_sections": body.get("agenda_sections", []),
        "required_attendee_roles": body.get("required_attendee_roles", []),
        "optional_attendee_roles": body.get("optional_attendee_roles", []),
        "prep_checklist_items": body.get("prep_checklist_items", []),
        "agenda_checklist_items": body.get("agenda_checklist_items", []),
        "closeout_checklist_items": body.get("closeout_checklist_items", []),
        "appears_on_ics230_default": bool(body.get("appears_on_ics230_default", True)),
        "active": bool(body.get("active", True)),
    }
    existing = repo.find_one({"slug": slug})
    if existing:
        repo.update_one(existing["_id"], upd)
    else:
        repo.insert_one(upd)
    return _template_out(upd)


# -------------------------------------------------------------------------
# Meeting CRUD
# -------------------------------------------------------------------------

@incident_router.get("/incidents/{incident_id}/planning/meetings")
def list_meetings(
    incident_id: str,
    operational_period_id: Optional[str] = None,
    include_canceled: bool = True,
    ics230_only: bool = False,
) -> List[Dict[str, Any]]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    q: Dict[str, Any] = {"incident_id": incident_id, "deleted": {"$ne": True}}
    if operational_period_id is not None:
        q["operational_period_id"] = operational_period_id
    if ics230_only:
        q["show_on_ics230"] = True
        q["status"] = {"$in": ["scheduled", "ready", "completed"]}
    elif not include_canceled:
        q["status"] = {"$ne": "canceled"}
    docs = repo.find_many(q, sort=[("meeting_date", 1), ("start_time", 1), ("title", 1)])
    return [_meeting_out(d) for d in docs]


@incident_router.post("/incidents/{incident_id}/planning/meetings", status_code=201)
def create_meeting(incident_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    new_id = next_int_id(repo._col)
    doc = {
        "int_id": new_id,
        "incident_id": incident_id,
        "operational_period_id": body.get("operational_period_id"),
        "template_id": body.get("template_id"),
        "title": str(body.get("title") or ""),
        "meeting_date": str(body.get("meeting_date") or ""),
        "start_time": str(body.get("start_time") or ""),
        "end_time": str(body.get("end_time") or ""),
        "location": str(body.get("location") or ""),
        "virtual_link": str(body.get("virtual_link") or ""),
        "owner": str(body.get("owner") or ""),
        "status": str(body.get("status") or "draft"),
        "show_on_ics230": bool(body.get("show_on_ics230", True)),
        "freeform_notes": str(body.get("freeform_notes") or ""),
        "notes_log_routing_status": str(body.get("notes_log_routing_status") or "not routed"),
        "created_at": body.get("created_at") or _utcnow(),
        "attendees": [],
        "checklist_items": [],
        "structured_notes": [],
    }
    saved = repo.insert_one(doc)
    return _meeting_out(saved)


@incident_router.get("/incidents/{incident_id}/planning/meetings/{meeting_id}")
def get_meeting(incident_id: str, meeting_id: int) -> Dict[str, Any]:
    doc = _col_get(incident_id, meeting_id)
    return _meeting_out(doc)


@incident_router.patch("/incidents/{incident_id}/planning/meetings/{meeting_id}")
def update_meeting(incident_id: str, meeting_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    upd: Dict[str, Any] = {}
    for field in ("title", "meeting_date", "start_time", "end_time", "location", "virtual_link",
                  "owner", "status", "freeform_notes", "notes_log_routing_status",
                  "operational_period_id", "template_id"):
        if field in body:
            upd[field] = body[field]
    if "show_on_ics230" in body:
        upd["show_on_ics230"] = bool(body["show_on_ics230"])
    repo.update_one(doc["_id"], upd)
    return get_meeting(incident_id, meeting_id)


@incident_router.delete("/incidents/{incident_id}/planning/meetings/{meeting_id}", status_code=204)
def delete_meeting(incident_id: str, meeting_id: int) -> None:
    repo = _repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id})
    if doc:
        repo.update_one(doc["_id"], {"deleted": True})


# -------------------------------------------------------------------------
# Attendees (embedded array)
# -------------------------------------------------------------------------

def _next_sub_id(items: list) -> int:
    if not items:
        return 1
    return max(i.get("id", 0) for i in items) + 1


@incident_router.get("/incidents/{incident_id}/planning/meetings/{meeting_id}/attendees")
def list_attendees(incident_id: str, meeting_id: int) -> List[Dict[str, Any]]:
    doc = _col_get(incident_id, meeting_id)
    return [_attendee_out(a) for a in doc.get("attendees", [])]


@incident_router.post("/incidents/{incident_id}/planning/meetings/{meeting_id}/attendees", status_code=201)
def add_attendee(incident_id: str, meeting_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    new_id = _next_sub_id(doc.get("attendees", []))
    att = {
        "id": new_id,
        "meeting_id": meeting_id,
        "display_name": str(body.get("display_name") or ""),
        "attendee_type": str(body.get("attendee_type") or "role"),
        "role": str(body.get("role") or ""),
        "requirement_status": str(body.get("requirement_status") or "required"),
        "attendance_status": str(body.get("attendance_status") or "invited"),
    }
    # $push to an embedded array — not expressible via BaseRepository's
    # generic methods, so we drop to the raw collection and broadcast
    # ourselves, mirroring update_one's pattern.
    repo._col.update_one({"int_id": meeting_id, "incident_id": incident_id}, {"$push": {"attendees": att}})
    updated = repo._col.find_one({"int_id": meeting_id, "incident_id": incident_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return _attendee_out(att)


@incident_router.patch("/incidents/{incident_id}/planning/meetings/{meeting_id}/attendees/{attendee_id}")
def update_attendee(incident_id: str, meeting_id: int, attendee_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    attendees = doc.get("attendees", [])
    for i, a in enumerate(attendees):
        if a.get("id") == attendee_id:
            for field in ("display_name", "attendee_type", "role", "requirement_status", "attendance_status"):
                if field in body:
                    attendees[i][field] = body[field]
            repo.update_one(doc["_id"], {"attendees": attendees})
            return _attendee_out(attendees[i])
    raise HTTPException(status_code=404, detail="Attendee not found")


@incident_router.delete("/incidents/{incident_id}/planning/meetings/{meeting_id}/attendees/{attendee_id}", status_code=204)
def remove_attendee(incident_id: str, meeting_id: int, attendee_id: int) -> None:
    repo = _repo(incident_id)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id})
    if not doc:
        return
    # $pull from an embedded array — not expressible via BaseRepository's
    # generic methods, so we drop to the raw collection and broadcast
    # ourselves, mirroring update_one's pattern.
    repo._col.update_one(
        {"incident_id": incident_id, "int_id": meeting_id},
        {"$pull": {"attendees": {"id": attendee_id}}},
    )
    updated = repo._col.find_one({"incident_id": incident_id, "int_id": meeting_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)


# -------------------------------------------------------------------------
# Checklist items (embedded array)
# -------------------------------------------------------------------------

@incident_router.get("/incidents/{incident_id}/planning/meetings/{meeting_id}/checklist")
def list_checklist(incident_id: str, meeting_id: int) -> List[Dict[str, Any]]:
    doc = _col_get(incident_id, meeting_id)
    return [_checklist_out(c) for c in doc.get("checklist_items", [])]


@incident_router.post("/incidents/{incident_id}/planning/meetings/{meeting_id}/checklist", status_code=201)
def add_checklist_item(incident_id: str, meeting_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    new_id = _next_sub_id(doc.get("checklist_items", []))
    item = {
        "id": new_id,
        "meeting_id": meeting_id,
        "group_name": str(body.get("group_name") or ""),
        "text": str(body.get("text") or ""),
        "assigned_to": str(body.get("assigned_to") or ""),
        "is_complete": bool(body.get("is_complete", False)),
        "is_not_applicable": bool(body.get("is_not_applicable", False)),
        "sort_order": int(body.get("sort_order") or 0),
    }
    repo._col.update_one({"int_id": meeting_id, "incident_id": incident_id}, {"$push": {"checklist_items": item}})
    updated = repo._col.find_one({"int_id": meeting_id, "incident_id": incident_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return _checklist_out(item)


@incident_router.patch("/incidents/{incident_id}/planning/meetings/{meeting_id}/checklist/{item_id}")
def update_checklist_item(incident_id: str, meeting_id: int, item_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    items = doc.get("checklist_items", [])
    for i, c in enumerate(items):
        if c.get("id") == item_id:
            for field in ("group_name", "text", "assigned_to", "sort_order"):
                if field in body:
                    items[i][field] = body[field]
            for field in ("is_complete", "is_not_applicable"):
                if field in body:
                    items[i][field] = bool(body[field])
            repo.update_one(doc["_id"], {"checklist_items": items})
            return _checklist_out(items[i])
    raise HTTPException(status_code=404, detail="Checklist item not found")


# -------------------------------------------------------------------------
# Structured notes (embedded array)
# -------------------------------------------------------------------------

@incident_router.get("/incidents/{incident_id}/planning/meetings/{meeting_id}/notes")
def list_notes(incident_id: str, meeting_id: int) -> List[Dict[str, Any]]:
    doc = _col_get(incident_id, meeting_id)
    return [_note_out(n) for n in doc.get("structured_notes", [])]


@incident_router.post("/incidents/{incident_id}/planning/meetings/{meeting_id}/notes", status_code=201)
def add_note(incident_id: str, meeting_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    new_id = _next_sub_id(doc.get("structured_notes", []))
    note = {
        "id": new_id,
        "meeting_id": meeting_id,
        "category": str(body.get("category") or ""),
        "text": str(body.get("text") or ""),
        "author": str(body.get("author") or ""),
        "timestamp": body.get("timestamp") or _utcnow(),
        "routing_status": str(body.get("routing_status") or "draft"),
        "routed_log_refs": list(body.get("routed_log_refs") or []),
        "routed_at": body.get("routed_at"),
    }
    repo._col.update_one({"int_id": meeting_id, "incident_id": incident_id}, {"$push": {"structured_notes": note}})
    updated = repo._col.find_one({"int_id": meeting_id, "incident_id": incident_id})
    if updated:
        repo._broadcast("updated", updated["_id"], updated)
    return _note_out(note)


@incident_router.patch("/incidents/{incident_id}/planning/meetings/{meeting_id}/notes/{note_id}/route")
def mark_note_routed(incident_id: str, meeting_id: int, note_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    notes = doc.get("structured_notes", [])
    for i, n in enumerate(notes):
        if n.get("id") == note_id:
            notes[i]["routing_status"] = body.get("status", "routed")
            notes[i]["routed_log_refs"] = list(body.get("refs") or [])
            notes[i]["routed_at"] = _utcnow()
            repo.update_one(doc["_id"], {"structured_notes": notes})
            return _note_out(notes[i])
    raise HTTPException(status_code=404, detail="Note not found")


def _col_get(incident_id: str, meeting_id: int) -> dict:
    repo = _repo(incident_id)
    _ensure_int_ids(repo._col)
    doc = repo.find_one({"incident_id": incident_id, "int_id": meeting_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return doc


# -------------------------------------------------------------------------
# Template seeding / sync
# -------------------------------------------------------------------------

def _seed_missing_templates() -> None:
    try:
        from modules.planning.meetings.seeds import ICS_MEETING_TEMPLATES
        repo = _templates_repo()
        for t in ICS_MEETING_TEMPLATES:
            if repo.find_one({"slug": t.slug}):
                continue
            payload = {
                "slug": t.slug,
                "name": t.name,
                "default_duration_minutes": int(t.default_duration_minutes),
                "agenda_sections": t.agenda_sections,
                "required_attendee_roles": t.required_attendee_roles,
                "optional_attendee_roles": t.optional_attendee_roles,
                "prep_checklist_items": t.prep_checklist_items,
                "agenda_checklist_items": t.agenda_checklist_items,
                "closeout_checklist_items": t.closeout_checklist_items,
                "appears_on_ics230_default": bool(t.appears_on_ics230_default),
                "active": bool(t.active),
            }
            repo.insert_one(payload)
    except Exception:
        pass
