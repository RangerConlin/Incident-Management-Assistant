"""Master certification types and embedded personnel cert assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class CertificationTypesRepository(BaseRepository):
    collection_name = MasterCollections.CERTIFICATION_TYPES
    soft_deletes = False


class CertificationTagsRepository(BaseRepository):
    collection_name = MasterCollections.CERTIFICATION_TAGS
    soft_deletes = False


class LegacyPersonnelCertificationsRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL_CERTIFICATIONS
    soft_deletes = False


def _cert_types_repo() -> CertificationTypesRepository:
    return CertificationTypesRepository(get_master_db())


def _cert_tags_repo() -> CertificationTagsRepository:
    return CertificationTagsRepository(get_master_db())


def _legacy_personnel_certs_repo() -> LegacyPersonnelCertificationsRepository:
    return LegacyPersonnelCertificationsRepository(get_master_db())


def _personnel_col():
    return get_master_db()[MasterCollections.PERSONNEL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tags_for_cert(cert_type_id: int) -> list[str]:
    docs = _cert_tags_repo().find_many({"cert_type_id": int(cert_type_id)})
    return [d.get("tag") for d in docs if d.get("tag")]


def _normalize_cert_type(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    cert_id = d.get("int_id") if d.get("int_id") is not None else d.get("id")
    if cert_id is not None:
        cert_id = int(cert_id)
        d["id"] = cert_id
        d["int_id"] = cert_id
        d["tags"] = _tags_for_cert(cert_id)
    d["is_medical"] = bool(d.get("is_medical"))
    return d


def _find_cert_type(cert_type_id: int | None = None, code: str | None = None) -> dict[str, Any] | None:
    repo = _cert_types_repo()
    doc = None
    if cert_type_id is not None:
        doc = repo.find_one({"int_id": int(cert_type_id)})
    if not doc and code:
        doc = repo.find_one({"code": str(code)})
    return _normalize_cert_type(doc) if doc else None


def _find_person(personnel_id: str) -> dict[str, Any] | None:
    col = _personnel_col()
    pid = str(personnel_id)
    return (
        col.find_one({"person_id": pid})
        or col.find_one({"personnel_id": pid})
        or col.find_one({"id": pid})
        or (col.find_one({"int_id": int(pid)}) if pid.isdigit() else None)
    )


def _minimal_person_cert(raw: dict[str, Any]) -> dict[str, int] | None:
    src = dict(raw or {})
    cert_type_id = src.get("cert_type_id") or src.get("int_id") or src.get("id")
    if cert_type_id is None and src.get("code"):
        catalog = _find_cert_type(code=str(src.get("code")))
        cert_type_id = catalog.get("id") if catalog else None
    try:
        cert_type_id = int(cert_type_id)
    except (TypeError, ValueError):
        return None
    try:
        level = max(0, min(3, int(src.get("level", 0))))
    except (TypeError, ValueError):
        level = 0
    return {"cert_type_id": cert_type_id, "level": level}


def _person_cert_rows(person: dict[str, Any]) -> list[dict[str, int]]:
    certs = person.get("certifications") or person.get("certs") or []
    if not isinstance(certs, list):
        return []
    rows: dict[int, dict[str, int]] = {}
    for cert in certs:
        if isinstance(cert, dict):
            row = _minimal_person_cert(cert)
            if row:
                cert_type_id = row["cert_type_id"]
                rows[cert_type_id] = {
                    "cert_type_id": cert_type_id,
                    "level": max(rows.get(cert_type_id, {}).get("level", 0), row["level"]),
                }
    return list(rows.values())


def _legacy_rows(personnel_id: str) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for doc in _legacy_personnel_certs_repo().find_many({"personnel_id": str(personnel_id)}):
        row = _minimal_person_cert(doc)
        if row:
            rows.append(row)
    return rows


def _enriched_row(row: dict[str, int]) -> dict[str, Any]:
    cert_type_id = int(row["cert_type_id"])
    catalog = _find_cert_type(cert_type_id) or {}
    return {
        "cert_type_id": cert_type_id,
        "id": cert_type_id,
        "level": int(row.get("level") or 0),
        "code": catalog.get("code", ""),
        "name": catalog.get("name", ""),
        "category": catalog.get("category", ""),
        "issuing_org": catalog.get("issuing_org", ""),
        "parent_id": catalog.get("parent_id"),
        "tags": catalog.get("tags") or [],
        "is_medical": bool(catalog.get("is_medical")),
    }


@router.get("/types")
def list_cert_types(search: str = "") -> list[dict[str, Any]]:
    repo = _cert_types_repo()
    query = {} if not search else {
        "$or": [
            {"code": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}},
            {"issuing_org": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = repo.find_many(query, sort=[("category", 1), ("code", 1)])
    return [_normalize_cert_type(d) for d in docs]


@router.get("/types/{cert_type_id}")
def get_cert_type(cert_type_id: int) -> dict[str, Any]:
    doc = _find_cert_type(cert_type_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Cert type not found")
    return doc


@router.post("/types", status_code=201)
def upsert_cert_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _cert_types_repo()
    cert_id = body.get("cert_type_id") or body.get("id") or body.get("int_id")
    if cert_id is None:
        raise HTTPException(status_code=422, detail="cert_type_id required")
    cert_id = int(cert_id)
    doc: dict[str, Any] = {
        "int_id": cert_id,
        "code": body.get("code", ""),
        "name": body.get("name", ""),
        "category": body.get("category", ""),
        "issuing_org": body.get("issuing_org", ""),
        "parent_id": body.get("parent_id"),
        "is_medical": bool(body.get("is_medical")),
    }
    existing = repo.find_one({"int_id": cert_id})
    if existing:
        repo.update_one(existing["_id"], doc)
    else:
        repo.insert_one(doc)
    tags_repo = _cert_tags_repo()
    tags_repo.delete_many({"cert_type_id": cert_id})
    for tag in body.get("tags") or []:
        tags_repo.insert_one({"cert_type_id": cert_id, "tag": str(tag)})
    return {"id": cert_id, "int_id": cert_id}


@router.put("/types/{cert_type_id}")
def update_cert_type(cert_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    body["cert_type_id"] = cert_type_id
    return upsert_cert_type(body)


@router.get("/types/{cert_type_id}/tags")
def get_cert_tags(cert_type_id: int) -> list[str]:
    return _tags_for_cert(cert_type_id)


@router.get("/personnel/{personnel_id}")
def list_personnel_certs(personnel_id: str) -> list[dict[str, Any]]:
    person = _find_person(personnel_id)
    if not person:
        return []
    rows = _person_cert_rows(person)
    if not rows:
        rows = _legacy_rows(str(person.get("personnel_id") or person.get("person_id") or person.get("id") or personnel_id))
        if rows:
            _personnel_col().update_one(
                {"_id": person["_id"]},
                {"$set": {"certifications": rows, "updated_at": _utcnow()}},
            )
    return sorted([_enriched_row(row) for row in rows], key=lambda c: (str(c.get("category") or ""), str(c.get("code") or "")))


@router.post("/personnel/{personnel_id}/{cert_type_id}", status_code=201)
def set_personnel_cert(personnel_id: str, cert_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    person = _find_person(personnel_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    if not _find_cert_type(cert_type_id):
        raise HTTPException(status_code=404, detail="Cert type not found")
    row = _minimal_person_cert({"cert_type_id": cert_type_id, "level": body.get("level", 0)})
    if not row:
        raise HTTPException(status_code=422, detail="Invalid certification data")
    rows = [existing for existing in _person_cert_rows(person) if existing["cert_type_id"] != int(cert_type_id)]
    rows.append(row)
    rows.sort(key=lambda c: c["cert_type_id"])
    _personnel_col().update_one(
        {"_id": person["_id"]},
        {"$set": {"certifications": rows, "updated_at": _utcnow()}},
    )
    return _enriched_row(row)


@router.delete("/personnel/{personnel_id}/{cert_type_id}", status_code=204)
def delete_personnel_cert(personnel_id: str, cert_type_id: int) -> None:
    person = _find_person(personnel_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    rows = _person_cert_rows(person)
    updated_rows = [row for row in rows if row["cert_type_id"] != int(cert_type_id)]
    if len(updated_rows) == len(rows):
        raise HTTPException(status_code=404, detail="Cert assignment not found")
    _personnel_col().update_one(
        {"_id": person["_id"]},
        {"$set": {"certifications": updated_rows, "updated_at": _utcnow()}},
    )
