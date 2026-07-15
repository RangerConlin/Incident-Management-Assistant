"""Master personnel catalog API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.int_id import _ensure_record_ids, next_record_id
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_RECORD_FIELD = "person_record"
_DUPLICATE_FIELDS = (
    "person_id",
    "name",
    "first_name",
    "last_name",
    "callsign",
    "primary_role",
    "role",
    "rank",
    "home_unit",
    "organization",
    "email",
    "phone",
    "radio_id",
    "title",
    "status",
)


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _personnel_repo() -> PersonnelRepository:
    return PersonnelRepository(get_master_db())


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    d["person_record"] = d.get("person_record")
    d["person_id"] = d.get("person_id") or ""
    d["primary_role"] = d.get("primary_role") or d.get("role") or ""
    d["phone"] = d.get("phone")
    d["certifications"] = d.get("certifications") or []
    d["is_medic"] = bool(d.get("is_medic", False))
    d["incident_history"] = d.get("incident_history") or []
    return d


def _find_person(repo: PersonnelRepository, record_id: int) -> dict[str, Any] | None:
    return repo.find_one({_RECORD_FIELD: record_id})


def _matches_personnel_search(doc: dict[str, Any], term: str) -> bool:
    if not term:
        return True
    haystack = "|".join(
        filter(
            None,
            [
                str(doc.get("person_id") or ""),
                str(doc.get("name") or ""),
                str(doc.get("callsign") or ""),
                str(doc.get("phone") or ""),
            ],
        )
    ).lower()
    return term.lower() in haystack


def _clean_scalar(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _duplicate_fingerprint(source: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Build a stable fingerprint for exact-clone prevention.

    `person_id` is intentionally non-unique across distinct people, so we do
    not reject duplicate IDs alone. We only reject a create when the full
    user-editable identity payload matches an existing row.
    """

    normalized: dict[str, str] = {}
    for field in _DUPLICATE_FIELDS:
        normalized[field] = _clean_scalar(source.get(field))
    # Compare the canonical role slot so `role` and `primary_role` collapse.
    normalized["primary_role"] = normalized["primary_role"] or normalized["role"]
    normalized["role"] = normalized["primary_role"]
    normalized["organization"] = normalized["organization"] or normalized["home_unit"]
    normalized["home_unit"] = normalized["home_unit"] or normalized["organization"]
    return tuple((field, normalized[field]) for field in _DUPLICATE_FIELDS)


def _find_exact_duplicate(
    repo: PersonnelRepository,
    body: dict[str, Any],
    *,
    exclude_record: int | None = None,
) -> dict[str, Any] | None:
    target = _duplicate_fingerprint(body)
    for doc in repo.find_many({}, sort=[("person_record", 1)]):
        if exclude_record is not None and doc.get("person_record") == exclude_record:
            continue
        if _duplicate_fingerprint(doc) == target:
            return doc
    return None


@router.get("/search")
def search_personnel(
    q: str = Query(""),
    limit: int = Query(50),
) -> list[dict[str, Any]]:
    term = (q or "").strip()
    repo = _personnel_repo()
    _ensure_record_ids(repo._col, _RECORD_FIELD)
    docs = repo.find_many({}, sort=[("name", 1)])
    if not term:
        return [_normalize(d) for d in docs[:limit]]
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
    repo = _personnel_repo()
    _ensure_record_ids(repo._col, _RECORD_FIELD)
    docs = repo.find_many({}, sort=[("name", 1)])
    if search.strip():
        filtered = []
        for d in docs:
            if _matches_personnel_search(d, search):
                filtered.append(d)
            if len(filtered) >= limit:
                break
        docs = filtered
    else:
        docs = docs[:limit]
    return [_normalize(d) for d in docs]


@router.post("", status_code=201)
def create_person(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _personnel_repo()
    body = dict(body)
    body.pop("_id", None)
    body.pop(_RECORD_FIELD, None)
    duplicate = _find_exact_duplicate(repo, body)
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                "An identical personnel record already exists "
                f"(person_record {duplicate.get('person_record')})."
            ),
        )

    next_id = next_record_id(repo._col, _RECORD_FIELD)
    now = _utcnow()
    doc: dict[str, Any] = {
        _RECORD_FIELD: next_id,
        **body,
        "created_at": now,
        "updated_at": now,
    }
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.get("/{person_record}")
def get_person(person_record: int) -> dict[str, Any]:
    doc = _find_person(_personnel_repo(), person_record)
    if not doc:
        raise HTTPException(status_code=404, detail="Person not found")
    return _normalize(doc)


@router.put("/{person_record}")
def update_person(
    person_record: int,
    body: dict[str, Any] = Body(...),
    active_incident_id: str | None = Query(None),
) -> dict[str, Any]:
    repo = _personnel_repo()
    existing = _find_person(repo, person_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")

    body = dict(body)
    body.pop("_id", None)
    body.pop(_RECORD_FIELD, None)
    body.pop("incident_history", None)

    duplicate = _find_exact_duplicate(repo, body, exclude_record=person_record)
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                "Updating this person would duplicate existing personnel record "
                f"{duplicate.get('person_record')}."
            ),
        )

    body["updated_at"] = _utcnow()
    repo.update_one(existing["_id"], body, touch_updated_at=False)
    updated = repo.find_by_id(existing["_id"])

    if active_incident_id and updated:
        try:
            incident_personnel_col = get_incident_db(active_incident_id)["incident_personnel"]
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
            incident_personnel_col.update_one(
                {_RECORD_FIELD: person_record},
                {"$set": sync_fields},
            )
        except Exception:
            pass

    return _normalize(updated or existing)


@router.delete("/{person_record}", status_code=204)
def delete_person(person_record: int) -> None:
    repo = _personnel_repo()
    existing = _find_person(repo, person_record)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    repo.delete_one(existing["_id"])
