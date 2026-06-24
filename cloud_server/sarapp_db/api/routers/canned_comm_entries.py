"""FastAPI router for master canned communication entries."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_SEARCHABLE = ["title", "category", "message", "priority", "status_update"]


class CannedCommEntriesRepository(BaseRepository):
    collection_name = MasterCollections.CANNED_COMM_ENTRIES
    # Keyed by sequential `id`, not `_id`. Existing docs use `deleted` only
    # informally (the legacy get_entry filtered with `{"$ne": True}`); there
    # is no soft-delete workflow exposed by this router, so disable
    # BaseRepository's automatic `deleted: False` filtering.
    soft_deletes = False


def _repo() -> CannedCommEntriesRepository:
    return CannedCommEntriesRepository(get_master_db())


def _next_id(repo: CannedCommEntriesRepository) -> int:
    docs = repo.find_many({}, sort=[("id", -1)], limit=1)
    doc = docs[0] if docs else None
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
    repo = _repo()
    query: dict[str, Any] = {}
    if active_only:
        query["is_active"] = True
    docs = repo.find_many(query, sort=[("title", 1)])
    if search.strip():
        t = search.strip().lower()
        docs = [
            d for d in docs
            if any(t in str(d.get(f) or "").lower() for f in _SEARCHABLE)
        ]
    return [_normalize(d) for d in docs]


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict[str, Any]:
    doc = _repo().find_one({"id": entry_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_entry(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    title = str(body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")
    message = str(body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    new_id = _next_id(repo)
    doc: dict[str, Any] = {
        "id": new_id,
        "title": title,
        "category": (body.get("category") or "").strip() or None,
        "message": message,
        "priority": body.get("priority") or None,
        "notification_level": int(body.get("notification_level") or 0),
        "status_update": body.get("status_update") or None,
        "is_active": bool(body.get("is_active", True)),
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


@router.patch("/{entry_id}")
def update_entry(entry_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"id": entry_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    update: dict[str, Any] = {}
    for field in ("title", "category", "message", "priority",
                  "notification_level", "status_update", "is_active"):
        if field in body:
            update[field] = body[field]
    if "notification_level" in update:
        update["notification_level"] = int(update["notification_level"] or 0)
    repo.update_one(existing["_id"], update)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int) -> None:
    repo = _repo()
    existing = repo.find_one({"id": entry_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    repo.delete_one(existing["_id"])
