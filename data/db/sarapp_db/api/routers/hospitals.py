"""Master hospital catalog API router."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

router = APIRouter()

_SEARCHABLE = ["name", "city", "state", "code", "contact_name", "address"]


def _col():
    return get_master_db()[MasterCollections.HOSPITALS]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_id(col) -> int:
    doc = col.find_one(sort=[("id", -1)], projection={"id": 1})
    return int(doc["id"]) + 1 if doc and doc.get("id") is not None else 1


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    if d.get("id") is None and d.get("hospital_id"):
        try:
            d["id"] = int(d["hospital_id"])
        except (TypeError, ValueError):
            d["id"] = None
    return d


def _assert_unique(col, field: str, value: str, exclude_id: int | None) -> None:
    if not value:
        return
    query: dict[str, Any] = {
        field: {"$regex": f"^{re.escape(value)}$", "$options": "i"},
        "deleted": {"$ne": True},
    }
    if exclude_id is not None:
        query["id"] = {"$ne": int(exclude_id)}
    if col.find_one(query, projection={"id": 1}) is not None:
        raise HTTPException(status_code=409, detail=f"A hospital with the same {field} already exists")


@router.get("")
def list_hospitals(search: str = Query("")) -> list[dict[str, Any]]:
    col = _col()
    query: dict[str, Any] = {"deleted": {"$ne": True}}
    if search.strip():
        pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{field: pattern} for field in _SEARCHABLE]
    docs = list(col.find(query).sort("name", 1))
    return [_normalize(d) for d in docs]


@router.get("/{hospital_id}")
def get_hospital(hospital_id: int) -> dict[str, Any]:
    doc = _col().find_one({"id": hospital_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_hospital(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _col()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Hospital name is required")
    _assert_unique(col, "name", name, None)
    code = body.get("code")
    if code:
        _assert_unique(col, "code", str(code), None)
    body.pop("_id", None)
    body.pop("id", None)
    new_id = _next_id(col)
    now = _utcnow()
    doc: dict[str, Any] = {
        "_id": str(uuid.uuid4()),
        "id": new_id,
        "hospital_id": str(new_id),
        **body,
        "name": name,
        "deleted": False,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _normalize(doc)


@router.patch("/{hospital_id}")
def update_hospital(hospital_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _col()
    existing = col.find_one({"id": hospital_id, "deleted": {"$ne": True}})
    if not existing:
        raise HTTPException(status_code=404, detail="Hospital not found")
    if "name" in body:
        name = str(body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Hospital name is required")
        _assert_unique(col, "name", name, hospital_id)
        body["name"] = name
    if body.get("code"):
        _assert_unique(col, "code", str(body["code"]), hospital_id)
    body.pop("_id", None)
    body.pop("id", None)
    body["hospital_id"] = str(hospital_id)
    body["updated_at"] = _utcnow()
    col.update_one({"id": hospital_id}, {"$set": body})
    return _normalize(col.find_one({"id": hospital_id}))


@router.delete("/{hospital_id}", status_code=204)
def delete_hospital(hospital_id: int) -> None:
    result = _col().update_one(
        {"id": hospital_id}, {"$set": {"deleted": True, "updated_at": _utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Hospital not found")
