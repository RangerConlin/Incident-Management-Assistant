"""Master certification types and embedded personnel cert assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class CertificationTypesRepository(BaseRepository):
    collection_name = MasterCollections.CERTIFICATION_TYPES
    soft_deletes = False


class CertificationTagsRepository(BaseRepository):
    collection_name = MasterCollections.CERTIFICATION_TAGS
    soft_deletes = False


class LegacyPersonnelCertificationsRepository(BaseRepository):
    """Legacy standalone cert assignment collection.

    Personnel certifications are now stored on each master personnel document in
    the embedded `certifications` array. This repository is retained only so we
    can read any old records during the transition.
    """

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
        or col.find_one({"id": pid})
        or (col.find_one({"int_id": int(pid)}) if pid.isdigit() else None)
    )


def _cert_key(cert: dict[str, Any]) -> str:
    cert_type_id = cert.get("cert_type_id") or cert.get("int_id") or cert.get("id")
    if cert_type_id is not None:
        return f"id:{int(cert_type_id)}"
    return f"code:{str(cert.get('code') or '').strip().upper()}"


def _normalize_person_cert(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a stable embedded personnel-cert shape.

    The UI has used a few different key names over time. Keep the useful data,
    normalize the catalog reference, and enrich the record from the live catalog
    when possible.
    """

    src = dict(raw or {})
    cert_type_id = src.get("cert_type_id") or src.get("int_id") or src.get("id")
    try:
        cert_type_id = int(cert_type_id) if cert_type_id is not None else None
    except (TypeError, ValueError):
        cert_type_id = None

    catalog = _find_cert_type(cert_type_id, src.get("code"))
    if catalog:
        cert_type_id = int(catalog["id"])

    try:
        level = max(0, min(3, int(src.get("level", 0))))
    except (TypeError, ValueError):
        level = 0

    expiration = src.get("expiration") or src.get("expiration_date") or ""
    docs = src.get("docs") or src.get("attachment_url") or ""

    normalized = {
        "id": cert_type_id,
        "cert_type_id": cert_type_id,
        "code": (catalog or src).get("code", ""),
        "name": (catalog or src).get("name", ""),
        "category": (catalog or src).get("category", ""),
        "issuing_org": (catalog or src).get("issuing_org", ""),
        "parent_id": (catalog or src).get("parent_id"),
        "tags": (catalog or src).get("tags") or [],
        "level": level,
        "issue_date": src.get("issue_date") or "",
        "expiration": expiration,
        "expiration_date": expiration,
        "docs": docs,
        "attachment_url": src.get("attachment_url") or docs,
        "verification_status": src.get("verification_status") or "",
        "verified_by": src.get("verified_by") or "",
        "verified_at": src.get("verified_at") or "",
        "source": src.get("source") or "manual",
        "notes": src.get("notes") or "",
        "updated_at": src.get("updated_at") or "",
    }
    return normalized


def _embedded_certs_for_person(person: dict[str, Any]) -> list[dict[str, Any]]:
    certs = person.get("certifications") or person.get("certs") or []
    if not isinstance(certs, list):
        return []
    return [_normalize_person_cert(c) for c in certs if isinstance(c, dict)]


def _legacy_certs_for_person(personnel_id: str) -> list[dict[str, Any]]:
    docs = _legacy_personnel_certs_repo().find_many({"personnel_id": str(personnel_id)})
    rows = []
    for doc in docs:
        doc.pop("_id", None)
        rows.append(_normalize_person_cert(doc))
    return rows


# ---------------------------------------------------------------------------
# Certification Types (read-only catalog mirror)
# ---------------------------------------------------------------------------

@router.get("/types")
def list_cert_types(search: str = "") -> list[dict[str, Any]]:
    repo = _cert_types_repo()
    query = {} if not search else {
        "$or": [
            {"code": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
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
    }
    existing = repo.find_one({"int_id": cert_id})
    if existing:
        repo.update_one(existing["_id"], doc)
    else:
        repo.insert_one(doc)
    tags = body.get("tags") or []
    tags_repo = _cert_tags_repo()
    tags_repo.delete_many({"cert_type_id": cert_id})
    for tag in tags:
        tags_repo.insert_one({"cert_type_id": cert_id, "tag": str(tag)})
    return {"id": cert_id, "int_id": cert_id}


@router.put("/types/{cert_type_id}")
def update_cert_type(cert_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    body["cert_type_id"] = cert_type_id
    return upsert_cert_type(body)


@router.get("/types/{cert_type_id}/tags")
def get_cert_tags(cert_type_id: int) -> list[str]:
    return _tags_for_cert(cert_type_id)


# ---------------------------------------------------------------------------
# Personnel Certifications (embedded on master personnel document)
# ---------------------------------------------------------------------------

@router.get("/personnel/{personnel_id}")
def list_personnel_certs(personnel_id: str) -> list[dict[str, Any]]:
    person = _find_person(personnel_id)
    if not person:
        return []

    rows = _embedded_certs_for_person(person)

    # Transitional fallback: if old standalone records exist and the personnel
    # document has not been populated yet, surface those records and write them
    # back to the personnel document as the new canonical array.
    if not rows:
        rows = _legacy_certs_for_person(str(person.get("person_id") or person.get("id") or personnel_id))
        if rows:
            _personnel_col().update_one(
                {"_id": person["_id"]},
                {"$set": {"certifications": rows, "updated_at": _utcnow()}},
            )

    return sorted(rows, key=lambda c: (str(c.get("category") or ""), str(c.get("code") or "")))


@router.post("/personnel/{personnel_id}/{cert_type_id}", status_code=201)
def set_personnel_cert(
    personnel_id: str,
    cert_type_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    person = _find_person(personnel_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    catalog = _find_cert_type(cert_type_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Cert type not found")

    now = _utcnow()
    existing_rows = _embedded_certs_for_person(person)
    new_record = _normalize_person_cert({
        **body,
        "cert_type_id": cert_type_id,
        "code": catalog.get("code"),
        "name": catalog.get("name"),
        "category": catalog.get("category"),
        "issuing_org": catalog.get("issuing_org"),
        "parent_id": catalog.get("parent_id"),
        "tags": catalog.get("tags") or [],
        "updated_at": now,
    })

    key = _cert_key(new_record)
    updated_rows = [row for row in existing_rows if _cert_key(row) != key]
    updated_rows.append(new_record)
    updated_rows.sort(key=lambda c: (str(c.get("category") or ""), str(c.get("code") or "")))

    _personnel_col().update_one(
        {"_id": person["_id"]},
        {"$set": {"certifications": updated_rows, "updated_at": now}},
    )
    return new_record


@router.delete("/personnel/{personnel_id}/{cert_type_id}", status_code=204)
def delete_personnel_cert(personnel_id: str, cert_type_id: int) -> None:
    person = _find_person(personnel_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    existing_rows = _embedded_certs_for_person(person)
    updated_rows = [row for row in existing_rows if int(row.get("cert_type_id") or -1) != int(cert_type_id)]
    if len(updated_rows) == len(existing_rows):
        raise HTTPException(status_code=404, detail="Cert assignment not found")

    _personnel_col().update_one(
        {"_id": person["_id"]},
        {"$set": {"certifications": updated_rows, "updated_at": _utcnow()}},
    )
