"""FastAPI router for Liaison agency coordination and stakeholder feedback."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.client import get_db
from sarapp_db.mongo.collection_names import IncidentCollections

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _agencies(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_AGENCIES]


def _contacts(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_CONTACTS]


def _interactions(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_INTERACTIONS]


def _agency_requests(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_AGENCY_REQUESTS]


def _resource_offers(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_RESOURCE_OFFERS]


def _feedback(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_FEEDBACK]


def _followups(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_FOLLOWUP_ACTIONS]


def _restrictions(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_RESTRICTIONS]


def _agreements(incident_id: str):
    db = get_db(f"sarapp_incident_{incident_id}")
    return db[IncidentCollections.LIAISON_AGREEMENTS]


def _ensure_int_ids(col) -> int:
    """Assign sequential int_id to any docs that are missing one."""
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    counter = (max_doc["int_id"] if max_doc else 0)
    for doc in col.find({"int_id": {"$exists": False}}):
        counter += 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": counter}})
    return counter


def _next_int_id(col) -> int:
    _ensure_int_ids(col)
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (max_doc["int_id"] if max_doc else 0) + 1


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agencies")
def list_agencies(incident_id: str) -> list[dict]:
    col = _agencies(incident_id)
    _ensure_int_ids(col)
    return [_strip(d) for d in col.find({"deleted": {"$ne": True}})]


@router.post("/incidents/{incident_id}/liaison/agencies", status_code=201)
def create_agency(incident_id: str, body: dict[str, Any]) -> dict:
    col = _agencies(incident_id)
    int_id = _next_int_id(col)
    ts = _now()
    doc = {
        **body,
        "incident_id": incident_id,
        "int_id": int_id,
        "created_at": ts,
        "updated_at": ts,
    }
    col.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/liaison/agencies/{agency_id}")
def get_agency(incident_id: str, agency_id: int) -> dict:
    col = _agencies(incident_id)
    doc = col.find_one({"int_id": agency_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(404, "Agency not found")
    return _strip(doc)


@router.patch("/incidents/{incident_id}/liaison/agencies/{agency_id}")
def update_agency(incident_id: str, agency_id: int, body: dict[str, Any]) -> dict:
    col = _agencies(incident_id)
    body.pop("int_id", None)
    body["updated_at"] = _now()
    result = col.find_one_and_update(
        {"int_id": agency_id, "deleted": {"$ne": True}},
        {"$set": body},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, "Agency not found")
    return _strip(result)


@router.patch("/incidents/{incident_id}/liaison/agencies/{agency_id}/status")
def update_agency_status(incident_id: str, agency_id: int, body: dict[str, Any]) -> dict:
    status = body.get("current_status")
    if not status:
        raise HTTPException(400, "current_status required")
    col = _agencies(incident_id)
    result = col.find_one_and_update(
        {"int_id": agency_id, "deleted": {"$ne": True}},
        {"$set": {"current_status": status, "updated_at": _now()}},
        return_document=True,
    )
    if not result:
        raise HTTPException(404, "Agency not found")
    return _strip(result)


# ---------------------------------------------------------------------------
# Agency rows (summary view with counts)
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agency-rows")
def list_agency_rows(incident_id: str) -> list[dict]:
    """Return agencies with computed open_requests/resource_offers/open_feedback_items counts."""
    col = _agencies(incident_id)
    _ensure_int_ids(col)
    agencies_list = list(col.find({"deleted": {"$ne": True}}))

    req_col = _agency_requests(incident_id)
    offer_col = _resource_offers(incident_id)
    fb_col = _feedback(incident_id)

    rows = []
    for ag in agencies_list:
        aid = ag.get("int_id")
        open_req = req_col.count_documents({"agency_id": aid, "status": {"$nin": ["Filled", "Declined", "Cancelled", "Closed"]}})
        open_offer = offer_col.count_documents({"agency_id": aid, "status": {"$nin": ["Declined", "Released"]}})
        open_fb = fb_col.count_documents({"agency_id": aid, "status": {"$nin": ["Resolved", "Closed", "Cancelled"]}})
        rows.append({
            "id": aid,
            "agency_name": ag.get("name", ""),
            "agency_type": ag.get("agency_type", ""),
            "jurisdiction": ag.get("jurisdiction", ""),
            "current_status": ag.get("current_status", ""),
            "assigned_liaison": ag.get("assigned_liaison", ""),
            "last_contact": ag.get("last_contact", ""),
            "next_contact_due": ag.get("next_contact_due", ""),
            "open_requests": open_req,
            "resource_offers": open_offer,
            "open_feedback_items": open_fb,
            "priority": ag.get("priority", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# Agency detail (all related tables)
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agencies/{agency_id}/detail")
def get_agency_detail(incident_id: str, agency_id: int) -> dict:
    col = _agencies(incident_id)
    ag = col.find_one({"int_id": agency_id})
    if not ag:
        raise HTTPException(404, "Agency not found")
    agency_doc = _strip(ag)

    def _rows(c, query):
        return [_strip(d) for d in c.find(query)]

    return {
        "agency": agency_doc,
        "contacts": _rows(_contacts(incident_id), {"agency_id": agency_id}),
        "interactions": _rows(_interactions(incident_id), {"agency_id": agency_id}),
        "requests": _rows(_agency_requests(incident_id), {"agency_id": agency_id}),
        "offers": _rows(_resource_offers(incident_id), {"agency_id": agency_id}),
        "feedback": _rows(_feedback(incident_id), {"agency_id": agency_id}),
        "followups": _rows(_followups(incident_id), {"agency_id": agency_id}),
        "restrictions": _rows(_restrictions(incident_id), {"agency_id": agency_id}),
        "agreements": _rows(_agreements(incident_id), {"agency_id": agency_id}),
        "attachments": [],
        "audit": [],
    }


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agencies/{agency_id}/contacts")
def list_contacts(incident_id: str, agency_id: int) -> list[dict]:
    return [_strip(d) for d in _contacts(incident_id).find({"agency_id": agency_id})]


@router.post("/incidents/{incident_id}/liaison/agencies/{agency_id}/contacts", status_code=201)
def create_contact(incident_id: str, agency_id: int, body: dict[str, Any]) -> dict:
    col = _contacts(incident_id)
    int_id = _next_int_id(col)
    ts = _now()
    doc = {**body, "agency_id": agency_id, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    col.insert_one(doc)
    return _strip(doc)


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/interactions")
def list_interactions(incident_id: str, agency_id: int | None = None) -> list[dict]:
    query: dict = {}
    if agency_id is not None:
        query["agency_id"] = agency_id
    return [_strip(d) for d in _interactions(incident_id).find(query)]


@router.post("/incidents/{incident_id}/liaison/interactions", status_code=201)
def create_interaction(incident_id: str, body: dict[str, Any]) -> dict:
    col = _interactions(incident_id)
    int_id = _next_int_id(col)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    col.insert_one(doc)
    # Update last_contact on the agency
    agency_id = body.get("agency_id")
    occurred = body.get("occurred_at") or ts
    if agency_id is not None:
        _agencies(incident_id).update_one(
            {"int_id": agency_id},
            {"$set": {"last_contact": occurred, "updated_at": ts}},
        )
    return _strip(doc)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/feedback")
def list_feedback(incident_id: str) -> list[dict]:
    col = _feedback(incident_id)
    _ensure_int_ids(col)
    return [_strip(d) for d in col.find()]


@router.post("/incidents/{incident_id}/liaison/feedback", status_code=201)
def create_feedback(incident_id: str, body: dict[str, Any]) -> dict:
    col = _feedback(incident_id)
    int_id = _next_int_id(col)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "entered_ts": ts}
    col.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/liaison/feedback-rows")
def list_feedback_rows(incident_id: str) -> list[dict]:
    """Return feedback rows with linked_item text for the FeedbackBoard."""
    col = _feedback(incident_id)
    _ensure_int_ids(col)
    rows = []
    for doc in col.find():
        linked_parts = []
        if doc.get("objective_id"):
            linked_parts.append(f"Objective #{doc['objective_id']}")
        if doc.get("task_id"):
            linked_parts.append(f"Task #{doc['task_id']}")
        if doc.get("resource_request_id"):
            linked_parts.append(f"ResourceReq #{doc['resource_request_id']}")
        rows.append({
            "id": doc.get("int_id"),
            "date_time": doc.get("entered_ts", ""),
            "source": doc.get("agency_id", ""),
            "feedback_type": doc.get("feedback_type", ""),
            "priority": doc.get("priority", ""),
            "linked_item": ", ".join(linked_parts) if linked_parts else "",
            "status": doc.get("status", ""),
            "assigned_to": doc.get("assigned_to", ""),
            "due_followup": doc.get("followup_due", ""),
            "resolution_status": doc.get("validation_status", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# Agency requests
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agency-requests")
def list_agency_requests(incident_id: str, agency_id: int | None = None) -> list[dict]:
    query: dict = {}
    if agency_id is not None:
        query["agency_id"] = agency_id
    return [_strip(d) for d in _agency_requests(incident_id).find(query)]


@router.post("/incidents/{incident_id}/liaison/agency-requests", status_code=201)
def create_agency_request(incident_id: str, body: dict[str, Any]) -> dict:
    col = _agency_requests(incident_id)
    int_id = _next_int_id(col)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    col.insert_one(doc)
    return _strip(doc)


# ---------------------------------------------------------------------------
# Resource offers
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/resource-offers")
def list_resource_offers(incident_id: str, agency_id: int | None = None) -> list[dict]:
    query: dict = {}
    if agency_id is not None:
        query["agency_id"] = agency_id
    return [_strip(d) for d in _resource_offers(incident_id).find(query)]


@router.post("/incidents/{incident_id}/liaison/resource-offers", status_code=201)
def create_resource_offer(incident_id: str, body: dict[str, Any]) -> dict:
    col = _resource_offers(incident_id)
    int_id = _next_int_id(col)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    col.insert_one(doc)
    return _strip(doc)
