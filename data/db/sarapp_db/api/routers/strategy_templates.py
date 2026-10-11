"""FastAPI router for master strategy (work assignment) templates.

A strategy template is a suggested ICS-204 work assignment. It can be tied
to an objective template via `objective_template_id` so that importing an
objective can offer its suggested strategies for import in the same step;
templates with no `objective_template_id` are generic and selectable for
any objective.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import _ensure_record_ids, dual_key_field, next_record_id
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_RECORD_FIELD = "int_id"
_MASTER_RECORD_FIELD = "int_id_master"


class StrategyTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.STRATEGY_TEMPLATES
    soft_deletes = False


def _repo() -> StrategyTemplatesRepository:
    return StrategyTemplatesRepository(get_master_db())


def _record_field(repo: StrategyTemplatesRepository) -> str:
    return dual_key_field(repo._db, _RECORD_FIELD, _MASTER_RECORD_FIELD)


def _strip(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# List / search
# ---------------------------------------------------------------------------

@router.get("")
def list_strategy_templates(
    search: str = "",
    include_archived: bool = False,
    objective_template_id: int | None = None,
    tag: str = "",
) -> list[dict[str, Any]]:
    repo = _repo()
    field = _record_field(repo)
    _ensure_record_ids(repo._col, field)
    query: dict[str, Any] = {}
    if not include_archived:
        query["active"] = {"$ne": False}
    if objective_template_id is not None:
        query["objective_template_id"] = objective_template_id
    if search:
        pattern = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [{"title": pattern}, {"description": pattern}]
    if tag:
        query["tags"] = tag.strip()
    docs = repo.find_many(query, sort=[("updated_at", -1), (field, -1)])
    return [_strip(d) for d in docs]


@router.get("/tags")
def list_tags() -> list[str]:
    repo = _repo()
    tags = repo._col.distinct("tags", {"active": {"$ne": False}})
    return sorted(t for t in tags if t)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_strategy_template(body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    field = _record_field(repo)
    tags = [t.strip() for t in (body.get("tags") or []) if str(t).strip()]
    doc = {
        field: next_record_id(repo._col, field),
        "objective_template_id": body.get("objective_template_id"),
        "title": str(body.get("title") or ""),
        "description": str(body.get("description") or ""),
        "assignment_kind": body.get("assignment_kind") or "Ground",
        "branch": body.get("branch") or None,
        "division_group": body.get("division_group") or None,
        "priority": body.get("priority") or "Normal",
        "active": body.get("active", True),
        "tags": tags,
    }
    saved = repo.insert_one(doc)
    return _strip(saved)


@router.get("/{template_id}")
def get_strategy_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    doc = repo.find_one({_record_field(repo): template_id})
    if not doc:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    return _strip(doc)


@router.patch("/{template_id}")
def update_strategy_template(template_id: int, body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    field = _record_field(repo)
    existing = repo.find_one({field: template_id})
    if not existing:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    update: dict[str, Any] = {}
    for field in (
        "objective_template_id", "title", "description", "assignment_kind",
        "branch", "division_group", "priority", "active",
    ):
        if field in body:
            update[field] = body[field]
    if "tags" in body:
        update["tags"] = [t.strip() for t in (body["tags"] or []) if str(t).strip()]
    update.pop(_RECORD_FIELD, None)
    update.pop(_MASTER_RECORD_FIELD, None)
    repo.update_one(existing["_id"], update)
    doc = repo.find_by_id(existing["_id"])
    return _strip(doc)


@router.delete("/{template_id}", status_code=204)
def delete_strategy_template(template_id: int) -> None:
    repo = _repo()
    existing = repo.find_one({_record_field(repo): template_id})
    if not existing:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    repo.delete_one(existing["_id"])


@router.patch("/{template_id}/active")
def set_active(template_id: int, body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    active = bool(body.get("active", True))
    existing = repo.find_one({_record_field(repo): template_id})
    if not existing:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    repo.update_one(existing["_id"], {"active": active})
    doc = repo.find_by_id(existing["_id"])
    return _strip(doc)
