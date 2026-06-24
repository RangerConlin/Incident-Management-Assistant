"""Master vehicle catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()

_DEFAULT_STATUSES = ["Available", "In Service", "Out of Service", "Retired"]
_DEFAULT_TYPES = ["Passenger Vehicle", "Utility", "Support", "Other"]


def _col():
    return get_client()[DB_MASTER][MasterCollections.VEHICLES]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_vehicle_ids(col) -> None:
    for doc in col.find({"vehicle_id": {"$exists": False}}):
        max_doc = col.find_one({"vehicle_id": {"$exists": True}}, sort=[("vehicle_id", -1)])
        next_id = (max_doc["vehicle_id"] + 1) if max_doc else 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"vehicle_id": next_id}})


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["id"] = d.get("vehicle_id")
    return d


def _find_by_ref(col, ref_id: str) -> dict[str, Any] | None:
    """Look up a vehicle by its id/reference number.

    The reference number is user-editable and may be a legacy auto-assigned
    int or an arbitrary string, so try both forms.
    """
    doc = col.find_one({"vehicle_id": ref_id})
    if doc:
        return doc
    if str(ref_id).isdigit():
        return col.find_one({"vehicle_id": int(ref_id)})
    return None


@router.get("")
def list_vehicles(
    search: str = Query(""),
    status_filter: str = Query(""),
    type_filter: str = Query(""),
) -> list[dict[str, Any]]:
    col = _col()
    _ensure_vehicle_ids(col)
    query: dict[str, Any] = {}
    if status_filter:
        query["status_id"] = status_filter
    if type_filter:
        query["type_id"] = type_filter
    docs = list(col.find(query).sort("make", 1))
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if t in (d.get("vin") or "").lower()
            or t in (d.get("license_plate") or "").lower()
            or t in (d.get("make") or "").lower()
            or t in (d.get("model") or "").lower()
            or t in (d.get("tags") or "").lower()
        ]
    return [_normalize(d) for d in docs]


@router.get("/types")
def list_vehicle_types() -> list[dict[str, Any]]:
    col = _col()
    values = col.distinct("type_id", {"type_id": {"$nin": [None, ""]}})
    entries = [{"id": v, "name": v} for v in sorted(values) if v]
    if not entries:
        entries = [{"id": t, "name": t} for t in _DEFAULT_TYPES]
    return entries


@router.get("/statuses")
def list_vehicle_statuses() -> list[dict[str, Any]]:
    col = _col()
    values = col.distinct("status_id", {"status_id": {"$nin": [None, ""]}})
    seen = {v for v in values if v}
    entries = [{"id": v, "name": v} for v in sorted(seen)]
    for default in _DEFAULT_STATUSES:
        if default not in seen:
            entries.append({"id": default, "name": default})
    return entries


@router.get("/{vehicle_id}")
def get_vehicle(vehicle_id: str) -> dict[str, Any]:
    doc = _find_by_ref(_col(), vehicle_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _normalize(doc)


class VehicleBody(BaseModel):
    id: str | None = None
    vin: str = ""
    license_plate: str = ""
    year: int | None = None
    make: str = ""
    model: str = ""
    capacity: int = 0
    type_id: str = ""
    status_id: str = "Available"
    tags: str = ""
    organization: str = ""
    resource_type_id: int | None = None


@router.post("", status_code=201)
def create_vehicle(body: VehicleBody) -> dict[str, Any]:
    col = _col()
    _ensure_vehicle_ids(col)

    requested_id = body.id.strip() if body.id else None
    if requested_id:
        if _find_by_ref(col, requested_id):
            raise HTTPException(status_code=409, detail="Vehicle ID is already in use")
        next_id: Any = requested_id
    else:
        max_doc = col.find_one({"vehicle_id": {"$exists": True}}, sort=[("vehicle_id", -1)])
        next_id = (max_doc["vehicle_id"] + 1) if max_doc else 1

    now = _utcnow()
    doc: dict[str, Any] = {
        "vehicle_id": next_id,
        **body.model_dump(exclude={"id"}),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.patch("/{vehicle_id}")
def update_vehicle(
    vehicle_id: str, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _col()
    existing = _find_by_ref(col, vehicle_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    body.pop("vehicle_id", None)
    body.pop("_id", None)
    new_ref = body.pop("id", None)
    if new_ref is not None:
        new_ref = str(new_ref).strip() or None

    update_fields = dict(body)
    if new_ref and new_ref != str(existing.get("vehicle_id")):
        other = _find_by_ref(col, new_ref)
        if other and other["_id"] != existing["_id"]:
            raise HTTPException(status_code=409, detail="Vehicle ID is already in use")
        update_fields["vehicle_id"] = new_ref

    update_fields["updated_at"] = _utcnow()
    col.update_one({"_id": existing["_id"]}, {"$set": update_fields})
    doc = col.find_one({"_id": existing["_id"]})
    return _normalize(doc)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: str) -> None:
    col = _col()
    existing = _find_by_ref(col, vehicle_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    col.delete_one({"_id": existing["_id"]})
