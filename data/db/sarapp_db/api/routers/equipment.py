"""Master equipment catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()


def _col():
    return get_client()[DB_MASTER][MasterCollections.EQUIPMENT]


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
def list_equipment(
    search: str = Query(""),
    limit: int = Query(200),
) -> list[dict[str, Any]]:
    col = _col()
    _ensure_int_ids(col)
    docs = list(col.find().sort("name", 1).limit(limit))
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
    doc = _col().find_one({"int_id": equipment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_equipment(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _col()
    _ensure_int_ids(col)
    body.pop("_id", None)
    body.pop("int_id", None)
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (max_doc["int_id"] + 1) if max_doc else 1
    now = _utcnow()
    doc: dict[str, Any] = {
        "int_id": next_id,
        **body,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.patch("/{equipment_id}")
def update_equipment(
    equipment_id: int, body: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    col = _col()
    existing = col.find_one({"int_id": equipment_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Equipment not found")
    body.pop("int_id", None)
    body.pop("_id", None)
    body["updated_at"] = _utcnow()
    col.update_one({"int_id": equipment_id}, {"$set": body})
    doc = col.find_one({"int_id": equipment_id})
    return _normalize(doc)


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int) -> None:
    result = _col().delete_one({"int_id": equipment_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Equipment not found")
