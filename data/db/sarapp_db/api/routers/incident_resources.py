"""Incident resource check-in / check-out router.

Compatibility endpoints for ICS-211 and form builders that expose checked-in
incident resources. Canonical state lives in the per-incident
``resource_status`` collection.

Endpoints are mounted under /api/incidents/{incident_id}/resources.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_MASTER_COLLECTION = {
    "personnel": MasterCollections.PERSONNEL,
    "vehicle": MasterCollections.VEHICLES,
    "aircraft": MasterCollections.AIRCRAFT,
    "equipment": MasterCollections.EQUIPMENT,
}


class ResourceStatusRepository(BaseRepository):
    collection_name = IncidentCollections.RESOURCE_STATUS


class _MasterLookupRepository(BaseRepository):
    pass


def _rs_repo(incident_id: str) -> ResourceStatusRepository:
    return ResourceStatusRepository(get_incident_db(incident_id))


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


_RECORD_FIELD = {
    "personnel": "person_record",
    "vehicle": "vehicle_record",
    "aircraft": "aircraft_record",
    "equipment": "equipment_record",
}


def _get_master_record(resource_type: str, resource_id: str) -> dict[str, Any]:
    cname = _MASTER_COLLECTION.get(resource_type)
    if not cname:
        raise HTTPException(status_code=400, detail=f"Unknown resource type: {resource_type}")
    record_field = _RECORD_FIELD.get(resource_type, "person_record")
    repo = _master_repo(cname)
    doc = repo.find_one({record_field: int(resource_id)}) if resource_id.isdigit() else None
    if not doc:
        raise HTTPException(status_code=404, detail=f"{resource_type} {resource_id} not found in master")
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# List checked-in resources
# ---------------------------------------------------------------------------

_ENTITY_TYPE_MAP: dict[str, str] = {
    "personnel": "personnel",
    "vehicle": "vehicle",
    "aircraft": "aircraft",
    "equipment": "equipment",
}

_CHECKED_IN_STATUSES = {
    "Checked In", "Assigned", "Available", "Out of Service", "Preparing for Demobilization",
}


@router.get("")
def list_resources(
    incident_id: str,
    resource_type: str = Query(""),
) -> list[dict[str, Any]]:
    repo = _rs_repo(incident_id)
    query: dict[str, Any] = {"status": {"$in": sorted(_CHECKED_IN_STATUSES)}}
    if resource_type:
        entity_type = _ENTITY_TYPE_MAP.get(resource_type.lower(), resource_type.lower())
        query["entity_type"] = entity_type
    docs = repo.find_many(query, sort=[("resource_name", 1)])
    return [_normalize(d) for d in docs]


@router.get("/checked-ids")
def get_checked_ids(
    incident_id: str,
    resource_type: str = Query(""),
) -> list[str]:
    repo = _rs_repo(incident_id)
    query: dict[str, Any] = {}
    if resource_type:
        entity_type = _ENTITY_TYPE_MAP.get(resource_type.lower(), resource_type.lower())
        query["entity_type"] = entity_type
    docs = repo.find_many(query)
    return [
        str(d["record_id"])
        for d in docs
        if d.get("record_id") is not None and str(d.get("status") or "") in _CHECKED_IN_STATUSES
    ]


@router.get("/{resource_type}/{resource_id}")
def get_resource(
    incident_id: str, resource_type: str, resource_id: str
) -> dict[str, Any]:
    repo = _rs_repo(incident_id)
    entity_type = _ENTITY_TYPE_MAP.get(resource_type.lower(), resource_type.lower())
    rid = int(resource_id) if resource_id.isdigit() else resource_id
    doc = repo.find_one({"entity_type": entity_type, "record_id": rid})
    if not doc:
        raise HTTPException(status_code=404, detail="Resource not checked in")
    return _normalize(doc)


# ---------------------------------------------------------------------------
# Check in (copy master record to incident)
# ---------------------------------------------------------------------------

def _resource_display_name(resource_type: str, master_doc: dict[str, Any], resource_id: str) -> str:
    if resource_type == "vehicle":
        return (
            master_doc.get("callsign")
            or master_doc.get("license_plate")
            or " ".join(str(v) for v in [master_doc.get("year"), master_doc.get("make"), master_doc.get("model")] if v)
            or resource_id
        )
    if resource_type == "aircraft":
        return master_doc.get("callsign") or master_doc.get("tail_number") or master_doc.get("aircraft_id") or resource_id
    if resource_type == "equipment":
        return master_doc.get("name") or master_doc.get("serial_number") or resource_id
    return master_doc.get("name") or resource_id


@router.post("/{resource_type}/{resource_id}", status_code=201)
def check_in_resource(
    incident_id: str,
    resource_type: str,
    resource_id: str,
    overrides: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    if resource_type == "personnel":
        raise HTTPException(status_code=400, detail="Personnel use the /checkin endpoint")

    master_doc = _get_master_record(resource_type, resource_id)
    master_doc.pop("_id", None)

    entity_type = _ENTITY_TYPE_MAP.get(resource_type.lower(), resource_type.lower())
    rid = int(resource_id) if resource_id.isdigit() else resource_id
    resource_name = _resource_display_name(resource_type, master_doc, resource_id)
    status = str(overrides.get("status") or "Checked In")
    now = _utcnow()

    repo = _rs_repo(incident_id)
    existing = repo.find_one({"entity_type": entity_type, "record_id": rid})

    if existing:
        # Update status if it changed
        updates: dict[str, Any] = {"updated_at": now}
        if status != existing.get("status"):
            updates["status"] = status
            entry = {"status": status, "timestamp": now, "changed_by": overrides.get("changed_by") or "Check-In"}
            repo.apply_update(existing["_id"], {"$set": updates, "$push": {"status_log": entry}})
        else:
            repo.update_one(existing["_id"], updates)
        saved = repo.find_by_id(existing["_id"])
    else:
        doc = {
            "entity_type": entity_type,
            "record_id": rid,
            "resource_name": resource_name,
            "resource_type": resource_type.title(),
            "status": status,
            "status_log": [{"status": status, "timestamp": now, "changed_by": overrides.get("changed_by") or "Check-In"}],
            "checked_in_time": now,
            "created_at": now,
            "updated_at": now,
            "eta_utc": overrides.get("eta_utc"),
            "location": overrides.get("location") or master_doc.get("location"),
            "notes": overrides.get("notes"),
        }
        saved = repo.insert_one(doc)

    if saved:
        saved.pop("_id", None)
        return saved
    return {"entity_type": entity_type, "record_id": rid, "status": status}


# ---------------------------------------------------------------------------
# Check out (remove from incident)
# ---------------------------------------------------------------------------

@router.delete("/{resource_type}/{resource_id}", status_code=204)
def check_out_resource(
    incident_id: str, resource_type: str, resource_id: str
) -> None:
    repo = _rs_repo(incident_id)
    entity_type = _ENTITY_TYPE_MAP.get(resource_type.lower(), resource_type.lower())
    rid = int(resource_id) if resource_id.isdigit() else resource_id
    existing = repo.find_one({"entity_type": entity_type, "record_id": rid})
    if not existing or str(existing.get("status") or "") not in _CHECKED_IN_STATUSES:
        raise HTTPException(status_code=404, detail="Resource not checked in")
    now = _utcnow()
    entry = {"status": "Demobilized", "timestamp": now, "changed_by": "Check-Out"}
    repo.apply_update(
        existing["_id"],
        {
            "$set": {
                "status": "Demobilized",
                "checked_out_time": now,
                "assigned_to": None,
                "assignment_reference": None,
                "updated_at": now,
            },
            "$unset": {"checked_in_time": ""},
            "$push": {"status_log": entry},
        },
    )
