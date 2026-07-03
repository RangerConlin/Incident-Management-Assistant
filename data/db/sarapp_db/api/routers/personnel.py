"""Master personnel catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import _ensure_record_ids, next_record_id

router = APIRouter()

_RECORD_FIELD = "person_record"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _col():
    return get_client()[DB_MASTER][MasterCollections.PERSONNEL]


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["person_record"] = d.get("person_record")
    d["person_id"] = d.get("person_id") or ""
    d["primary_role"] = d.get("primary_role") or d.get("role") or d.get("rank")
    d["phone"] = d.get("phone")
    d["certifications"] = d.get("certifications") or []
    d["is_medic"] = bool(d.get("is_medic", False))
    d["incident_history"] = d.get("incident_history") or []
    return d


def _find_person(col, record_id: int):
    return col.find_one({_RECORD_FIELD: record_id})


def _matches_personnel_search(doc: dict[str, Any], term: str) -> bool:
    if not term:
        return True
    haystack = "|".join(filter(None, [
        str(doc.get("person_id") or ""),
        str(doc.get("name") or ""),
        str(doc.get("callsign") or ""),
        str(doc.get("phone") or ""),
    ])).lower()
    return term.lower() in haystack


@router.get("/search")
def search_personnel(
    q: str = Query(""),
    limit: int = Query(50),
) -> list[dict[str, Any]]:
    term = (q or "").strip()
    col = _col()
    if not term:
        docs = list(col.find().sort("name", 1).limit(limit))
        return [_normalize(d) for d in docs]
    docs = list(col.find().sort("name", 1))
    results = []
    for d in docs:
        if _matches_personnel_search(d, term):
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
    _ensure_record_ids(col, _RECORD_FIELD)
    if search.strip():
        docs = []
        for d in col.find().sort("name", 1):
            if _matches_personnel_search(d, search):
                docs.append(d)
            if len(docs) >= limit:
                break
    else:
        docs = list(col.find().sort("name", 1).limit(limit))
    return [_normalize(d) for d in docs]


@router.post("", status_code=201)
def create_person(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _col()
    body.pop("_id", None)
    body.pop(_RECORD_FIELD, None)
    next_id = next_record_id(col, _RECORD_FIELD)
    now = _utcnow()
    doc: dict[str, Any] = {
        _RECORD_FIELD: next_id,
        **body,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return _normalize(doc)


@router.get("/{person_record}")
def get_person(person_record: int) -> dict[str, Any]:
    doc = _find_person(_col(), person_record)
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize(doc)


@router.put("/{person_record}")
def update_person(
    person_record: int,
    body: dict[str, Any] = Body(...),
    active_incident_id: str | None = Query(None),
) -> dict[str, Any]:
    col = _col()
    existing = _find_person(col, person_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    body.pop("_id", None)
    body.pop(_RECORD_FIELD, None)
    body.pop("incident_history", None)
    body["updated_at"] = _utcnow()
    col.update_one({"_id": existing["_id"]}, {"$set": body})
    updated = col.find_one({"_id": existing["_id"]})

    if active_incident_id:
        try:
            from sarapp_db.mongo.client import get_db
            incident_col = get_db(f"sarapp_incident_{active_incident_id}")["incident_personnel"]
            sync_fields = {
                "name": updated.get("name"),
                "rank": updated.get("rank"),
                "callsign": updated.get("callsign"),
                "role": updated.get("primary_role") or updated.get("role"),
                "phone": updated.get("phone"),
                "email": updated.get("email"),
                "organization": updated.get("organization"),
                "person_id": updated.get("person_id") or "",
                "is_medic": bool(updated.get("is_medic", False)),
            }
            incident_col.update_one({_RECORD_FIELD: person_record}, {"$set": sync_fields})
        except Exception:
            pass

    return _normalize(updated)


@router.delete("/{person_record}", status_code=204)
def delete_person(person_record: int) -> None:
    col = _col()
    existing = _find_person(col, person_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    col.delete_one({"_id": existing["_id"]})
