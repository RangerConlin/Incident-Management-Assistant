"""FastAPI router — IAP (Incident Action Plan) packages for an incident.

IAP packages are stored as documents in the ``iap_packages`` collection.
Each document carries an embedded ``forms`` array so a package and all its
forms are loaded in a single query.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class IAPPackagesRepository(BaseRepository):
    collection_name = IncidentCollections.IAP_PACKAGES
    soft_deletes = False


def _repo(incident_id: str) -> IAPPackagesRepository:
    return IAPPackagesRepository(get_incident_db(incident_id))


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _pkg_doc_to_dict(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    out.pop("updated_at", None)
    return out


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class FormModel(BaseModel):
    form_id: str
    title: str
    op_number: int
    revision: int = 0
    status: str = "draft"
    last_updated: Optional[str] = None
    fields: Optional[dict[str, Any]] = None
    attachments: Optional[list[str]] = None
    display_order: int = 0


class PackageUpsertRequest(BaseModel):
    incident_id: str
    op_start: str
    op_end: str
    created_at: Optional[str] = None
    status: str = "draft"
    notes: str = ""
    version_tag: Optional[str] = None
    published_pdf_path: Optional[str] = None


class FormOrderRequest(BaseModel):
    order: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_package(
    repo: IAPPackagesRepository,
    incident_id: str,
    op_number: int,
) -> Optional[dict[str, Any]]:
    return repo.find_one({"incident_id": incident_id, "op_number": op_number})


def _require_package(
    repo: IAPPackagesRepository,
    incident_id: str,
    op_number: int,
) -> dict[str, Any]:
    doc = _find_package(repo, incident_id, op_number)
    if doc is None:
        raise HTTPException(404, f"IAP package not found: incident={incident_id} op={op_number}")
    return doc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}/iap/packages")
def list_packages(incident_id: str) -> list[dict[str, Any]]:
    repo = _repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("op_number", 1)])
    return [_pkg_doc_to_dict(d) for d in docs]


@router.get("/incidents/{incident_id}/iap/packages/{op_number}")
def get_package(incident_id: str, op_number: int) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = _require_package(repo, incident_id, op_number)
    return _pkg_doc_to_dict(doc)


@router.put("/incidents/{incident_id}/iap/packages/{op_number}")
def upsert_package(
    incident_id: str, op_number: int, body: PackageUpsertRequest
) -> dict[str, Any]:
    repo = _repo(incident_id)
    existing = _find_package(repo, incident_id, op_number)
    updates = {
        "incident_id": incident_id,
        "op_number": op_number,
        "op_start": body.op_start,
        "op_end": body.op_end,
        "status": body.status,
        "notes": body.notes,
        "version_tag": body.version_tag,
        "published_pdf_path": body.published_pdf_path,
    }
    if existing:
        repo.update_one(existing["_id"], updates)
        doc = _find_package(repo, incident_id, op_number)
    else:
        doc = repo.insert_one({
            **updates,
            "created_at": body.created_at or _now_iso(),
            "forms": [],
        })
    return _pkg_doc_to_dict(doc)


@router.put("/incidents/{incident_id}/iap/packages/{op_number}/forms/{form_id}")
def upsert_form(
    incident_id: str, op_number: int, form_id: str, body: FormModel
) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = _require_package(repo, incident_id, op_number)

    new_form: dict[str, Any] = {
        "form_id": form_id,
        "title": body.title,
        "op_number": op_number,
        "revision": body.revision,
        "status": body.status,
        "last_updated": body.last_updated or _now_iso(),
        "fields": body.fields or {},
        "attachments": body.attachments or [],
        "display_order": body.display_order,
    }

    forms: list[dict[str, Any]] = list(doc.get("forms", []))
    idx = next((i for i, f in enumerate(forms) if f.get("form_id") == form_id), None)
    if idx is not None:
        forms[idx] = new_form
    else:
        forms.append(new_form)

    repo.update_one(doc["_id"], {"forms": forms})
    updated = _find_package(repo, incident_id, op_number)
    return _pkg_doc_to_dict(updated)


@router.delete(
    "/incidents/{incident_id}/iap/packages/{op_number}/forms/{form_id}",
    status_code=204,
)
def delete_form(incident_id: str, op_number: int, form_id: str) -> None:
    repo = _repo(incident_id)
    doc = _require_package(repo, incident_id, op_number)

    forms: list[dict[str, Any]] = [
        f for f in doc.get("forms", []) if f.get("form_id") != form_id
    ]
    # Re-index display_order after removal
    for i, f in enumerate(forms):
        f["display_order"] = i

    repo.update_one(doc["_id"], {"forms": forms})


@router.put("/incidents/{incident_id}/iap/packages/{op_number}/forms-order")
def update_forms_order(
    incident_id: str, op_number: int, body: FormOrderRequest
) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = _require_package(repo, incident_id, op_number)

    forms_by_id: dict[str, dict[str, Any]] = {
        f["form_id"]: f for f in doc.get("forms", [])
    }
    ordered: list[dict[str, Any]] = []
    for idx, fid in enumerate(body.order):
        if fid in forms_by_id:
            forms_by_id[fid]["display_order"] = idx
            ordered.append(forms_by_id[fid])
    # Append any forms not referenced in the order list at the end
    referenced = set(body.order)
    for fid, form in forms_by_id.items():
        if fid not in referenced:
            form["display_order"] = len(ordered)
            ordered.append(form)

    repo.update_one(doc["_id"], {"forms": ordered})
    updated = _find_package(repo, incident_id, op_number)
    return _pkg_doc_to_dict(updated)
