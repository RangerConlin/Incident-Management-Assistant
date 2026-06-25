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
    missing = list(col.find({"int_id": {"$exists": False}}))
    if not missing:
        return
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (max_doc["int_id"] + 1) if max_doc else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _col():
    return get_client()[DB_MASTER][MasterCollections.PERSONNEL]


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    person_id = next((d[k] for k in ("person_id", "int_id", "id") if d.get(k) is not None), None)
    d["id"] = str(person_id) if person_id is not None else None
    d["primary_role"] = d.get("primary_role") or d.get("role") or d.get("rank")
    d["phone"] = d.get("phone") or d.get("contact")
    d["home_unit"] = d.get("home_unit") or d.get("unit")
    d["certifications"] = d.get("certifications") or d.get("certs")
    d["is_medic"] = bool(d.get("is_medic", False))
    d["badge_number"] = d.get("badge_number") or ""
    d["incident_history"] = d.get("incident_history") or []
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
            d.get("badge_number") or "",
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
            or t in (d.get("badge_number") or "").lower()
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


def _find_person(col, person_id: str):
    return col.find_one({"person_id": person_id}) or col.find_one({"id": person_id})


@router.get("/{person_id}")
def get_person(person_id: str) -> dict[str, Any]:
    col = _col()
    _ensure_int_ids(col)
    doc = (
        col.find_one({"person_id": person_id})
        or col.find_one({"id": person_id})
        or (col.find_one({"int_id": int(person_id)}) if person_id.isdigit() else None)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize(doc)


@router.put("/{person_id}")
def update_person(
    person_id: str,
    body: dict[str, Any] = Body(...),
    active_incident_id: str | None = Query(None),
) -> dict[str, Any]:
    col = _col()
    _ensure_int_ids(col)
    existing = (
        col.find_one({"person_id": person_id})
        or col.find_one({"id": person_id})
        or (col.find_one({"int_id": int(person_id)}) if person_id.isdigit() else None)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    body.pop("_id", None)
    body.pop("int_id", None)
    body.pop("id", None)
    body.pop("incident_history", None)
    body["updated_at"] = _utcnow()
    col.update_one({"_id": existing["_id"]}, {"$set": body})
    updated = col.find_one({"_id": existing["_id"]})

    # Push the edit down to the active incident's local copy only. Other
    # incidents catch up the next time they're loaded (see
    # operations.sync_incident_personnel_from_master).
    if active_incident_id:
        try:
            from sarapp_db.mongo.client import get_db
            master_id = updated.get("int_id")
            incident_col = get_db(f"sarapp_incident_{active_incident_id}")["incident_personnel"]
            sync_fields = {
                "name": updated.get("name"),
                "rank": updated.get("rank"),
                "callsign": updated.get("callsign"),
                "role": updated.get("primary_role") or updated.get("role"),
                "phone": updated.get("phone"),
                "email": updated.get("email"),
                "organization": updated.get("home_unit") or updated.get("organization"),
                "unit": updated.get("home_unit") or updated.get("unit"),
                "badge_number": updated.get("badge_number"),
                "is_medic": bool(updated.get("is_medic", False)),
            }
            incident_col.update_one({"master_id": master_id}, {"$set": sync_fields})
        except Exception:
            pass

    return _normalize(updated)


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: str) -> None:
    col = _col()
    _ensure_int_ids(col)
    existing = (
        col.find_one({"person_id": person_id})
        or col.find_one({"id": person_id})
        or (col.find_one({"int_id": int(person_id)}) if person_id.isdigit() else None)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    col.delete_one({"_id": existing["_id"]})
