"""Master qualification catalog API router.

Lockdown collection (see Design Documents/Instructions/
mongodb_schema_decisions.md and backlog.md's dual-key/lockdown split):
qualification profiles are an admin-controlled taxonomy describing
higher-level role requirements (e.g. "Medic", "Pilot", "Team Leader"),
expressed in terms of tags on the certification catalog
(`certification_types.py`) that a person's certifications must carry.
Writes are central-catalog authoritative only, same as certification types.

This replaces the hardcoded `modules/personnel/models/validation_profiles.py`
catalog as the source of truth — see
`data/db/sarapp_db/migrations/seed_qualification_types_from_hardcoded_profiles.py`
for the one-time migration that seeded this collection from it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db, is_central_master_db
from sarapp_db.mongo.int_id import next_record_id
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_RECORD_FIELD = "id"
_LOCKDOWN_DETAIL = "Qualification types are central-catalog authoritative; edit them on the central catalog."


class QualificationTypesRepository(BaseRepository):
    collection_name = MasterCollections.QUALIFICATION_TYPES
    soft_deletes = False


def _repo() -> QualificationTypesRepository:
    return QualificationTypesRepository(get_master_db())


def _require_central(repo: QualificationTypesRepository) -> None:
    if not is_central_master_db(repo._db):
        raise HTTPException(status_code=403, detail=_LOCKDOWN_DETAIL)


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["any_tags"] = list(d.get("any_tags") or [])
    d["all_tags"] = list(d.get("all_tags") or [])
    d["min_level"] = int(d.get("min_level") or 2)
    d["is_active"] = bool(d.get("is_active", True))
    return d


def _matches(doc: dict[str, Any], term: str) -> bool:
    haystack = "|".join(
        filter(
            None,
            [
                str(doc.get("code") or ""),
                str(doc.get("name") or ""),
                ",".join(doc.get("any_tags") or []),
                ",".join(doc.get("all_tags") or []),
            ],
        )
    ).lower()
    return term.lower() in haystack


@router.get("")
def list_qualification_types(
    search: str = Query(""),
    include_inactive: bool = Query(False),
) -> list[dict[str, Any]]:
    repo = _repo()
    query: dict[str, Any] = {}
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    docs = repo.find_many(query, sort=[("name", 1)])
    if search.strip():
        term = search.strip()
        docs = [d for d in docs if _matches(d, term)]
    return [_normalize(d) for d in docs]


@router.get("/{qualification_type_id}")
def get_qualification_type(qualification_type_id: int) -> dict[str, Any]:
    doc = _repo().find_one({_RECORD_FIELD: qualification_type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Qualification type not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_qualification_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    _require_central(repo)
    code = str(body.get("code") or "").strip()
    name = str(body.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(status_code=422, detail="code and name are required")
    next_id = next_record_id(repo._col, _RECORD_FIELD)
    doc: dict[str, Any] = {
        _RECORD_FIELD: next_id,
        "code": code,
        "name": name,
        "any_tags": [str(t).strip().upper() for t in (body.get("any_tags") or []) if str(t).strip()],
        "all_tags": [str(t).strip().upper() for t in (body.get("all_tags") or []) if str(t).strip()],
        "min_level": int(body.get("min_level") or 2),
        "is_active": bool(body.get("is_active", True)),
    }
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.put("/{qualification_type_id}")
def update_qualification_type(qualification_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    _require_central(repo)
    existing = repo.find_one({_RECORD_FIELD: qualification_type_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Qualification type not found")
    updates: dict[str, Any] = {}
    for field in ("code", "name", "min_level", "is_active"):
        if field in body:
            updates[field] = body[field]
    if "any_tags" in body:
        updates["any_tags"] = [str(t).strip().upper() for t in (body["any_tags"] or []) if str(t).strip()]
    if "all_tags" in body:
        updates["all_tags"] = [str(t).strip().upper() for t in (body["all_tags"] or []) if str(t).strip()]
    repo.update_one(existing["_id"], updates)
    updated = repo.find_by_id(existing["_id"])
    return _normalize(updated or existing)


@router.delete("/{qualification_type_id}", status_code=204)
def delete_qualification_type(qualification_type_id: int) -> None:
    repo = _repo()
    _require_central(repo)
    existing = repo.find_one({_RECORD_FIELD: qualification_type_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Qualification type not found")
    repo.delete_one(existing["_id"])
