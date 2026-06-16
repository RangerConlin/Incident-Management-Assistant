"""Master organization types, rank structures, organizations, and ranks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()


def _org_types_col():
    return get_client()[DB_MASTER][MasterCollections.ORGANIZATION_TYPES]


def _rank_structures_col():
    return get_client()[DB_MASTER][MasterCollections.RANK_STRUCTURES]


def _organizations_col():
    return get_client()[DB_MASTER][MasterCollections.ORGANIZATIONS]


def _ranks_col():
    return get_client()[DB_MASTER][MasterCollections.RANKS]


def _overrides_col():
    return get_client()[DB_MASTER][MasterCollections.ORGANIZATION_RANK_STRUCTURE_OVERRIDES]


def _org_audit_col():
    return get_client()[DB_MASTER][MasterCollections.ORGANIZATION_AUDIT_LOG]


def _rank_audit_col():
    return get_client()[DB_MASTER][MasterCollections.RANK_STRUCTURE_AUDIT_LOG]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _next_int_id(col) -> int:
    doc = list(col.find().sort("int_id", -1).limit(1))
    return (doc[0].get("int_id", 0) if doc else 0) + 1


# ---------------------------------------------------------------------------
# Organization Types
# ---------------------------------------------------------------------------

@router.get("/types")
def list_org_types(search: str = "") -> list[dict[str, Any]]:
    col = _org_types_col()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/types", status_code=201)
def create_org_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _org_types_col()
    doc = {
        "int_id": _next_int_id(col),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/types/{type_id}")
def get_org_type(type_id: int) -> dict[str, Any]:
    doc = _org_types_col().find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    doc.pop("_id", None)
    return doc


@router.patch("/types/{type_id}")
def update_org_type(type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _org_types_col()
    updates = {}
    if "name" in body:
        updates["name"] = body["name"]
    if "description" in body:
        updates["description"] = body["description"]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = col.update_one({"int_id": type_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Organization type not found")
    doc = col.find_one({"int_id": type_id})
    doc.pop("_id", None)
    return doc


@router.delete("/types/{type_id}", status_code=204)
def delete_org_type(type_id: int) -> None:
    result = _org_types_col().delete_one({"int_id": type_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Organization type not found")


# ---------------------------------------------------------------------------
# Rank Structures
# ---------------------------------------------------------------------------

@router.get("/rank-structures")
def list_rank_structures(search: str = "") -> list[dict[str, Any]]:
    col = _rank_structures_col()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/rank-structures", status_code=201)
def create_rank_structure(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _rank_structures_col()
    doc = {
        "int_id": _next_int_id(col),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    doc.pop("_id", None)
    return doc


@router.get("/rank-structures/{structure_id}")
def get_rank_structure(structure_id: int) -> dict[str, Any]:
    doc = _rank_structures_col().find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    doc.pop("_id", None)
    return doc


@router.patch("/rank-structures/{structure_id}")
def update_rank_structure(
    structure_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    col = _rank_structures_col()
    updates = {}
    if "name" in body:
        updates["name"] = body["name"]
    if "description" in body:
        updates["description"] = body["description"]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = col.update_one({"int_id": structure_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": structure_id,
        "action": "update",
        "timestamp": _utcnow(),
    })
    doc = col.find_one({"int_id": structure_id})
    doc.pop("_id", None)
    return doc


@router.delete("/rank-structures/{structure_id}", status_code=204)
def delete_rank_structure(structure_id: int) -> None:
    result = _rank_structures_col().delete_one({"int_id": structure_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": structure_id,
        "action": "delete",
        "timestamp": _utcnow(),
    })


@router.post("/rank-structures/{structure_id}/duplicate")
def duplicate_rank_structure(structure_id: int) -> dict[str, Any]:
    col = _rank_structures_col()
    src = col.find_one({"int_id": structure_id})
    if not src:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    new_doc = {
        "int_id": _next_int_id(col),
        "name": f"{src.get('name')} (Copy)",
        "description": src.get("description"),
        "created_at": _utcnow(),
    }
    col.insert_one(new_doc)
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": new_doc["int_id"],
        "action": "duplicate",
        "source_id": structure_id,
        "timestamp": _utcnow(),
    })
    new_doc.pop("_id", None)
    return new_doc


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

@router.get("/organizations")
def list_organizations(search: str = "") -> list[dict[str, Any]]:
    col = _organizations_col()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"call_sign": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/organizations", status_code=201)
def create_organization(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _organizations_col()
    doc = {
        "int_id": _next_int_id(col),
        "name": body.get("name", ""),
        "call_sign": body.get("call_sign"),
        "org_type_id": body.get("org_type_id"),
        "parent_id": body.get("parent_id"),
        "rank_structure_id": body.get("rank_structure_id"),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    _org_audit_col().insert_one({
        "_id": _new_id(),
        "organization_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    doc.pop("_id", None)
    return doc


@router.get("/organizations/{org_id}")
def get_organization(org_id: int) -> dict[str, Any]:
    doc = _organizations_col().find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    doc.pop("_id", None)
    return doc


@router.patch("/organizations/{org_id}")
def update_organization(org_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _organizations_col()
    updates = {}
    for field in ("name", "call_sign", "org_type_id", "parent_id", "rank_structure_id"):
        if field in body:
            updates[field] = body[field]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = col.update_one({"int_id": org_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    _org_audit_col().insert_one({
        "_id": _new_id(),
        "organization_id": org_id,
        "action": "update",
        "timestamp": _utcnow(),
    })
    doc = col.find_one({"int_id": org_id})
    doc.pop("_id", None)
    return doc


@router.delete("/organizations/{org_id}", status_code=204)
def delete_organization(org_id: int) -> None:
    result = _organizations_col().delete_one({"int_id": org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
    _org_audit_col().insert_one({
        "_id": _new_id(),
        "organization_id": org_id,
        "action": "delete",
        "timestamp": _utcnow(),
    })


# ---------------------------------------------------------------------------
# Ranks
# ---------------------------------------------------------------------------

@router.get("/ranks")
def list_ranks(
    structure_id: int | None = Query(None),
    search: str = "",
) -> list[dict[str, Any]]:
    col = _ranks_col()
    query = {}
    if structure_id:
        query["rank_structure_id"] = structure_id
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"abbreviation": {"$regex": search, "$options": "i"}},
        ]
    docs = list(col.find(query).sort("rank_order", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/ranks", status_code=201)
def create_rank(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _ranks_col()
    doc = {
        "int_id": _next_int_id(col),
        "rank_structure_id": body.get("rank_structure_id"),
        "name": body.get("name", ""),
        "abbreviation": body.get("abbreviation"),
        "rank_order": body.get("rank_order", 0),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/ranks/{rank_id}")
def get_rank(rank_id: int) -> dict[str, Any]:
    doc = _ranks_col().find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    doc.pop("_id", None)
    return doc


@router.patch("/ranks/{rank_id}")
def update_rank(rank_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _ranks_col()
    updates = {}
    for field in ("name", "abbreviation", "rank_order"):
        if field in body:
            updates[field] = body[field]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = col.update_one({"int_id": rank_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rank not found")
    doc = col.find_one({"int_id": rank_id})
    doc.pop("_id", None)
    return doc


@router.delete("/ranks/{rank_id}", status_code=204)
def delete_rank(rank_id: int) -> None:
    result = _ranks_col().delete_one({"int_id": rank_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rank not found")


# ---------------------------------------------------------------------------
# Organization Rank Structure Overrides
# ---------------------------------------------------------------------------

@router.get("/organizations/{org_id}/rank-structure-override")
def get_rank_structure_override(org_id: int) -> dict[str, Any] | None:
    doc = _overrides_col().find_one({"organization_id": org_id})
    if doc:
        doc.pop("_id", None)
    return doc


@router.post("/organizations/{org_id}/rank-structure-override")
def set_rank_structure_override(
    org_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    col = _overrides_col()
    doc = {
        "organization_id": org_id,
        "rank_structure_id": body.get("rank_structure_id"),
        "created_at": _utcnow(),
    }
    col.update_one({"organization_id": org_id}, {"$set": doc}, upsert=True)
    return doc


@router.delete("/organizations/{org_id}/rank-structure-override", status_code=204)
def delete_rank_structure_override(org_id: int) -> None:
    result = _overrides_col().delete_one({"organization_id": org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Override not found")
