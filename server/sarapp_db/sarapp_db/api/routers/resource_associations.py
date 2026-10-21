"""Resource Associations API router (Stage 2).

Persistent, non-incident-specific relationships between two individual
master resources -- a radio assigned to a person, equipment carried onboard
a vehicle, a vehicle associated with a trailer, a person routinely assigned
to a unit. These are standing relationships: changing an incident team's
composition must never write to this collection (see operations.py/
checkin.py, which only ever read it).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.mongo.resource_kinds import (
    RESOURCE_KINDS,
    find_resource,
    is_known_resource_type,
    resource_display_name,
)

router = APIRouter()

# Suggested association types. Deliberately not an enum anywhere in this
# module -- `association_type` is a plain string field so a new kind of
# relationship can be recorded without a schema or code change.
SUGGESTED_ASSOCIATION_TYPES: tuple[str, ...] = (
    "Assigned",
    "Carried/Onboard",
    "Default Member",
    "Associated",
)


class ResourceAssociationsRepository(BaseRepository):
    collection_name = MasterCollections.RESOURCE_ASSOCIATIONS


def _repo() -> ResourceAssociationsRepository:
    return ResourceAssociationsRepository(get_master_db())


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ResourceEndpoint(BaseModel):
    resource_type: str
    resource_id: int


class SaveAssociationRequest(BaseModel):
    source: ResourceEndpoint
    target: ResourceEndpoint
    association_type: str
    owning_organization: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    notes: str = ""
    active: bool = True
    created_by: str = ""


def _edge_key(resource_type: str, resource_id: int) -> tuple[str, int]:
    return (resource_type, int(resource_id))


def find_path(
    edges: list[tuple[tuple[str, int], tuple[str, int]]],
    start: tuple[str, int],
    goal: tuple[str, int],
) -> bool:
    """Pure graph search: True if `goal` is reachable from `start` by
    following `edges` (source -> target) in order. Used both to detect a
    would-be cycle before insert and unit-tested on its own (no Mongo).
    """
    if start == goal:
        return True
    adjacency: dict[tuple[str, int], list[tuple[str, int]]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)
    seen: set[tuple[str, int]] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == goal:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, []))
    return False


def _active_edges(repo: ResourceAssociationsRepository) -> list[tuple[tuple[str, int], tuple[str, int]]]:
    edges = []
    for doc in repo.find_many({"active": True}):
        src = doc.get("source") or {}
        dst = doc.get("target") or {}
        if "resource_type" in src and "resource_type" in dst:
            edges.append((_edge_key(src["resource_type"], src["resource_id"]), _edge_key(dst["resource_type"], dst["resource_id"])))
    return edges


def _normalize(doc: dict[str, Any], db) -> dict[str, Any]:
    d = dict(doc)
    d["id"] = d.pop("_id", None)
    src = d.get("source") or {}
    dst = d.get("target") or {}
    d["source_label"] = resource_display_name(
        find_resource(db, src.get("resource_type", ""), src.get("resource_id", -1)), src.get("resource_type", "")
    )
    d["target_label"] = resource_display_name(
        find_resource(db, dst.get("resource_type", ""), dst.get("resource_id", -1)), dst.get("resource_type", "")
    )
    return d


@router.get("")
def list_associations(
    resource_type: str = Query(""),
    resource_id: Optional[int] = Query(None),
    role: str = Query("either", description="source | target | either"),
    include_inactive: bool = Query(True),
) -> list[dict[str, Any]]:
    """List associations involving a resource (either side), or every
    association when no resource is given."""
    repo = _repo()
    query: dict[str, Any] = {} if include_inactive else {"active": True}
    if resource_type and resource_id is not None:
        clauses = []
        if role in ("source", "either"):
            clauses.append({"source.resource_type": resource_type, "source.resource_id": resource_id})
        if role in ("target", "either"):
            clauses.append({"target.resource_type": resource_type, "target.resource_id": resource_id})
        query["$or"] = clauses
    docs = repo.find_many(query, sort=[("updated_at", -1)])
    return [_normalize(d, repo._db) for d in docs]


@router.get("/{association_id}")
def get_association(association_id: str) -> dict[str, Any]:
    repo = _repo()
    doc = repo.find_by_id(association_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Association not found")
    return _normalize(doc, repo._db)


def _validate_endpoint(db, endpoint: ResourceEndpoint, label: str) -> None:
    if not is_known_resource_type(endpoint.resource_type):
        raise HTTPException(
            status_code=400,
            detail=f"{label} resource_type must be one of {RESOURCE_KINDS}, got {endpoint.resource_type!r}.",
        )
    if find_resource(db, endpoint.resource_type, endpoint.resource_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"{label} resource {endpoint.resource_type}:{endpoint.resource_id} does not exist.",
        )


@router.post("", status_code=201)
def create_association(body: SaveAssociationRequest) -> dict[str, Any]:
    repo = _repo()
    db = repo._db

    _validate_endpoint(db, body.source, "Source")
    _validate_endpoint(db, body.target, "Target")

    source_key = _edge_key(body.source.resource_type, body.source.resource_id)
    target_key = _edge_key(body.target.resource_type, body.target.resource_id)
    if source_key == target_key:
        raise HTTPException(status_code=400, detail="A resource cannot be associated with itself.")

    # Duplicate prevention: same source/target/type pair already active.
    existing = repo.find_one(
        {
            "source.resource_type": body.source.resource_type,
            "source.resource_id": body.source.resource_id,
            "target.resource_type": body.target.resource_type,
            "target.resource_id": body.target.resource_id,
            "association_type": body.association_type,
            "active": True,
        }
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="That association already exists.")

    # Cycle prevention: reject if the target can already reach the source
    # through existing active associations (adding this edge would close a loop).
    if find_path(_active_edges(repo), target_key, source_key):
        raise HTTPException(
            status_code=409,
            detail="This association would create a circular reference between resources.",
        )

    doc = {
        "source": body.source.model_dump(),
        "target": body.target.model_dump(),
        "association_type": body.association_type,
        "owning_organization": body.owning_organization,
        "effective_start": body.effective_start,
        "effective_end": body.effective_end,
        "notes": body.notes,
        "active": body.active,
        "created_by": body.created_by,
    }
    saved = repo.insert_one(doc)
    return _normalize(saved, db)


class UpdateAssociationRequest(BaseModel):
    association_type: Optional[str] = None
    owning_organization: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


@router.patch("/{association_id}")
def update_association(association_id: str, body: UpdateAssociationRequest = Body(...)) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_by_id(association_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Association not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        repo.update_one(association_id, updates)
    doc = repo.find_by_id(association_id)
    return _normalize(doc, repo._db)


@router.delete("/{association_id}", status_code=204)
def delete_association(association_id: str) -> None:
    """Soft-delete (remove) a standing association."""
    repo = _repo()
    if not repo.soft_delete(association_id):
        raise HTTPException(status_code=404, detail="Association not found")


@router.get("/types/suggested")
def list_suggested_types() -> list[str]:
    return list(SUGGESTED_ASSOCIATION_TYPES)
