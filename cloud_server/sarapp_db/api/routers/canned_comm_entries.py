"""FastAPI router for master canned communication entries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

router = APIRouter()

_SEARCHABLE = ["title", "category", "message", "priority", "status_update"]


def _col():
    return get_master_db()[MasterCollections.CANNED_COMM_ENTRIES]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_id(col) -> int:
    doc = col.find_one(sort=[("id", -1)], projection={"id": 1})
    return int(doc["id"]) + 1 if doc and doc.get("id") is not None else 1


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    if d.get("is_active") is None:
        d["is_active"] = True
    d["notification_level"] = int(d.get("notification_level") or 0)
    return d


@router.get("")
def list_entries(
    search: str = Query(""),
    active_only: bool = Query(False),
) -> list[dict[str, Any]]:
    col = _col()
    query: dict[str, Any] = {}
    if active_only:
        query["is_active"] = True
    docs = list(col.find(query).sort("title", 1))
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if any(t in str(d.get(f) or "").lower() for f in _SEARCHABLE)
        ]
    return [_normalize(d) for d in docs]


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict[str, Any]:
    doc = _col().find_one({"id": entry_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_entry(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _col()
    title = str(body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")
    message = str(body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    now = _utcnow()
    new_id = _next_id(col)
    doc: dict[str, Any] = {
        "id": new_id,
        "title": title,
        "category": (body.get("category") or "").strip() or None,
        "message": message,
        "priority": body.get("priority") or None,
        "notification_level": int(body.get("notification_level") or 0),
        "status_update": body.get("status_update") or None,
        "is_active": bool(body.get("is_active", True)),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _normalize(doc)


@router.patch("/{entry_id}")
def update_entry(entry_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _col()
    existing = col.find_one({"id": entry_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    update: dict[str, Any] = {"updated_at": _utcnow()}
    for field in ("title", "category", "message", "priority",
                  "notification_level", "status_update", "is_active"):
        if field in body:
            update[field] = body[field]
    if "notification_level" in update:
        update["notification_level"] = int(update["notification_level"] or 0)
    col.update_one({"id": entry_id}, {"$set": update})
    doc = col.find_one({"id": entry_id})
    return _normalize(doc)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int) -> None:
    col = _col()
    result = col.delete_one({"id": entry_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
