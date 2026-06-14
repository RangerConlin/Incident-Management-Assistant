"""Master certification types and personnel cert assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()


def _cert_types_col():
    return get_client()[DB_MASTER][MasterCollections.CERTIFICATION_TYPES]


def _cert_tags_col():
    return get_client()[DB_MASTER][MasterCollections.CERTIFICATION_TAGS]


def _personnel_certs_col():
    return get_client()[DB_MASTER][MasterCollections.PERSONNEL_CERTIFICATIONS]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Certification Types (read-only catalog)
# ---------------------------------------------------------------------------

@router.get("/types")
def list_cert_types(search: str = "") -> list[dict[str, Any]]:
    col = _cert_types_col()
    query = {} if not search else {
        "$or": [
            {"code": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("category", 1).sort("code", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.get("/types/{cert_type_id}")
def get_cert_type(cert_type_id: int) -> dict[str, Any]:
    doc = _cert_types_col().find_one({"int_id": cert_type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Cert type not found")
    doc.pop("_id", None)
    return doc


@router.get("/types/{cert_type_id}/tags")
def get_cert_tags(cert_type_id: int) -> list[str]:
    col = _cert_tags_col()
    docs = col.find({"cert_type_id": cert_type_id})
    return [d.get("tag") for d in docs if d.get("tag")]


# ---------------------------------------------------------------------------
# Personnel Certifications (assignments per person)
# ---------------------------------------------------------------------------

@router.get("/personnel/{personnel_id}")
def list_personnel_certs(personnel_id: str) -> list[dict[str, Any]]:
    col = _personnel_certs_col()
    docs = list(col.find({"personnel_id": personnel_id}).sort("category", 1))
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

    col = _personnel_certs_col()
    doc = {
        "personnel_id": personnel_id,
        "cert_type_id": cert_type_id,
        "level": level,
        "attachment_url": attachment_url,
        "updated_at": _utcnow(),
    }
    col.update_one(
        {"personnel_id": personnel_id, "cert_type_id": cert_type_id},
        {"$set": doc},
        upsert=True,
    )
    return doc


@router.delete("/personnel/{personnel_id}/{cert_type_id}", status_code=204)
def delete_personnel_cert(personnel_id: str, cert_type_id: int) -> None:
    result = _personnel_certs_col().delete_one({
        "personnel_id": personnel_id,
        "cert_type_id": cert_type_id,
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cert assignment not found")
