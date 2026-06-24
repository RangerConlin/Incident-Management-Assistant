"""FastAPI router for Safety Analysis Templates master data."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class SafetyAnalysisTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.SAFETY_ANALYSIS_TEMPLATES
    # Keyed by `template_id`, not `_id`; no `deleted` field — is_active is a
    # separate, user-facing flag, not a soft-delete marker.
    soft_deletes = False


def _repo() -> SafetyAnalysisTemplatesRepository:
    return SafetyAnalysisTemplatesRepository(get_master_db())


def _next_id(repo: SafetyAnalysisTemplatesRepository) -> int:
    docs = repo.find_many({}, sort=[("template_id", -1)], limit=1)
    last = docs[0] if docs else None
    return (last["template_id"] + 1) if last and last.get("template_id") else 1


def _clean_doc(doc: dict[str, Any]) -> dict[str, Any]:
    doc.pop("_id", None)
    return doc


@router.get("")
def list_templates(
    search_text: Optional[str] = None,
    scenario_type: Optional[str] = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    repo = _repo()
    query: dict[str, Any] = {}
    if not include_inactive:
        query["is_active"] = True
    if scenario_type and scenario_type not in ("All", ""):
        query["scenario_type"] = scenario_type
    docs = [_clean_doc(d) for d in repo.find_many(query)]
    if search_text:
        s = search_text.lower()
        docs = [
            d for d in docs
            if s in (d.get("name") or "").lower() or s in (d.get("description") or "").lower()
        ]
    docs.sort(key=lambda d: (d.get("name") or "").lower())
    return docs


@router.get("/{template_id}")
def get_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    doc = repo.find_one({"template_id": template_id})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return _clean_doc(doc)


@router.post("")
def create_template(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    tid = _next_id(repo)
    doc = {
        "template_id": tid,
        "name": name,
        "description": body.get("description", ""),
        "scenario_type": body.get("scenario_type", "General"),
        "target_forms": list(body.get("target_forms") or []),
        "hazard_entries": list(body.get("hazard_entries") or []),
        "is_active": bool(body.get("is_active", True)),
        "notes": body.get("notes", ""),
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }
    repo.insert_one(doc)
    return {"template_id": tid}


@router.put("/{template_id}")
def update_template(template_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"template_id": template_id})
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    repo.update_one(existing["_id"], {
        "name": name,
        "description": body.get("description", ""),
        "scenario_type": body.get("scenario_type", "General"),
        "target_forms": list(body.get("target_forms") or []),
        "hazard_entries": list(body.get("hazard_entries") or []),
        "is_active": bool(body.get("is_active", True)),
        "notes": body.get("notes", ""),
        "updated_by": body.get("updated_by", ""),
    })
    return {"template_id": template_id}


@router.delete("/{template_id}")
def delete_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"template_id": template_id})
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    repo.delete_one(existing["_id"])
    return {"deleted": True}


@router.post("/{template_id}/clone")
def clone_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    doc = repo.find_one({"template_id": template_id})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    new_id = _next_id(repo)
    new_doc = {k: v for k, v in doc.items() if k not in ("_id", "created_at", "updated_at")}
    new_doc["template_id"] = new_id
    new_doc["name"] = doc["name"] + " (Copy)"
    repo.insert_one(new_doc)
    return {"template_id": new_id}


@router.patch("/{template_id}/active")
def set_active(template_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"template_id": template_id})
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    repo.update_one(existing["_id"], {"is_active": bool(body.get("active", True))})
    return {"template_id": template_id}
