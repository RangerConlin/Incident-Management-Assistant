"""FastAPI router for Liaison agency coordination and stakeholder feedback."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Repositories
#
# All liaison collections are keyed by a sequential `int_id` (not `_id`), and
# none carry a `deleted` field (agencies/feedback historically filtered with
# `{"deleted": {"$ne": True}}`, which is equivalent to "no deleted field" for
# existing docs). soft_deletes is disabled so BaseRepository's find/count
# methods don't inject a `deleted: False` filter that would hide these docs.
# ---------------------------------------------------------------------------

class LiaisonAgenciesRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_AGENCIES
    soft_deletes = False


class LiaisonContactsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_CONTACTS
    soft_deletes = False


class LiaisonInteractionsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_INTERACTIONS
    soft_deletes = False


class LiaisonAgencyRequestsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_AGENCY_REQUESTS
    soft_deletes = False


class LiaisonResourceOffersRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_RESOURCE_OFFERS
    soft_deletes = False


class LiaisonFeedbackRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_FEEDBACK
    soft_deletes = False


class LiaisonFollowupActionsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_FOLLOWUP_ACTIONS
    soft_deletes = False


class LiaisonRestrictionsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_RESTRICTIONS
    soft_deletes = False


class LiaisonAgreementsRepository(BaseRepository):
    collection_name = IncidentCollections.LIAISON_AGREEMENTS
    soft_deletes = False


def _agencies(incident_id: str) -> LiaisonAgenciesRepository:
    return LiaisonAgenciesRepository(get_incident_db(incident_id))


def _contacts(incident_id: str) -> LiaisonContactsRepository:
    return LiaisonContactsRepository(get_incident_db(incident_id))


def _interactions(incident_id: str) -> LiaisonInteractionsRepository:
    return LiaisonInteractionsRepository(get_incident_db(incident_id))


def _agency_requests(incident_id: str) -> LiaisonAgencyRequestsRepository:
    return LiaisonAgencyRequestsRepository(get_incident_db(incident_id))


def _resource_offers(incident_id: str) -> LiaisonResourceOffersRepository:
    return LiaisonResourceOffersRepository(get_incident_db(incident_id))


def _feedback(incident_id: str) -> LiaisonFeedbackRepository:
    return LiaisonFeedbackRepository(get_incident_db(incident_id))


def _followups(incident_id: str) -> LiaisonFollowupActionsRepository:
    return LiaisonFollowupActionsRepository(get_incident_db(incident_id))


def _restrictions(incident_id: str) -> LiaisonRestrictionsRepository:
    return LiaisonRestrictionsRepository(get_incident_db(incident_id))


def _agreements(incident_id: str) -> LiaisonAgreementsRepository:
    return LiaisonAgreementsRepository(get_incident_db(incident_id))


def _ensure_int_ids(repo: BaseRepository) -> int:
    """Assign sequential int_id to any docs that are missing one."""
    col = repo._col
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    counter = (max_doc["int_id"] if max_doc else 0)
    for doc in col.find({"int_id": {"$exists": False}}):
        counter += 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": counter}})
    return counter


def _next_int_id(repo: BaseRepository) -> int:
    _ensure_int_ids(repo)
    max_doc = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (max_doc["int_id"] if max_doc else 0) + 1


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agencies")
def list_agencies(incident_id: str) -> list[dict]:
    repo = _agencies(incident_id)
    _ensure_int_ids(repo)
    return [_strip(d) for d in repo.find_many({"deleted": {"$ne": True}})]


@router.post("/incidents/{incident_id}/liaison/agencies", status_code=201)
def create_agency(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _agencies(incident_id)
    int_id = _next_int_id(repo)
    doc = {
        **body,
        "incident_id": incident_id,
        "int_id": int_id,
    }
    doc = repo.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/liaison/agencies/{agency_id}")
def get_agency(incident_id: str, agency_id: int) -> dict:
    repo = _agencies(incident_id)
    doc = repo.find_one({"int_id": agency_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(404, "Agency not found")
    return _strip(doc)


@router.patch("/incidents/{incident_id}/liaison/agencies/{agency_id}")
def update_agency(incident_id: str, agency_id: int, body: dict[str, Any]) -> dict:
    repo = _agencies(incident_id)
    body.pop("int_id", None)
    doc = repo.find_one({"int_id": agency_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(404, "Agency not found")
    repo.update_one(doc["_id"], body)
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


@router.patch("/incidents/{incident_id}/liaison/agencies/{agency_id}/status")
def update_agency_status(incident_id: str, agency_id: int, body: dict[str, Any]) -> dict:
    status = body.get("current_status")
    if not status:
        raise HTTPException(400, "current_status required")
    repo = _agencies(incident_id)
    doc = repo.find_one({"int_id": agency_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(404, "Agency not found")
    repo.update_one(doc["_id"], {"current_status": status})
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


# ---------------------------------------------------------------------------
# Agency rows (summary view with counts)
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/agency-rows")
def list_agency_rows(incident_id: str) -> list[dict]:
    """Return agencies with computed open_requests/resource_offers/open_feedback_items counts."""
    agencies_repo = _agencies(incident_id)
    _ensure_int_ids(agencies_repo)
    agencies_list = agencies_repo.find_many({"deleted": {"$ne": True}})

    req_repo = _agency_requests(incident_id)
    offer_repo = _resource_offers(incident_id)
    fb_repo = _feedback(incident_id)

    rows = []
    for ag in agencies_list:
        aid = ag.get("int_id")
        open_req = req_repo.count({"agency_id": aid, "status": {"$nin": ["Filled", "Declined", "Cancelled", "Closed"]}})
        open_offer = offer_repo.count({"agency_id": aid, "status": {"$nin": ["Declined", "Released"]}})
        open_fb = fb_repo.count({"agency_id": aid, "status": {"$nin": ["Resolved", "Closed", "Cancelled"]}})
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
    agencies_repo = _agencies(incident_id)
    ag = agencies_repo.find_one({"int_id": agency_id})
    if not ag:
        raise HTTPException(404, "Agency not found")
    agency_doc = _strip(ag)

    def _rows(repo: BaseRepository, query):
        return [_strip(d) for d in repo.find_many(query)]

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
    return [_strip(d) for d in _contacts(incident_id).find_many({"agency_id": agency_id})]


@router.post("/incidents/{incident_id}/liaison/agencies/{agency_id}/contacts", status_code=201)
def create_contact(incident_id: str, agency_id: int, body: dict[str, Any]) -> dict:
    repo = _contacts(incident_id)
    int_id = _next_int_id(repo)
    doc = {**body, "agency_id": agency_id, "incident_id": incident_id, "int_id": int_id}
    doc = repo.insert_one(doc)
    return _strip(doc)


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/interactions")
def list_interactions(incident_id: str, agency_id: int | None = None) -> list[dict]:
    query: dict = {}
    if agency_id is not None:
        query["agency_id"] = agency_id
    return [_strip(d) for d in _interactions(incident_id).find_many(query)]


@router.post("/incidents/{incident_id}/liaison/interactions", status_code=201)
def create_interaction(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _interactions(incident_id)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    doc = repo.insert_one(doc)
    # Update last_contact on the agency
    agency_id = body.get("agency_id")
    occurred = body.get("occurred_at") or ts
    if agency_id is not None:
        agencies_repo = _agencies(incident_id)
        ag_doc = agencies_repo.find_one({"int_id": agency_id})
        if ag_doc:
            agencies_repo.update_one(ag_doc["_id"], {"last_contact": occurred})
    return _strip(doc)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/feedback")
def list_feedback(
    incident_id: str,
    objective_id: int | None = None,
    strategy_id: int | None = None,
    task_id: int | None = None,
    resource_request_id: int | None = None,
) -> list[dict]:
    repo = _feedback(incident_id)
    _ensure_int_ids(repo)
    query: dict[str, Any] = {}
    if objective_id is not None:
        query["objective_id"] = objective_id
    if strategy_id is not None:
        query["strategy_id"] = strategy_id
    if task_id is not None:
        query["task_id"] = task_id
    if resource_request_id is not None:
        query["resource_request_id"] = resource_request_id
    return [_strip(d) for d in repo.find_many(query)]


@router.post("/incidents/{incident_id}/liaison/feedback", status_code=201)
def create_feedback(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _feedback(incident_id)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "entered_ts": ts}
    doc = repo.insert_one(doc)
    return _strip(doc)


@router.get("/incidents/{incident_id}/liaison/feedback-rows")
def list_feedback_rows(incident_id: str) -> list[dict]:
    """Return feedback rows with linked_item text for the FeedbackBoard."""
    repo = _feedback(incident_id)
    _ensure_int_ids(repo)
    rows = []
    for doc in repo.find_many({}):
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
            "objective_id": doc.get("objective_id"),
            "task_id": doc.get("task_id"),
            "resource_request_id": doc.get("resource_request_id"),
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
    return [_strip(d) for d in _agency_requests(incident_id).find_many(query)]


@router.post("/incidents/{incident_id}/liaison/agency-requests", status_code=201)
def create_agency_request(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _agency_requests(incident_id)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    doc = repo.insert_one(doc)
    return _strip(doc)


@router.patch("/incidents/{incident_id}/liaison/agency-requests/{request_id}/converted")
def mark_agency_request_converted(incident_id: str, request_id: int, body: dict[str, Any]) -> dict:
    """Record that a customer request was converted into an Objective or Task."""
    converted_to_type = body.get("converted_to_type")
    converted_to_id = body.get("converted_to_id")
    if not converted_to_type or not converted_to_id:
        raise HTTPException(400, "converted_to_type and converted_to_id required")
    repo = _agency_requests(incident_id)
    doc = repo.find_one({"int_id": request_id})
    if not doc:
        raise HTTPException(404, "Agency request not found")
    repo.update_one(doc["_id"], {
        "converted_to_type": converted_to_type,
        "converted_to_id": converted_to_id,
    })
    result = repo.find_by_id(doc["_id"])
    return _strip(result)


# ---------------------------------------------------------------------------
# Resource offers
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/liaison/resource-offers")
def list_resource_offers(incident_id: str, agency_id: int | None = None) -> list[dict]:
    query: dict = {}
    if agency_id is not None:
        query["agency_id"] = agency_id
    return [_strip(d) for d in _resource_offers(incident_id).find_many(query)]


@router.post("/incidents/{incident_id}/liaison/resource-offers", status_code=201)
def create_resource_offer(incident_id: str, body: dict[str, Any]) -> dict:
    repo = _resource_offers(incident_id)
    int_id = _next_int_id(repo)
    ts = _now()
    doc = {**body, "incident_id": incident_id, "int_id": int_id, "created_at": ts}
    doc = repo.insert_one(doc)
    return _strip(doc)
