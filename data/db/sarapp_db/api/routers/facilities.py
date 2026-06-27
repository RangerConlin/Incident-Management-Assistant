from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class FacilitiesRepository(BaseRepository):
    collection_name = IncidentCollections.FACILITIES


def _repo(incident_id: str) -> FacilitiesRepository:
    return FacilitiesRepository(get_incident_db(incident_id))


class FacilityPayload(BaseModel):
    name: str
    facility_type: str = "other"
    status: str = "active"
    address: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocoded_address: str = ""
    manager_personnel_id: str = ""
    manager_name: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    notes: str = ""
    function_tags: List[str] = Field(default_factory=list)
    served_sections: List[str] = Field(default_factory=list)
    is_primary: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id") or ""),
        "incident_id": str(doc.get("incident_id") or ""),
        "name": str(doc.get("name") or ""),
        "facility_type": str(doc.get("facility_type") or "other"),
        "status": str(doc.get("status") or "active"),
        "address": str(doc.get("address") or ""),
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "geocoded_address": str(doc.get("geocoded_address") or ""),
        "manager_personnel_id": str(doc.get("manager_personnel_id") or ""),
        "manager_name": str(doc.get("manager_name") or ""),
        "contact_name": str(doc.get("contact_name") or ""),
        "contact_phone": str(doc.get("contact_phone") or ""),
        "notes": str(doc.get("notes") or ""),
        "function_tags": list(doc.get("function_tags") or doc.get("capabilities") or []),
        "served_sections": list(doc.get("served_sections") or doc.get("served_modules") or []),
        "is_primary": bool(doc.get("is_primary") or False),
        "metadata": dict(doc.get("metadata") or {}),
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
    }


def _apply_primary_constraint(repo: FacilitiesRepository, incident_id: str, facility_type: str, keep_id: str) -> None:
    others = repo.find_many(
        {"incident_id": incident_id, "facility_type": facility_type, "is_primary": True}
    )
    for row in others:
        if str(row.get("_id")) == keep_id:
            continue
        repo.update_one(str(row["_id"]), {"is_primary": False})


@router.get("/incidents/{incident_id}/facilities")
def list_facilities(
    incident_id: str,
    facility_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    repo = _repo(incident_id)
    query: Dict[str, Any] = {"incident_id": incident_id}
    if facility_type:
        query["facility_type"] = facility_type
    if status:
        query["status"] = status
    rows = repo.find_many(query, sort=[("facility_type", 1), ("name", 1)])
    return [_serialize(row) for row in rows]


@router.get("/incidents/{incident_id}/facilities/{facility_id}")
def get_facility(incident_id: str, facility_id: str) -> Dict[str, Any]:
    repo = _repo(incident_id)
    row = repo.find_by_id(facility_id)
    if not row or str(row.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Facility not found")
    return _serialize(row)


@router.post("/incidents/{incident_id}/facilities", status_code=201)
def create_facility(incident_id: str, payload: FacilityPayload) -> Dict[str, Any]:
    repo = _repo(incident_id)
    values = payload.model_dump()
    values["capabilities"] = list(values["function_tags"])
    values["served_modules"] = list(values["served_sections"])
    doc = repo.insert_one({"incident_id": incident_id, **values})
    if payload.is_primary:
        _apply_primary_constraint(repo, incident_id, payload.facility_type, str(doc["_id"]))
        doc = repo.find_by_id(str(doc["_id"])) or doc
    return _serialize(doc)


@router.put("/incidents/{incident_id}/facilities/{facility_id}")
def update_facility(incident_id: str, facility_id: str, payload: FacilityPayload) -> Dict[str, Any]:
    repo = _repo(incident_id)
    existing = repo.find_by_id(facility_id)
    if not existing or str(existing.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Facility not found")
    values = payload.model_dump()
    values["capabilities"] = list(values["function_tags"])
    values["served_modules"] = list(values["served_sections"])
    repo.update_one(facility_id, {"incident_id": incident_id, **values})
    if payload.is_primary:
        _apply_primary_constraint(repo, incident_id, payload.facility_type, facility_id)
    updated = repo.find_by_id(facility_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Facility not found after update")
    return _serialize(updated)


@router.delete("/incidents/{incident_id}/facilities/{facility_id}")
def delete_facility(incident_id: str, facility_id: str) -> Dict[str, bool]:
    repo = _repo(incident_id)
    existing = repo.find_by_id(facility_id)
    if not existing or str(existing.get("incident_id")) != incident_id:
        raise HTTPException(status_code=404, detail="Facility not found")
    return {"ok": repo.soft_delete(facility_id)}
