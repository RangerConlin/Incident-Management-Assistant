"""Incident resource check-in / check-out router.

Tracks which master resources (personnel, vehicle, aircraft, equipment)
are checked in to a given incident.  Each document in check_in_out has
a resource_type field to distinguish them.

Endpoints are mounted under /api/incidents/{incident_id}/resources.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.collection_names import MasterCollections, IncidentCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_MASTER_COLLECTION = {
    "personnel": MasterCollections.PERSONNEL,
    "vehicle": MasterCollections.VEHICLES,
    "aircraft": MasterCollections.AIRCRAFT,
    "equipment": MasterCollections.EQUIPMENT,
}


class CheckInOutRepository(BaseRepository):
    collection_name = IncidentCollections.CHECK_IN_OUT
    soft_deletes = False


class _MasterLookupRepository(BaseRepository):
    pass


def _incident_repo(incident_id: str) -> CheckInOutRepository:
    return CheckInOutRepository(get_incident_db(incident_id))


def _master_repo(collection_name: str) -> _MasterLookupRepository:
    repo_cls = type("_MasterLookupRepository", (BaseRepository,), {
        "collection_name": collection_name,
        "soft_deletes": False,
    })
    return repo_cls(get_master_db())


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    return d


def _get_master_record(resource_type: str, resource_id: str) -> dict[str, Any]:
    cname = _MASTER_COLLECTION.get(resource_type)
    if not cname:
        raise HTTPException(status_code=400, detail=f"Unknown resource type: {resource_type}")
    repo = _master_repo(cname)
    doc = (
        repo.find_one({"int_id": int(resource_id)}) if resource_id.isdigit() else None
    ) or repo.find_one({"id": resource_id}) or repo.find_one({"person_id": resource_id}) or repo.find_one({"tail_number": resource_id.upper()})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{resource_type} {resource_id} not found in master")
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# List checked-in resources
# ---------------------------------------------------------------------------

@router.get("")
def list_resources(
    incident_id: str,
    resource_type: str = Query(""),
) -> list[dict[str, Any]]:
    repo = _incident_repo(incident_id)
    query: dict[str, Any] = {}
    if resource_type:
        query["resource_type"] = resource_type
    docs = repo.find_many(query, sort=[("checked_in_at", 1)])
    return [_normalize(d) for d in docs]


@router.get("/checked-ids")
def get_checked_ids(
    incident_id: str,
    resource_type: str = Query(""),
) -> list[str]:
    repo = _incident_repo(incident_id)
    query: dict[str, Any] = {}
    if resource_type:
        query["resource_type"] = resource_type
    docs = repo.find_many(query)
    return [str(d["resource_id"]) for d in docs if d.get("resource_id") is not None]


@router.get("/{resource_type}/{resource_id}")
def get_resource(
    incident_id: str, resource_type: str, resource_id: str
) -> dict[str, Any]:
    repo = _incident_repo(incident_id)
    doc = repo.find_one({
        "resource_type": resource_type,
        "resource_id": resource_id,
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Resource not checked in")
    return _normalize(doc)


# ---------------------------------------------------------------------------
# Check in (copy master record to incident)
# ---------------------------------------------------------------------------

@router.post("/{resource_type}/{resource_id}", status_code=201)
def check_in_resource(
    incident_id: str,
    resource_type: str,
    resource_id: str,
    overrides: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    master_doc = _get_master_record(resource_type, resource_id)
    master_doc.pop("_id", None)

    # Apply overrides (cannot change id fields)
    id_keys = {"int_id", "id", "person_id", "tail_number"}
    for k, v in overrides.items():
        if k not in id_keys:
            master_doc[k] = v

    now = _utcnow()
    repo = _incident_repo(incident_id)
    doc = {
        "resource_type": resource_type,
        "resource_id": resource_id,
        **master_doc,
        "_checked_in": True,
        "checked_in_at": now,
    }
    # Atomic upsert keyed on (resource_type, resource_id), not `_id` — not
    # expressible via BaseRepository's generic methods, so we drop to the
    # raw collection and broadcast ourselves, mirroring update_one's pattern.
    query = {"resource_type": resource_type, "resource_id": resource_id}
    repo._col.replace_one(query, doc, upsert=True)
    saved = repo._col.find_one(query)
    if saved:
        repo._broadcast("updated", saved["_id"], saved)
        saved.pop("_id", None)
        return saved
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Check out (remove from incident)
# ---------------------------------------------------------------------------

@router.delete("/{resource_type}/{resource_id}", status_code=204)
def check_out_resource(
    incident_id: str, resource_type: str, resource_id: str
) -> None:
    repo = _incident_repo(incident_id)
    existing = repo.find_one({
        "resource_type": resource_type,
        "resource_id": resource_id,
    })
    if not existing:
        raise HTTPException(status_code=404, detail="Resource not checked in")
    repo.delete_one(existing["_id"])
