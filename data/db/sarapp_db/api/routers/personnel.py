"""Master personnel catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_int_ids(col) -> None:
    for doc in col.find({"int_id": {"$exists": False}}):
        max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
        next_id = (max_doc["int_id"] + 1) if max_doc else 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})


def _col():
    return get_client()[DB_MASTER][MasterCollections.PERSONNEL]


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    person_id = d.get("person_id") or d.get("int_id") or d.get("id")
    d["id"] = str(person_id) if person_id is not None else None
    d["primary_role"] = d.get("primary_role") or d.get("role") or d.get("rank")
    d["phone"] = d.get("phone") or d.get("contact")
    d["home_unit"] = d.get("home_unit") or d.get("unit")
    d["certifications"] = d.get("certifications") or d.get("certs")
    return d


@router.get("/search")
def search_personnel(
    q: str = Query(""),
    limit: int = Query(50),
) -> list[dict[str, Any]]:
    term = (q or "").strip()
    if not term:
        docs = list(_col().find().sort("name", 1).limit(limit))
        return [_normalize(d) for d in docs]
    t = term.lower()
    docs = list(_col().find().sort("name", 1))
    results = []
    for d in docs:
        haystack = "|".join(filter(None, [
            str(d.get("person_id") or d.get("id") or ""),
            d.get("name") or "",
            d.get("callsign") or "",
            d.get("phone") or "",
            d.get("contact") or "",
        ])).lower()
        if t in haystack:
            results.append(_normalize(d))
        if len(results) >= limit:
            break
    return results


@router.get("")
def list_personnel(
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
            or t in str(d.get("person_id") or d.get("id") or "").lower()
            or t in (d.get("callsign") or "").lower()
        ]
    return [_normalize(d) for d in docs]


@router.post("", status_code=201)
def create_person(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
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
    # person_id defaults to the string form of int_id if not supplied
    if not doc.get("person_id") and not doc.get("id"):
        doc["person_id"] = str(next_id)
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.get("/{person_id}")
def get_person(person_id: str) -> dict[str, Any]:
    doc = (
        _col().find_one({"person_id": person_id})
        or _col().find_one({"id": person_id})
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize(doc)
