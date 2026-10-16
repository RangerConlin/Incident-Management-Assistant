"""Master (cloud/central catalog) facilities — agency-wide facility records
(shelters, staging areas, bases, etc.) distinct from the per-incident
facilities tracked by `facilities.py` (`IncidentCollections.FACILITIES`).

Field shape mirrors the incident-scoped `FacilityPayload` in `facilities.py`,
minus the incident linkage and plus `parent_organization_id` so a facility
can be scoped to an organization in the master catalog, the same way
`organizations.py` scopes ranks/rank-structures.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db, is_central_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_LOCKDOWN_DETAIL = "Facilities are central-catalog authoritative; edit them on the central catalog."


class MasterFacilitiesRepository(BaseRepository):
    collection_name = MasterCollections.FACILITIES
    soft_deletes = False


def _facilities_repo() -> MasterFacilitiesRepository:
    return MasterFacilitiesRepository(get_master_db())


def _require_central(repo: BaseRepository) -> None:
    if not is_central_master_db(repo._db):
        raise HTTPException(status_code=403, detail=_LOCKDOWN_DETAIL)


def _next_int_id(repo: BaseRepository) -> int:
    docs = repo.find_many({}, sort=[("int_id", -1)], limit=1)
    return (docs[0].get("int_id", 0) if docs else 0) + 1


_FACILITY_FIELDS = (
    "name", "facility_type", "status", "parent_organization_id",
    "address", "latitude", "longitude", "geocoded_address", "icao_code",
    "manager_personnel_id", "manager_name", "contact_name", "contact_phone",
    "notes", "function_tags", "served_sections", "is_primary", "metadata",
)


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    payload = dict(doc)
    payload.pop("_id", None)
    payload["id"] = payload.get("int_id")
    return payload


def _enrich_facility(doc: dict[str, Any]) -> dict[str, Any]:
    from sarapp_db.api.routers.organizations import _organizations_repo

    payload = _serialize(doc) or {}
    parent_id = payload.get("parent_organization_id")
    if parent_id is not None:
        parent = _organizations_repo().find_one({"int_id": parent_id})
        payload["parent_organization_name"] = parent.get("name") if parent else None
    else:
        payload["parent_organization_name"] = None
    return payload


@router.get("/facilities")
def list_master_facilities(search: str = "") -> list[dict[str, Any]]:
    repo = _facilities_repo()
    query: dict[str, Any] = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"address": {"$regex": search, "$options": "i"}},
        ]
    return [_enrich_facility(doc) for doc in repo.find_many(query, sort=[("name", 1)])]


@router.post("/facilities", status_code=201)
def create_master_facility(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _facilities_repo()
    _require_central(repo)
    doc = {"int_id": _next_int_id(repo)}
    for field in _FACILITY_FIELDS:
        if field in body:
            doc[field] = body.get(field)
    if doc.get("facility_type") is None:
        doc["facility_type"] = "other"
    if doc.get("status") is None:
        doc["status"] = "active"
    if doc.get("is_primary") is None:
        doc["is_primary"] = False
    doc = repo.insert_one(doc)
    return _enrich_facility(doc)


@router.get("/facilities/{facility_id}")
def get_master_facility(facility_id: int) -> dict[str, Any]:
    doc = _facilities_repo().find_one({"int_id": facility_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Facility not found")
    return _enrich_facility(doc)


@router.patch("/facilities/{facility_id}")
def update_master_facility(facility_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _facilities_repo()
    _require_central(repo)
    updates = {field: body[field] for field in _FACILITY_FIELDS if field in body}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": facility_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Facility not found")
    repo.update_one(doc["_id"], updates)
    return _enrich_facility(repo.find_by_id(doc["_id"]))


@router.delete("/facilities/{facility_id}", status_code=204)
def delete_master_facility(facility_id: int) -> None:
    repo = _facilities_repo()
    _require_central(repo)
    doc = repo.find_one({"int_id": facility_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Facility not found")
    repo.delete_one(doc["_id"])
