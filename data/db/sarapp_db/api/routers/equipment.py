"""Master equipment catalog API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.mongo.int_id import _ensure_record_ids, next_record_id

router = APIRouter()

_RECORD_FIELD = "equipment_record"


class EquipmentRepository(BaseRepository):
    collection_name = MasterCollections.EQUIPMENT
    soft_deletes = False


def _repo() -> EquipmentRepository:
    return EquipmentRepository(get_master_db())


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["equipment_record"] = d.get("equipment_record")
    d["equipment_id"] = d.get("equipment_id") or ""
    return d


@router.get("")
def list_equipment(
    search: str = Query(""),
    limit: int = Query(200),
) -> list[dict[str, Any]]:
    repo = _repo()
    _ensure_record_ids(repo._col, _RECORD_FIELD)
    docs = repo.find_many({}, sort=[("name", 1)], limit=limit)
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if t in (d.get("name") or "").lower()
            or t in (d.get("type") or "").lower()
            or t in (d.get("serial_number") or "").lower()
            or t in (d.get("equipment_id") or "").lower()
        ]
    return [_normalize(d) for d in docs]


@router.get("/{equipment_record}")
def get_equipment(equipment_record: int) -> dict[str, Any]:
    doc = _repo().find_one({_RECORD_FIELD: equipment_record})
    if not doc:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_equipment(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    body.pop("_id", None)
    body.pop(_RECORD_FIELD, None)
    next_id = next_record_id(repo._col, _RECORD_FIELD)
    doc: dict[str, Any] = {
        _RECORD_FIELD: next_id,
        **body,
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


@router.patch("/{equipment_record}")
def update_equipment(
    equipment_record: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({_RECORD_FIELD: equipment_record})
    if not existing:
        raise HTTPException(status_code=404, detail="Equipment not found")
    body.pop(_RECORD_FIELD, None)
    body.pop("_id", None)
    repo.update_one(existing["_id"], body)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


@router.delete("/{equipment_record}", status_code=204)
def delete_equipment(equipment_record: int) -> None:
    repo = _repo()
    existing = repo.find_one({_RECORD_FIELD: equipment_record})
    if not existing:
        raise HTTPException(status_code=404, detail="Equipment not found")
    repo.delete_one(existing["_id"])
