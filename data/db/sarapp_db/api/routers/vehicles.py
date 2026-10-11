"""Master vehicle catalog API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import _ensure_record_ids, dual_key_field, next_record_id
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.sync.readthrough import refresh_collection_before_read

router = APIRouter()

_RECORD_FIELD = "vehicle_record"
_MASTER_RECORD_FIELD = "vehicle_record_master"

_DEFAULT_STATUSES = ["Available", "In Service", "Out of Service", "Retired"]
_DEFAULT_TYPES = ["Passenger Vehicle", "Utility", "Support", "Other"]


class VehicleRepository(BaseRepository):
    collection_name = MasterCollections.VEHICLES
    soft_deletes = False


def _repo() -> VehicleRepository:
    return VehicleRepository(get_master_db())


def _record_field(repo: VehicleRepository) -> str:
    return dual_key_field(repo._db, _RECORD_FIELD, _MASTER_RECORD_FIELD)


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["vehicle_record"] = d.get("vehicle_record")
    d["vehicle_record_master"] = d.get("vehicle_record_master")
    d["vehicle_id"] = d.get("vehicle_id") or ""
    return d


def _find_by_record(repo: VehicleRepository, vehicle_record: int) -> dict[str, Any] | None:
    return repo.find_one({_record_field(repo): vehicle_record})


@router.get("")
def list_vehicles(
    search: str = Query(""),
    status_filter: str = Query(""),
    type_filter: str = Query(""),
) -> list[dict[str, Any]]:
    refresh_collection_before_read(MasterCollections.VEHICLES)
    repo = _repo()
    _ensure_record_ids(repo._col, _record_field(repo))
    query: dict[str, Any] = {}
    if status_filter:
        query["status_id"] = status_filter
    if type_filter:
        query["type_id"] = type_filter
    docs = repo.find_many(query, sort=[("vehicle_id", 1)])
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
    repo = _repo()
    values = repo._col.distinct("type_id", {"type_id": {"$nin": [None, ""]}})
    entries = [{"id": v, "name": v} for v in sorted(values) if v]
    if not entries:
        entries = [{"id": t, "name": t} for t in _DEFAULT_TYPES]
    return entries


@router.get("/statuses")
def list_vehicle_statuses() -> list[dict[str, Any]]:
    repo = _repo()
    values = repo._col.distinct("status_id", {"status_id": {"$nin": [None, ""]}})
    seen = {v for v in values if v}
    entries = [{"id": v, "name": v} for v in sorted(seen)]
    for default in _DEFAULT_STATUSES:
        if default not in seen:
            entries.append({"id": default, "name": default})
    return entries


@router.get("/{vehicle_record}")
def get_vehicle(vehicle_record: int) -> dict[str, Any]:
    refresh_collection_before_read(MasterCollections.VEHICLES)
    doc = _find_by_record(_repo(), vehicle_record)
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
    repo = _repo()
    field = _record_field(repo)
    doc: dict[str, Any] = {
        field: next_record_id(repo._col, field),
        **body.model_dump(),
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


@router.patch("/{vehicle_record}")
def update_vehicle(
    vehicle_record: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _repo()
    existing = _find_by_record(repo, vehicle_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    body.pop(_RECORD_FIELD, None)
    body.pop(_MASTER_RECORD_FIELD, None)
    body.pop("_id", None)
    repo.update_one(existing["_id"], body)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


@router.delete("/{vehicle_record}", status_code=204)
def delete_vehicle(vehicle_record: int) -> None:
    repo = _repo()
    existing = _find_by_record(repo, vehicle_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    repo.delete_one(existing["_id"])
