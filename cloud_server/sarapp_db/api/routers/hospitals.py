"""Master hospital catalog API router."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_SEARCHABLE = ["name", "city", "state", "code", "contact_name", "address"]


class HospitalsRepository(BaseRepository):
    collection_name = MasterCollections.HOSPITALS
    # Keyed by sequential `id`, not `_id`; `deleted` here is a plain
    # application flag managed by these handlers, not via
    # BaseRepository.soft_delete — disable the automatic filter.
    soft_deletes = False


def _repo() -> HospitalsRepository:
    return HospitalsRepository(get_master_db())


def _next_id(repo: HospitalsRepository) -> int:
    docs = repo.find_many({}, sort=[("id", -1)], limit=1)
    doc = docs[0] if docs else None
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


def _assert_unique(repo: HospitalsRepository, field: str, value: str, exclude_id: int | None) -> None:
    if not value:
        return
    query: dict[str, Any] = {
        field: {"$regex": f"^{re.escape(value)}$", "$options": "i"},
        "deleted": {"$ne": True},
    }
    if exclude_id is not None:
        query["id"] = {"$ne": int(exclude_id)}
    if repo.find_one(query) is not None:
        raise HTTPException(status_code=409, detail=f"A hospital with the same {field} already exists")


@router.get("")
def list_hospitals(search: str = Query("")) -> list[dict[str, Any]]:
    repo = _repo()
    query: dict[str, Any] = {"deleted": {"$ne": True}}
    if search.strip():
        pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{field: pattern} for field in _SEARCHABLE]
    docs = repo.find_many(query, sort=[("name", 1)])
    return [_normalize(d) for d in docs]


@router.get("/{hospital_id}")
def get_hospital(hospital_id: int) -> dict[str, Any]:
    doc = _repo().find_one({"id": hospital_id, "deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return _normalize(doc)


@router.post("", status_code=201)
def create_hospital(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Hospital name is required")
    _assert_unique(repo, "name", name, None)
    code = body.get("code")
    if code:
        _assert_unique(repo, "code", str(code), None)
    body.pop("_id", None)
    body.pop("id", None)
    new_id = _next_id(repo)
    doc: dict[str, Any] = {
        "id": new_id,
        "hospital_id": str(new_id),
        **body,
        "name": name,
        "deleted": False,
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


@router.patch("/{hospital_id}")
def update_hospital(hospital_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"id": hospital_id, "deleted": {"$ne": True}})
    if not existing:
        raise HTTPException(status_code=404, detail="Hospital not found")
    if "name" in body:
        name = str(body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Hospital name is required")
        _assert_unique(repo, "name", name, hospital_id)
        body["name"] = name
    if body.get("code"):
        _assert_unique(repo, "code", str(body["code"]), hospital_id)
    body.pop("_id", None)
    body.pop("id", None)
    body["hospital_id"] = str(hospital_id)
    repo.update_one(existing["_id"], body)
    return _normalize(repo.find_by_id(existing["_id"]))


@router.delete("/{hospital_id}", status_code=204)
def delete_hospital(hospital_id: int) -> None:
    repo = _repo()
    existing = repo.find_one({"id": hospital_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Hospital not found")
    repo.update_one(existing["_id"], {"deleted": True})
