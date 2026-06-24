"""Master equipment catalog API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class EquipmentRepository(BaseRepository):
    collection_name = MasterCollections.EQUIPMENT
    # Keyed by sequential `int_id`, not `_id`; no `deleted` field — hard deletes.
    soft_deletes = False


def _repo() -> EquipmentRepository:
    return EquipmentRepository(get_master_db())


def _ensure_int_ids(repo: EquipmentRepository) -> None:
    col = repo._col
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
def list_equipment(
    search: str = Query(""),
    limit: int = Query(200),
) -> list[dict[str, Any]]:
    repo = _repo()
    _ensure_int_ids(repo)
    docs = repo.find_many({}, sort=[("name", 1)], limit=limit)
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if t in (d.get("name") or "").lower()
            or t in (d.get("type") or "").lower()
            or t in (d.get("serial_number") or "").lower()
        ]
    return [_normalize(d) for d in docs]


@router.get("/{equipment_id}")
def get_equipment(equipment_id: int) -> dict[str, Any]:
    doc = _repo().find_one({"int_id": equipment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_equipment(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    _ensure_int_ids(repo)
    body.pop("_id", None)
    body.pop("int_id", None)
    max_doc = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (max_doc["int_id"] + 1) if max_doc else 1
    doc: dict[str, Any] = {
        "int_id": next_id,
        **body,
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


@router.patch("/{equipment_id}")
def update_equipment(
    equipment_id: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"int_id": equipment_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Equipment not found")
    body.pop("int_id", None)
    body.pop("_id", None)
    repo.update_one(existing["_id"], body)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int) -> None:
    repo = _repo()
    existing = repo.find_one({"int_id": equipment_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Equipment not found")
    repo.delete_one(existing["_id"])
