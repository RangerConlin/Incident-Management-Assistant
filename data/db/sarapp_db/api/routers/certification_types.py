"""Master certification type catalog API router.

Lockdown collection (see Design Documents/Instructions/
mongodb_schema_decisions.md):
certification types are an admin-controlled taxonomy, not something a field
user creates ad hoc, and ids must stay stable once shipped (personnel
records embed certifications by `cert_type_id` reference, and
`modules/operations/taskings/repository.py` resolves a handful of ids to
CAPF109 codes). Writes are central-catalog authoritative only.

This replaces the hardcoded `modules/personnel/models/cert_catalog.py`
catalog as the source of truth — see
`data/db/sarapp_db/migrations/seed_certification_types_from_hardcoded_catalog.py`
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
_LOCKDOWN_DETAIL = "Certification types are central-catalog authoritative; edit them on the central catalog."


class CertificationTypesRepository(BaseRepository):
    collection_name = MasterCollections.CERTIFICATION_TYPES
    soft_deletes = False


def _repo() -> CertificationTypesRepository:
    return CertificationTypesRepository(get_master_db())


def _require_central(repo: CertificationTypesRepository) -> None:
    if not is_central_master_db(repo._db):
        raise HTTPException(status_code=403, detail=_LOCKDOWN_DETAIL)


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["tags"] = list(d.get("tags") or [])
    d["is_active"] = bool(d.get("is_active", True))
    return d


def _matches(doc: dict[str, Any], term: str) -> bool:
    haystack = "|".join(
        filter(
            None,
            [
                str(doc.get("code") or ""),
                str(doc.get("name") or ""),
                str(doc.get("category") or ""),
                str(doc.get("issuing_org") or ""),
                ",".join(doc.get("tags") or []),
            ],
        )
    ).lower()
    return term.lower() in haystack


@router.get("")
def list_certification_types(
    search: str = Query(""),
    category: str = Query(""),
    include_inactive: bool = Query(False),
) -> list[dict[str, Any]]:
    repo = _repo()
    # No _ensure_record_ids backfill here, deliberately: unlike collections
    # that gained their id field after already having real data, every
    # certification_types document has always been created with "id"
    # already set (via next_record_id below). A backfill call here would
    # (and once did, corrupting real data during this migration) silently
    # assign a fake "id" to any unrelated document that happens to exist in
    # this collection without one — see the legacy-data cleanup in
    # Design Documents/legacycode.md.
    query: dict[str, Any] = {}
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    if category:
        query["category"] = category
    docs = repo.find_many(query, sort=[("category", 1), ("code", 1)])
    if search.strip():
        term = search.strip()
        docs = [d for d in docs if _matches(d, term)]
    return [_normalize(d) for d in docs]


@router.get("/{cert_type_id}")
def get_certification_type(cert_type_id: int) -> dict[str, Any]:
    doc = _repo().find_one({_RECORD_FIELD: cert_type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Certification type not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_certification_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
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
        "category": str(body.get("category") or "").strip(),
        "issuing_org": str(body.get("issuing_org") or "").strip(),
        "parent_id": body.get("parent_id"),
        "tags": [str(t).strip().upper() for t in (body.get("tags") or []) if str(t).strip()],
        "is_active": bool(body.get("is_active", True)),
    }
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.put("/{cert_type_id}")
def update_certification_type(cert_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    _require_central(repo)
    existing = repo.find_one({_RECORD_FIELD: cert_type_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Certification type not found")
    updates: dict[str, Any] = {}
    for field in ("code", "name", "category", "issuing_org", "parent_id", "is_active"):
        if field in body:
            updates[field] = body[field]
    if "tags" in body:
        updates["tags"] = [str(t).strip().upper() for t in (body["tags"] or []) if str(t).strip()]
    repo.update_one(existing["_id"], updates)
    updated = repo.find_by_id(existing["_id"])
    return _normalize(updated or existing)


@router.delete("/{cert_type_id}", status_code=204)
def delete_certification_type(cert_type_id: int) -> None:
    repo = _repo()
    _require_central(repo)
    existing = repo.find_one({_RECORD_FIELD: cert_type_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Certification type not found")
    repo.delete_one(existing["_id"])
