"""Master organization types, rank structures, organizations, and ranks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


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


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    payload = dict(doc)
    payload.pop("_id", None)
    payload["id"] = payload.get("int_id")
    return payload


def _effective_rank_structure_id(org_repo: OrganizationsRepository, doc: dict[str, Any]) -> int | None:
    seen: set[int] = set()
    current = doc
    while current is not None:
        explicit = current.get("default_rank_structure_id")
        if explicit is None:
            explicit = current.get("rank_structure_id")
        if explicit is not None:
            return explicit
        parent_id = current.get("parent_organization_id")
        if parent_id is None:
            parent_id = current.get("parent_id")
        if parent_id is None or parent_id in seen:
            return None
        seen.add(parent_id)
        current = org_repo.find_one({"int_id": parent_id})
    return None


def _enrich_rank_structure(doc: dict[str, Any]) -> dict[str, Any]:
    payload = _serialize(doc) or {}
    org_type_id = payload.get("organization_type_id")
    if org_type_id is not None:
        org_type = _org_types_repo().find_one({"int_id": org_type_id})
        payload["organization_type_name"] = org_type.get("name") if org_type else None
    else:
        payload["organization_type_name"] = None
    return payload


def _enrich_organization(doc: dict[str, Any]) -> dict[str, Any]:
    org_repo = _organizations_repo()
    payload = _serialize(doc) or {}
    effective_id = _effective_rank_structure_id(org_repo, doc)
    payload["effective_rank_structure_id"] = effective_id
    payload["rank_structure_inherited"] = (
        effective_id is not None
        and payload.get("default_rank_structure_id") is None
        and payload.get("rank_structure_id") is None
    )
    if effective_id is not None:
        structure = _rank_structures_repo().find_one({"int_id": effective_id})
        payload["effective_rank_structure_name"] = structure.get("name") if structure else None
    else:
        payload["effective_rank_structure_name"] = None
    return payload


@router.get("/types")
def list_org_types(search: str = "") -> list[dict[str, Any]]:
    repo = _org_types_repo()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    return [_serialize(doc) for doc in repo.find_many(query, sort=[("name", 1)])]


@router.post("/types", status_code=201)
def create_org_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _org_types_repo()
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "is_active": body.get("is_active", 1),
        "sort_order": body.get("sort_order", 0),
    })
    return _serialize(doc) or {}


@router.get("/types/{type_id}")
def get_org_type(type_id: int) -> dict[str, Any]:
    doc = _org_types_repo().find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    return _serialize(doc) or {}


@router.patch("/types/{type_id}")
def update_org_type(type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _org_types_repo()
    updates = {field: body[field] for field in ("name", "description", "is_active", "sort_order") if field in body}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    repo.update_one(doc["_id"], updates)
    return _serialize(repo.find_by_id(doc["_id"])) or {}


@router.delete("/types/{type_id}", status_code=204)
def delete_org_type(type_id: int) -> None:
    repo = _org_types_repo()
    doc = repo.find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    repo.delete_one(doc["_id"])


@router.get("/rank-structures")
def list_rank_structures(search: str = "") -> list[dict[str, Any]]:
    repo = _rank_structures_repo()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    return [_enrich_rank_structure(doc) for doc in repo.find_many(query, sort=[("name", 1)])]


@router.post("/rank-structures", status_code=201)
def create_rank_structure(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _rank_structures_repo()
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "organization_type_id": body.get("organization_type_id"),
        "is_template": body.get("is_template", 0),
        "is_system_template": body.get("is_system_template", 0),
        "is_active": body.get("is_active", 1),
        "sort_order": body.get("sort_order", 0),
    })
    _rank_audit_repo().insert_one({
        "rank_structure_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    return _enrich_rank_structure(doc)


@router.get("/rank-structures/{structure_id}")
def get_rank_structure(structure_id: int) -> dict[str, Any]:
    doc = _rank_structures_repo().find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    return _enrich_rank_structure(doc)


@router.patch("/rank-structures/{structure_id}")
def update_rank_structure(structure_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _rank_structures_repo()
    updates = {
        field: body[field]
        for field in (
            "name", "description", "organization_type_id",
            "is_template", "is_system_template", "is_active", "sort_order",
        )
        if field in body
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    repo.update_one(doc["_id"], updates)
    _rank_audit_repo().insert_one({
        "rank_structure_id": structure_id,
        "action": "update",
        "timestamp": _utcnow(),
    })
    return _enrich_rank_structure(repo.find_by_id(doc["_id"]))


@router.delete("/rank-structures/{structure_id}", status_code=204)
def delete_rank_structure(structure_id: int) -> None:
    repo = _rank_structures_repo()
    doc = repo.find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    _ranks_repo().delete_many({"rank_structure_id": structure_id})
    repo.delete_one(doc["_id"])
    _rank_audit_repo().insert_one({
        "rank_structure_id": structure_id,
        "action": "delete",
        "timestamp": _utcnow(),
    })


@router.post("/rank-structures/{structure_id}/duplicate")
def duplicate_rank_structure(structure_id: int, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    repo = _rank_structures_repo()
    ranks_repo = _ranks_repo()
    src = repo.find_one({"int_id": structure_id})
    if not src:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    new_doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "name": body.get("name") or f"{src.get('name')} (Copy)",
        "description": src.get("description"),
        "organization_type_id": body.get("organization_type_id", src.get("organization_type_id")),
        "is_template": int(bool(body.get("is_template", src.get("is_template", 0)))),
        "is_system_template": 0,
        "is_active": src.get("is_active", 1),
        "sort_order": src.get("sort_order", 0),
    })
    for rank in ranks_repo.find_many({"rank_structure_id": structure_id}, sort=[("sort_order", 1), ("rank_order", 1)]):
        ranks_repo.insert_one({
            "int_id": _next_int_id(ranks_repo),
            "rank_structure_id": new_doc["int_id"],
            "rank_code": rank.get("rank_code", ""),
            "rank_name": rank.get("rank_name", rank.get("name", "")),
            "short_display": rank.get("short_display", rank.get("abbreviation", "")),
            "sort_order": rank.get("sort_order", rank.get("rank_order", 0)),
            "is_active": rank.get("is_active", 1),
        })
    _rank_audit_repo().insert_one({
        "rank_structure_id": new_doc["int_id"],
        "action": "duplicate",
        "source_id": structure_id,
        "timestamp": _utcnow(),
    })
    return _enrich_rank_structure(new_doc)


_ORGANIZATION_FIELDS = (
    "name", "short_name", "parent_organization_id", "organization_type_id",
    "default_rank_structure_id", "is_active", "notes", "external_id",
    "callsign_prefix", "sort_order", "call_sign", "org_type_id",
    "parent_id", "rank_structure_id",
)


@router.get("/organizations")
def list_organizations(search: str = "") -> list[dict[str, Any]]:
    repo = _organizations_repo()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"short_name": {"$regex": search, "$options": "i"}},
            {"call_sign": {"$regex": search, "$options": "i"}},
        ]
    }
    return [_enrich_organization(doc) for doc in repo.find_many(query, sort=[("name", 1)])]


@router.post("/organizations", status_code=201)
def create_organization(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _organizations_repo()
    doc = {"int_id": _next_int_id(repo)}
    for field in _ORGANIZATION_FIELDS:
        if field in body:
            doc[field] = body.get(field)
    if doc.get("is_active") is None:
        doc["is_active"] = 1
    if doc.get("sort_order") is None:
        doc["sort_order"] = 0
    doc = repo.insert_one(doc)
    _org_audit_repo().insert_one({
        "organization_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    return _enrich_organization(doc)


@router.get("/organizations/{org_id}")
def get_organization(org_id: int) -> dict[str, Any]:
    doc = _organizations_repo().find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _enrich_organization(doc)


@router.patch("/organizations/{org_id}")
def update_organization(org_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _organizations_repo()
    updates = {field: body[field] for field in _ORGANIZATION_FIELDS if field in body}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    repo.update_one(doc["_id"], updates)
    _org_audit_repo().insert_one({
        "organization_id": org_id,
        "action": "update",
        "timestamp": _utcnow(),
    })
    return _enrich_organization(repo.find_by_id(doc["_id"]))


@router.delete("/organizations/{org_id}", status_code=204)
def delete_organization(org_id: int) -> None:
    repo = _organizations_repo()
    doc = repo.find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    repo.delete_one(doc["_id"])
    _org_audit_repo().insert_one({
        "organization_id": org_id,
        "action": "delete",
        "timestamp": _utcnow(),
    })


@router.get("/ranks")
def list_ranks(structure_id: int | None = Query(None), search: str = "") -> list[dict[str, Any]]:
    repo = _ranks_repo()
    query: dict[str, Any] = {}
    if structure_id is not None:
        query["rank_structure_id"] = structure_id
    if search:
        query["$or"] = [
            {"rank_name": {"$regex": search, "$options": "i"}},
            {"rank_code": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]
    return [_serialize(doc) for doc in repo.find_many(query, sort=[("sort_order", 1), ("rank_order", 1)])]


@router.post("/ranks", status_code=201)
def create_rank(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ranks_repo()
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "rank_structure_id": body.get("rank_structure_id"),
        "rank_code": body.get("rank_code", body.get("abbreviation", "")),
        "rank_name": body.get("rank_name", body.get("name", "")),
        "short_display": body.get("short_display", body.get("abbreviation", "")),
        "sort_order": body.get("sort_order", body.get("rank_order", 0)),
        "is_active": body.get("is_active", 1),
    })
    return _serialize(doc) or {}


@router.get("/ranks/{rank_id}")
def get_rank(rank_id: int) -> dict[str, Any]:
    doc = _ranks_repo().find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    return _serialize(doc) or {}


@router.patch("/ranks/{rank_id}")
def update_rank(rank_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _ranks_repo()
    updates = {
        field: body[field]
        for field in ("rank_code", "rank_name", "short_display", "sort_order", "is_active", "name", "abbreviation", "rank_order")
        if field in body
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = repo.find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    repo.update_one(doc["_id"], updates)
    return _serialize(repo.find_by_id(doc["_id"])) or {}


@router.delete("/ranks/{rank_id}", status_code=204)
def delete_rank(rank_id: int) -> None:
    repo = _ranks_repo()
    doc = repo.find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    repo.delete_one(doc["_id"])


@router.get("/organizations/{org_id}/rank-structure-override")
def get_rank_structure_override(org_id: int) -> dict[str, Any] | None:
    return _serialize(_overrides_repo().find_one({"organization_id": org_id}))


@router.post("/organizations/{org_id}/rank-structure-override")
def set_rank_structure_override(org_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    repo = _overrides_repo()
    existing = repo.find_one({"organization_id": org_id})
    payload = {"organization_id": org_id, "rank_structure_id": body.get("rank_structure_id")}
    if existing:
        repo.update_one(existing["_id"], payload)
        result = repo.find_by_id(existing["_id"])
    else:
        result = repo.insert_one(payload)
    return _serialize(result) or {}


@router.delete("/organizations/{org_id}/rank-structure-override", status_code=204)
def delete_rank_structure_override(org_id: int) -> None:
    repo = _overrides_repo()
    doc = repo.find_one({"organization_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Override not found")
    repo.delete_one(doc["_id"])
