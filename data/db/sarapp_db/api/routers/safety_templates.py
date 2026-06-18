"""FastAPI router for Safety Analysis Templates master data."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException
from pymongo.database import Database

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_col(db: Optional[Database] = None):
    _db = db if db is not None else get_master_db()
    return _db[MasterCollections.SAFETY_ANALYSIS_TEMPLATES]


def _next_id(col) -> int:
    last = col.find_one({}, sort=[("template_id", -1)], projection={"template_id": 1})
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
    col = _get_col()
    query: dict[str, Any] = {}
    if not include_inactive:
        query["is_active"] = True
    if scenario_type and scenario_type not in ("All", ""):
        query["scenario_type"] = scenario_type
    docs = [_clean_doc(d) for d in col.find(query)]
    if search_text:
        s = search_text.lower()
        docs = [
            d for d in docs
            if s in d.get("name", "").lower() or s in d.get("description", "").lower()
        ]
    docs.sort(key=lambda d: d.get("name", "").lower())
    return docs


@router.get("/{template_id}")
def get_template(template_id: int) -> dict[str, Any]:
    col = _get_col()
    doc = col.find_one({"template_id": template_id})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return _clean_doc(doc)


@router.post("")
def create_template(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _get_col()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    tid = _next_id(col)
    now = _utcnow()
    doc = {
        "_id": str(uuid.uuid4()),
        "template_id": tid,
        "name": name,
        "description": body.get("description", ""),
        "scenario_type": body.get("scenario_type", "General"),
        "target_forms": list(body.get("target_forms") or []),
        "hazard_entries": list(body.get("hazard_entries") or []),
        "is_active": bool(body.get("is_active", True)),
        "notes": body.get("notes", ""),
        "created_at": now,
        "updated_at": now,
        "created_by": body.get("created_by", ""),
        "updated_by": body.get("updated_by", ""),
    }
    col.insert_one(doc)
    return {"template_id": tid}


@router.put("/{template_id}")
def update_template(template_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _get_col()
    if col.find_one({"template_id": template_id}) is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    col.update_one(
        {"template_id": template_id},
        {"$set": {
            "name": name,
            "description": body.get("description", ""),
            "scenario_type": body.get("scenario_type", "General"),
            "target_forms": list(body.get("target_forms") or []),
            "hazard_entries": list(body.get("hazard_entries") or []),
            "is_active": bool(body.get("is_active", True)),
            "notes": body.get("notes", ""),
            "updated_at": _utcnow(),
            "updated_by": body.get("updated_by", ""),
        }},
    )
    return {"template_id": template_id}


@router.delete("/{template_id}")
def delete_template(template_id: int) -> dict[str, Any]:
    col = _get_col()
    result = col.delete_one({"template_id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return {"deleted": True}


@router.post("/{template_id}/clone")
def clone_template(template_id: int) -> dict[str, Any]:
    col = _get_col()
    doc = col.find_one({"template_id": template_id})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    now = _utcnow()
    new_id = _next_id(col)
    new_doc = {**doc}
    new_doc["_id"] = str(uuid.uuid4())
    new_doc["template_id"] = new_id
    new_doc["name"] = doc["name"] + " (Copy)"
    new_doc["created_at"] = now
    new_doc["updated_at"] = now
    col.insert_one(new_doc)
    return {"template_id": new_id}


@router.patch("/{template_id}/active")
def set_active(template_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _get_col()
    if col.find_one({"template_id": template_id}) is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    col.update_one(
        {"template_id": template_id},
        {"$set": {"is_active": bool(body.get("active", True)), "updated_at": _utcnow()}},
    )
    return {"template_id": template_id}
