"""Master resource type library API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()


def _col():
    return get_client()[DB_MASTER][MasterCollections.RESOURCE_TYPES]


def _cap_col():
    return get_client()[DB_MASTER][MasterCollections.RESOURCE_CAPABILITIES]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _next_int_id(col, id_field: str) -> int:
    candidates = [
        int(d[id_field])
        for d in col.find({id_field: {"$regex": r"^\d+$"}}, {id_field: 1})
        if d.get(id_field, "").isdigit()
    ]
    return max(candidates, default=0) + 1


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    """Add computed fields the UI expects."""
    d = dict(doc)
    rt_id_str = d.get("resource_type_id", "")
    d["id"] = int(rt_id_str) if rt_id_str.isdigit() else None
    capability_names = d.get("capability_names") or []
    d["capabilities"] = ", ".join(capability_names)
    d["component_count"] = len(d.get("components") or [])
    return d


def _search_matches(doc: dict[str, Any], text: str) -> str | None:
    t = text.lower()
    for field, label in (
        ("name", "name"),
        ("planning_display_name", "display name"),
        ("category", "category"),
        ("source", "source"),
        ("owner_agency", "agency"),
        ("description", "description"),
        ("notes", "notes"),
    ):
        if t in (doc.get(field) or "").lower():
            return label
    for alias in doc.get("aliases") or []:
        if t in (alias or "").lower():
            return "alias"
    for cap in doc.get("capability_names") or []:
        if t in (cap or "").lower():
            return "capability"
    for m in doc.get("fema_mappings") or []:
        if t in (m.get("nims_name") or "").lower() or t in (m.get("type_code") or "").lower():
            return "FEMA/NIMS"
    return None


# ------------------------------------------------------------------
# List

@router.get("")
def list_resource_types(
    search_text: str = Query(""),
    category: str = Query("All"),
    source: str = Query("All"),
    active_filter: str = Query("Active"),
    include_inactive: bool = Query(False),
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if active_filter == "Active" and not include_inactive:
        query["is_active"] = True
    elif active_filter == "Inactive":
        query["is_active"] = False
    if category and category != "All":
        query["category"] = category
    if source and source != "All":
        query["source"] = source

    docs = list(_col().find(query).sort("name", 1))

    if search_text.strip():
        t = search_text.strip().lower()
        docs = [d for d in docs if _search_matches(d, t)]

    return [_normalize(d) for d in docs]


# ------------------------------------------------------------------
# Search

@router.get("/search")
def search_resource_types(
    q: str = Query(""),
    include_inactive: bool = Query(False),
    limit: int = Query(20),
) -> list[dict[str, Any]]:
    text = q.strip()
    if not text:
        return []
    base_query: dict[str, Any] = {} if include_inactive else {"is_active": True}
    docs = list(_col().find(base_query).sort("name", 1))
    results = []
    for doc in docs:
        matched_on = _search_matches(doc, text)
        if matched_on is not None:
            rt_id_str = doc.get("resource_type_id", "")
            results.append({
                "resource_type_id": int(rt_id_str) if rt_id_str.isdigit() else None,
                "resource_type_text": doc.get("planning_display_name") or doc.get("name", ""),
                "category": doc.get("category", ""),
                "source": doc.get("source", ""),
                "owner_agency": doc.get("owner_agency", ""),
                "matched_on": matched_on,
            })
        if len(results) >= limit:
            break
    return results


# ------------------------------------------------------------------
# Capabilities list (defined before /{resource_type_id} to avoid conflict)

@router.get("/capabilities")
def list_capabilities(
    include_inactive: bool = Query(False),
    category: str = Query("All"),
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {} if include_inactive else {"is_active": True}
    if category and category != "All":
        query["category"] = category
    docs = list(_cap_col().find(query).sort("name", 1))
    result = []
    for d in docs:
        cap_id_str = d.get("capability_id", "")
        result.append({
            **d,
            "id": int(cap_id_str) if cap_id_str.isdigit() else None,
        })
    return result


# ------------------------------------------------------------------
# Create

class SaveResourceTypeRequest(BaseModel):
    name: str
    planning_display_name: str = ""
    category: str = "Other"
    source: str = "AHJ Custom"
    owner_agency: str = ""
    description: str = ""
    default_unit: str = "each"
    typical_quantity: float = 1.0
    typical_team_size: int | None = None
    is_kit_cache: bool = False
    is_consumable: bool = False
    is_active: bool = True
    notes: str = ""
    created_by: str = ""
    updated_by: str = ""
    aliases: list[str] = []
    capability_ids: list[int] = []
    capability_names: list[str] = []
    components: list[dict[str, Any]] = []
    fema_mappings: list[dict[str, Any]] = []


@router.post("", status_code=201)
def create_resource_type(body: SaveResourceTypeRequest) -> dict[str, Any]:
    col = _col()
    new_int_id = _next_int_id(col, "resource_type_id")
    now = _utcnow()
    doc: dict[str, Any] = {
        "_id": _new_id(),
        "resource_type_id": str(new_int_id),
        **body.model_dump(exclude={"created_by"}),
        "created_by": body.created_by,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _normalize(doc)


# ------------------------------------------------------------------
# Get one

@router.get("/{resource_type_id}")
def get_resource_type(resource_type_id: str) -> dict[str, Any]:
    doc = _col().find_one({"resource_type_id": resource_type_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Resource type not found")
    return _normalize(doc)


# ------------------------------------------------------------------
# Full save

@router.put("/{resource_type_id}")
def save_resource_type(resource_type_id: str, body: SaveResourceTypeRequest) -> dict[str, Any]:
    col = _col()
    now = _utcnow()
    existing = col.find_one({"resource_type_id": resource_type_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Resource type not found")
    updates = {
        **body.model_dump(),
        "resource_type_id": resource_type_id,
        "_id": existing["_id"],
        "created_at": existing.get("created_at", now),
        "created_by": existing.get("created_by", ""),
        "updated_at": now,
    }
    col.replace_one({"resource_type_id": resource_type_id}, updates)
    return _normalize(updates)


# ------------------------------------------------------------------
# Replace components only

class ReplaceComponentsRequest(BaseModel):
    components: list[dict[str, Any]]


@router.patch("/{resource_type_id}/components")
def replace_components(resource_type_id: str, body: ReplaceComponentsRequest) -> dict[str, Any]:
    col = _col()
    result = col.update_one(
        {"resource_type_id": resource_type_id},
        {"$set": {"components": body.components, "updated_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Resource type not found")
    doc = col.find_one({"resource_type_id": resource_type_id})
    return _normalize(doc) if doc else {}


# ------------------------------------------------------------------
# Clone

@router.post("/{resource_type_id}/clone", status_code=201)
def clone_resource_type(resource_type_id: str) -> dict[str, Any]:
    col = _col()
    original = col.find_one({"resource_type_id": resource_type_id})
    if original is None:
        raise HTTPException(status_code=404, detail="Resource type not found")
    new_int_id = _next_int_id(col, "resource_type_id")
    now = _utcnow()
    base_name = original.get("name", "")
    copy_num = 1
    while col.find_one({"name": f"{base_name} Copy {copy_num}"}):
        copy_num += 1
    clone = dict(original)
    clone["_id"] = _new_id()
    clone["resource_type_id"] = str(new_int_id)
    clone["name"] = f"{base_name} Copy {copy_num}"
    pdn = original.get("planning_display_name", base_name)
    clone["planning_display_name"] = f"{pdn} Copy {copy_num}".strip()
    clone["created_at"] = now
    clone["updated_at"] = now
    clone["created_by"] = ""
    clone["updated_by"] = ""
    col.insert_one(clone)
    return _normalize(clone)


# ------------------------------------------------------------------
# Set active flag

class SetActiveRequest(BaseModel):
    active: bool


@router.patch("/{resource_type_id}/active")
def set_resource_type_active(resource_type_id: str, body: SetActiveRequest) -> dict[str, Any]:
    col = _col()
    result = col.update_one(
        {"resource_type_id": resource_type_id},
        {"$set": {"is_active": body.active, "updated_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Resource type not found")
    doc = col.find_one({"resource_type_id": resource_type_id})
    return _normalize(doc) if doc else {}


# ------------------------------------------------------------------
# Capability save

class SaveCapabilityRequest(BaseModel):
    name: str
    category: str = ""
    description: str = ""
    aliases: list[str] = []
    is_active: bool = True
    notes: str = ""
    capability_id: str | None = None


@router.post("/capabilities/save", status_code=201)
def save_capability(body: SaveCapabilityRequest) -> dict[str, Any]:
    col = _cap_col()
    now = _utcnow()
    if body.capability_id:
        existing = col.find_one({"capability_id": body.capability_id})
        if existing:
            updates = {**body.model_dump(exclude={"capability_id"}), "updated_at": now}
            col.update_one({"capability_id": body.capability_id}, {"$set": updates})
            doc = col.find_one({"capability_id": body.capability_id})
            cap_id_str = doc.get("capability_id", "")
            return {**doc, "id": int(cap_id_str) if cap_id_str.isdigit() else None}
    new_int_id = _next_int_id(col, "capability_id")
    doc = {
        "_id": _new_id(),
        "capability_id": str(new_int_id),
        "name": body.name,
        "category": body.category,
        "description": body.description,
        "aliases": body.aliases,
        "is_active": body.is_active,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return {**doc, "id": new_int_id}


# ------------------------------------------------------------------
# Set capability active flag

@router.patch("/capabilities/{capability_id}/active")
def set_capability_active(capability_id: str, body: SetActiveRequest) -> dict[str, Any]:
    col = _cap_col()
    result = col.update_one(
        {"capability_id": capability_id},
        {"$set": {"is_active": body.active, "updated_at": _utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Capability not found")
    doc = col.find_one({"capability_id": capability_id})
    cap_id_str = (doc or {}).get("capability_id", "")
    return {**(doc or {}), "id": int(cap_id_str) if cap_id_str.isdigit() else None}
