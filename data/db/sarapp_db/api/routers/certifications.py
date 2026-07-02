"""Embedded personnel certification assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class LegacyPersonnelCertificationsRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL_CERTIFICATIONS
    soft_deletes = False


def _legacy_personnel_certs_repo() -> LegacyPersonnelCertificationsRepository:
    return LegacyPersonnelCertificationsRepository(get_master_db())


def _personnel_col():
    return get_master_db()[MasterCollections.PERSONNEL]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _find_person(person_record: str) -> dict[str, Any] | None:
    col = _personnel_col()
    if str(person_record).isdigit():
        return col.find_one({"person_record": int(person_record)})
    return None


def _minimal_person_cert(raw: dict[str, Any]) -> dict[str, int] | None:
    src = dict(raw or {})
    cert_type_id = src.get("cert_type_id") or src.get("int_id") or src.get("id")
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


@router.get("/personnel/{person_record}")
def list_personnel_certs(person_record: str) -> list[dict[str, Any]]:
    person = _find_person(person_record)
    if not person:
        return []
    rows = _person_cert_rows(person)
    if not rows:
        rows = _legacy_rows(str(person.get("person_record") or person_record))
        if rows:
            _personnel_col().update_one(
                {"_id": person["_id"]},
                {"$set": {"certifications": rows, "updated_at": _utcnow()}},
            )
    return sorted(rows, key=lambda r: r["cert_type_id"])


@router.post("/personnel/{person_record}/{cert_type_id}", status_code=201)
def set_personnel_cert(person_record: str, cert_type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    person = _find_person(person_record)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    row = _minimal_person_cert({"cert_type_id": cert_type_id, "level": body.get("level", 0)})
    if not row:
        raise HTTPException(status_code=422, detail="Invalid certification data")
    rows = [r for r in _person_cert_rows(person) if r["cert_type_id"] != int(cert_type_id)]
    rows.append(row)
    rows.sort(key=lambda r: r["cert_type_id"])
    _personnel_col().update_one(
        {"_id": person["_id"]},
        {"$set": {"certifications": rows, "updated_at": _utcnow()}},
    )
    return row


@router.delete("/personnel/{person_record}/{cert_type_id}", status_code=204)
def delete_personnel_cert(person_record: str, cert_type_id: int) -> None:
    person = _find_person(person_record)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    rows = _person_cert_rows(person)
    updated_rows = [r for r in rows if r["cert_type_id"] != int(cert_type_id)]
    if len(updated_rows) == len(rows):
        raise HTTPException(status_code=404, detail="Cert assignment not found")
    _personnel_col().update_one(
        {"_id": person["_id"]},
        {"$set": {"certifications": updated_rows, "updated_at": _utcnow()}},
    )
