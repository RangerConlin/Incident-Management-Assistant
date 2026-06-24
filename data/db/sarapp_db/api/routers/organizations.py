"""Master organization types, rank structures, organizations, and ranks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


# ---------------------------------------------------------------------------
# Repositories
#
# All collections here are keyed by a sequential `int_id` (not `_id`), and
# none carry a `deleted` field — they are hard-deleted. soft_deletes is
# disabled so BaseRepository's find/count methods don't inject a
# `deleted: False` filter that would hide these docs.
# ---------------------------------------------------------------------------

class OrganizationTypesRepository(BaseRepository):
    collection_name = MasterCollections.ORGANIZATION_TYPES
    soft_deletes = False


class RankStructuresRepository(BaseRepository):
    collection_name = MasterCollections.RANK_STRUCTURES
    soft_deletes = False


class OrganizationsRepository(BaseRepository):
    collection_name = MasterCollections.ORGANIZATIONS
    soft_deletes = False


class RanksRepository(BaseRepository):
    collection_name = MasterCollections.RANKS
    soft_deletes = False


class OrganizationRankStructureOverridesRepository(BaseRepository):
    collection_name = MasterCollections.ORGANIZATION_RANK_STRUCTURE_OVERRIDES
    soft_deletes = False


class OrganizationAuditLogRepository(BaseRepository):
    collection_name = MasterCollections.ORGANIZATION_AUDIT_LOG
    soft_deletes = False


class RankStructureAuditLogRepository(BaseRepository):
    collection_name = MasterCollections.RANK_STRUCTURE_AUDIT_LOG
    soft_deletes = False


def _org_types_repo() -> OrganizationTypesRepository:
    return OrganizationTypesRepository(get_master_db())


def _rank_structures_repo() -> RankStructuresRepository:
    return RankStructuresRepository(get_master_db())


def _organizations_repo() -> OrganizationsRepository:
    return OrganizationsRepository(get_master_db())


def _ranks_repo() -> RanksRepository:
    return RanksRepository(get_master_db())


def _overrides_repo() -> OrganizationRankStructureOverridesRepository:
    return OrganizationRankStructureOverridesRepository(get_master_db())


def _org_audit_repo() -> OrganizationAuditLogRepository:
    return OrganizationAuditLogRepository(get_master_db())


def _rank_audit_repo() -> RankStructureAuditLogRepository:
    return RankStructureAuditLogRepository(get_master_db())


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_int_id(repo: BaseRepository) -> int:
    docs = repo.find_many({}, sort=[("int_id", -1)], limit=1)
    return (docs[0].get("int_id", 0) if docs else 0) + 1


# ---------------------------------------------------------------------------
# Organization Types
# ---------------------------------------------------------------------------

@router.get("/types")
def list_org_types(search: str = "") -> list[dict[str, Any]]:
    repo = _org_types_repo()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = repo.find_many(query, sort=[("name", 1)])
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/types", status_code=201)
def create_org_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _org_types_repo()
    doc = {
        "int_id": _next_int_id(repo),
        "name": body.get("name", ""),
        "description": body.get("description"),
    }
    doc = repo.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/types/{type_id}")
def get_org_type(type_id: int) -> dict[str, Any]:
    doc = _org_types_repo().find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    doc.pop("_id", None)
    return doc


@router.patch("/types/{type_id}")
def update_org_type(type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _org_types_repo()
    updates = {}
    if "name" in body:
        updates["name"] = body["name"]
    if "description" in body:
        updates["description"] = body["description"]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    repo.update_one(doc["_id"], updates)
    result = repo.find_by_id(doc["_id"])
    result.pop("_id", None)
    return result


@router.delete("/types/{type_id}", status_code=204)
def delete_org_type(type_id: int) -> None:
    repo = _org_types_repo()
    doc = repo.find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    repo.delete_one(doc["_id"])


# ---------------------------------------------------------------------------
# Rank Structures
# ---------------------------------------------------------------------------

@router.get("/rank-structures")
def list_rank_structures(search: str = "") -> list[dict[str, Any]]:
    repo = _rank_structures_repo()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = repo.find_many(query, sort=[("name", 1)])
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/rank-structures", status_code=201)
def create_rank_structure(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _rank_structures_repo()
    doc = {
        "int_id": _next_int_id(repo),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "organization_type_id": body.get("organization_type_id"),
        "is_system_template": bool(body.get("is_system_template", False)),
    }
    doc = repo.insert_one(doc)
    audit_repo = _rank_audit_repo()
    audit_repo.insert_one({
        "rank_structure_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    doc.pop("_id", None)
    return doc


@router.get("/rank-structures/{structure_id}")
def get_rank_structure(structure_id: int) -> dict[str, Any]:
    doc = _rank_structures_repo().find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    doc.pop("_id", None)
    return doc


@router.patch("/rank-structures/{structure_id}")
def update_rank_structure(
    structure_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    repo = _rank_structures_repo()
    updates = {}
    if "name" in body:
        updates["name"] = body["name"]
    if "description" in body:
        updates["description"] = body["description"]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    repo.update_one(doc["_id"], updates)
    audit_repo = _rank_audit_repo()
    audit_repo.insert_one({
        "rank_structure_id": structure_id,
        "action": "update",
        "timestamp": _utcnow(),
    })
    result = repo.find_by_id(doc["_id"])
    result.pop("_id", None)
    return result


@router.delete("/rank-structures/{structure_id}", status_code=204)
def delete_rank_structure(structure_id: int) -> None:
    repo = _rank_structures_repo()
    doc = repo.find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    repo.delete_one(doc["_id"])
    audit_repo = _rank_audit_repo()
    audit_repo.insert_one({
        "rank_structure_id": structure_id,
        "action": "delete",
        "timestamp": _utcnow(),
    })


@router.post("/rank-structures/{structure_id}/duplicate")
def duplicate_rank_structure(structure_id: int) -> dict[str, Any]:
    repo = _rank_structures_repo()
    src = repo.find_one({"int_id": structure_id})
    if not src:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    new_doc = {
        "int_id": _next_int_id(repo),
        "name": f"{src.get('name')} (Copy)",
        "description": src.get("description"),
    }
    new_doc = repo.insert_one(new_doc)
    audit_repo = _rank_audit_repo()
    audit_repo.insert_one({
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
    repo = _organizations_repo()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"call_sign": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = repo.find_many(query, sort=[("name", 1)])
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/organizations", status_code=201)
def create_organization(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _organizations_repo()
    doc = {
        "int_id": _next_int_id(repo),
        "name": body.get("name", ""),
        "call_sign": body.get("call_sign"),
        "org_type_id": body.get("org_type_id"),
        "parent_id": body.get("parent_id"),
        "rank_structure_id": body.get("rank_structure_id"),
    }
    doc = repo.insert_one(doc)
    audit_repo = _org_audit_repo()
    audit_repo.insert_one({
        "organization_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    doc.pop("_id", None)
    return doc


@router.get("/organizations/{org_id}")
def get_organization(org_id: int) -> dict[str, Any]:
    doc = _organizations_repo().find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    doc.pop("_id", None)
    return doc


@router.patch("/organizations/{org_id}")
def update_organization(org_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _organizations_repo()
    updates = {}
    for field in ("name", "call_sign", "org_type_id", "parent_id", "rank_structure_id"):
        if field in body:
            updates[field] = body[field]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    repo.update_one(doc["_id"], updates)
    audit_repo = _org_audit_repo()
    audit_repo.insert_one({
        "organization_id": org_id,
        "action": "update",
        "timestamp": _utcnow(),
    })
    result = repo.find_by_id(doc["_id"])
    result.pop("_id", None)
    return result


@router.delete("/organizations/{org_id}", status_code=204)
def delete_organization(org_id: int) -> None:
    repo = _organizations_repo()
    doc = repo.find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    repo.delete_one(doc["_id"])
    audit_repo = _org_audit_repo()
    audit_repo.insert_one({
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
    repo = _ranks_repo()
    query = {}
    if structure_id:
        query["rank_structure_id"] = structure_id
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"abbreviation": {"$regex": search, "$options": "i"}},
        ]
    docs = repo.find_many(query, sort=[("rank_order", 1)])
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/ranks", status_code=201)
def create_rank(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ranks_repo()
    doc = {
        "int_id": _next_int_id(repo),
        "rank_structure_id": body.get("rank_structure_id"),
        "name": body.get("name", ""),
        "abbreviation": body.get("abbreviation"),
        "rank_order": body.get("rank_order", 0),
    }
    doc = repo.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/ranks/{rank_id}")
def get_rank(rank_id: int) -> dict[str, Any]:
    doc = _ranks_repo().find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    doc.pop("_id", None)
    return doc


@router.patch("/ranks/{rank_id}")
def update_rank(rank_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ranks_repo()
    updates = {}
    for field in ("name", "abbreviation", "rank_order"):
        if field in body:
            updates[field] = body[field]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    repo.update_one(doc["_id"], updates)
    result = repo.find_by_id(doc["_id"])
    result.pop("_id", None)
    return result


@router.delete("/ranks/{rank_id}", status_code=204)
def delete_rank(rank_id: int) -> None:
    repo = _ranks_repo()
    doc = repo.find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    repo.delete_one(doc["_id"])


# ---------------------------------------------------------------------------
# Organization Rank Structure Overrides
# ---------------------------------------------------------------------------

@router.get("/organizations/{org_id}/rank-structure-override")
def get_rank_structure_override(org_id: int) -> dict[str, Any] | None:
    doc = _overrides_repo().find_one({"organization_id": org_id})
    if doc:
        doc.pop("_id", None)
    return doc


@router.post("/organizations/{org_id}/rank-structure-override")
def set_rank_structure_override(
    org_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    repo = _overrides_repo()
    existing = repo.find_one({"organization_id": org_id})
    payload = {
        "organization_id": org_id,
        "rank_structure_id": body.get("rank_structure_id"),
    }
    if existing:
        repo.update_one(existing["_id"], payload)
        result = repo.find_by_id(existing["_id"])
    else:
        result = repo.insert_one(payload)
    result.pop("_id", None)
    return result


@router.delete("/organizations/{org_id}/rank-structure-override", status_code=204)
def delete_rank_structure_override(org_id: int) -> None:
    repo = _overrides_repo()
    doc = repo.find_one({"organization_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Override not found")
    repo.delete_one(doc["_id"])
