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


def _ensure_int_ids(col) -> None:
    for doc in col.find({"int_id": {"$exists": False}}):
        max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
        next_id = (max_doc["int_id"] + 1) if max_doc else 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["id"] = d.get("int_id")
    return d


@router.get("")
def list_vehicles(
    search: str = Query(""),
    status_filter: str = Query(""),
    type_filter: str = Query(""),
) -> list[dict[str, Any]]:
    col = _col()
    _ensure_int_ids(col)
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
def get_vehicle(vehicle_id: int) -> dict[str, Any]:
    doc = _col().find_one({"int_id": vehicle_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _normalize(doc)


class VehicleBody(BaseModel):
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
    _ensure_int_ids(col)
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (max_doc["int_id"] + 1) if max_doc else 1
    now = _utcnow()
    doc: dict[str, Any] = {
        "int_id": next_id,
        **body.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.patch("/{vehicle_id}")
def update_vehicle(
    vehicle_id: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _col()
    existing = col.find_one({"int_id": vehicle_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    body.pop("int_id", None)
    body.pop("_id", None)
    body["updated_at"] = _utcnow()
    col.update_one({"int_id": vehicle_id}, {"$set": body})
    doc = col.find_one({"int_id": vehicle_id})
    return _normalize(doc)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int) -> None:
    result = _col().delete_one({"int_id": vehicle_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
