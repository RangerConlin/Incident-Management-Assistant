"""Master vehicle catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import _ensure_record_ids, next_record_id

router = APIRouter()

_RECORD_FIELD = "vehicle_record"

_DEFAULT_STATUSES = ["Available", "In Service", "Out of Service", "Retired"]
_DEFAULT_TYPES = ["Passenger Vehicle", "Utility", "Support", "Other"]


def _col():
    return get_client()[DB_MASTER][MasterCollections.VEHICLES]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["vehicle_record"] = d.get("vehicle_record")
    d["vehicle_id"] = d.get("vehicle_id") or ""
    return d


def _find_by_record(col, vehicle_record: int) -> dict[str, Any] | None:
    return col.find_one({_RECORD_FIELD: vehicle_record})


@router.get("")
def list_vehicles(
    search: str = Query(""),
    status_filter: str = Query(""),
    type_filter: str = Query(""),
) -> list[dict[str, Any]]:
    col = _col()
    _ensure_record_ids(col, _RECORD_FIELD)
    query: dict[str, Any] = {}
    if status_filter:
        query["status_id"] = status_filter
    if type_filter:
        query["type_id"] = type_filter
    docs = list(col.find(query).sort("vehicle_id", 1))
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if t in (d.get("vehicle_id") or "").lower()
            or t in (d.get("vin") or "").lower()
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


@router.get("/{vehicle_record}")
def get_vehicle(vehicle_record: int) -> dict[str, Any]:
    doc = _find_by_record(_col(), vehicle_record)
    if not doc:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _normalize(doc)


class VehicleBody(BaseModel):
    vehicle_id: str = ""  # user-entered ID (e.g. "Engine 2", "Unit 7")
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
    next_id = next_record_id(col, _RECORD_FIELD)
    now = _utcnow()
    doc: dict[str, Any] = {
        _RECORD_FIELD: next_id,
        **body.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.patch("/{vehicle_record}")
def update_vehicle(
    vehicle_record: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _col()
    existing = _find_by_record(col, vehicle_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    body.pop(_RECORD_FIELD, None)
    body.pop("_id", None)
    body["updated_at"] = _utcnow()
    col.update_one({"_id": existing["_id"]}, {"$set": body})
    doc = col.find_one({"_id": existing["_id"]})
    return _normalize(doc)


@router.delete("/{vehicle_record}", status_code=204)
def delete_vehicle(vehicle_record: int) -> None:
    col = _col()
    existing = _find_by_record(col, vehicle_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    col.delete_one({"_id": existing["_id"]})
