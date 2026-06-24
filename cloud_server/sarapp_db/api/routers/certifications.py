"""Master certification types and personnel cert assignments."""

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


class PersonnelCertificationsRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL_CERTIFICATIONS
    soft_deletes = False


def _cert_types_repo() -> CertificationTypesRepository:
    return CertificationTypesRepository(get_master_db())


def _cert_tags_repo() -> CertificationTagsRepository:
    return CertificationTagsRepository(get_master_db())


def _personnel_certs_repo() -> PersonnelCertificationsRepository:
    return PersonnelCertificationsRepository(get_master_db())


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Certification Types (read-only catalog)
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
    for d in docs:
        d.pop("_id", None)
    return docs


@router.get("/types/{cert_type_id}")
def get_cert_type(cert_type_id: int) -> dict[str, Any]:
    doc = _cert_types_repo().find_one({"int_id": cert_type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Cert type not found")
    doc.pop("_id", None)
    return doc


@router.post("/types", status_code=201)
def upsert_cert_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _cert_types_repo()
    cert_id = body.get("cert_type_id") or body.get("id")
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
    if tags:
        tags_repo = _cert_tags_repo()
        tags_repo.delete_many({"cert_type_id": cert_id})
        for tag in tags:
            tags_repo.insert_one({"cert_type_id": cert_id, "tag": tag})
    return {"id": cert_id}


@router.put("/types/{cert_type_id}")
def update_cert_type(cert_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    body["cert_type_id"] = cert_type_id
    return upsert_cert_type(body)


@router.get("/types/{cert_type_id}/tags")
def get_cert_tags(cert_type_id: int) -> list[str]:
    repo = _cert_tags_repo()
    docs = repo.find_many({"cert_type_id": cert_type_id})
    return [d.get("tag") for d in docs if d.get("tag")]


# ---------------------------------------------------------------------------
# Personnel Certifications (assignments per person)
# ---------------------------------------------------------------------------

@router.get("/personnel/{personnel_id}")
def list_personnel_certs(personnel_id: str) -> list[dict[str, Any]]:
    repo = _personnel_certs_repo()
    docs = repo.find_many({"personnel_id": personnel_id}, sort=[("category", 1)])
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/personnel/{personnel_id}/{cert_type_id}", status_code=201)
def set_personnel_cert(
    personnel_id: str,
    cert_type_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    level = min(3, max(0, int(body.get("level", 0))))
    attachment_url = body.get("attachment_url")

    repo = _personnel_certs_repo()
    fields = {
        "personnel_id": personnel_id,
        "cert_type_id": cert_type_id,
        "level": level,
        "attachment_url": attachment_url,
    }
    existing = repo.find_one({"personnel_id": personnel_id, "cert_type_id": cert_type_id})
    if existing:
        repo.update_one(existing["_id"], fields)
        doc = repo.find_by_id(existing["_id"])
    else:
        doc = repo.insert_one(fields)
    doc.pop("_id", None)
    return doc


@router.delete("/personnel/{personnel_id}/{cert_type_id}", status_code=204)
def delete_personnel_cert(personnel_id: str, cert_type_id: int) -> None:
    repo = _personnel_certs_repo()
    existing = repo.find_one({"personnel_id": personnel_id, "cert_type_id": cert_type_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Cert assignment not found")
    repo.delete_one(existing["_id"])
