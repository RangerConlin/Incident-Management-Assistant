"""FastAPI router for master strategy (work assignment) templates.

A strategy template is a suggested ICS-204 work assignment. It can be tied
to an objective template via `objective_template_id` so that importing an
objective can offer its suggested strategies for import in the same step;
templates with no `objective_template_id` are generic and selectable for
any objective.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.int_id import _ensure_int_ids, next_int_id

router = APIRouter()


def _col():
    return get_client()["sarapp_master"][MasterCollections.STRATEGY_TEMPLATES]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    col = _col()
    _ensure_int_ids(col)
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
    docs = list(col.find(query, sort=[("updated_at", -1), ("int_id", -1)]))
    return [_strip(d) for d in docs]


@router.get("/tags")
def list_tags() -> list[str]:
    col = _col()
    tags = col.distinct("tags", {"active": {"$ne": False}})
    return sorted(t for t in tags if t)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_strategy_template(body: dict[str, Any]) -> dict[str, Any]:
    col = _col()
    now = _now()
    tags = [t.strip() for t in (body.get("tags") or []) if str(t).strip()]
    doc = {
        "int_id": next_int_id(col),
        "objective_template_id": body.get("objective_template_id"),
        "title": str(body.get("title") or ""),
        "description": str(body.get("description") or ""),
        "assignment_kind": body.get("assignment_kind") or "Ground",
        "branch": body.get("branch") or None,
        "division_group": body.get("division_group") or None,
        "priority": body.get("priority") or "Normal",
        "active": body.get("active", True),
        "tags": tags,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    return _strip(doc)


@router.get("/{template_id}")
def get_strategy_template(template_id: int) -> dict[str, Any]:
    doc = _col().find_one({"int_id": template_id})
    if not doc:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    return _strip(doc)


@router.patch("/{template_id}")
def update_strategy_template(template_id: int, body: dict[str, Any]) -> dict[str, Any]:
    col = _col()
    update: dict[str, Any] = {"updated_at": _now()}
    for field in (
        "objective_template_id", "title", "description", "assignment_kind",
        "branch", "division_group", "priority", "active",
    ):
        if field in body:
            update[field] = body[field]
    if "tags" in body:
        update["tags"] = [t.strip() for t in (body["tags"] or []) if str(t).strip()]
    doc = col.find_one_and_update(
        {"int_id": template_id},
        {"$set": update},
        return_document=True,
    )
    if not doc:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    return _strip(doc)


@router.delete("/{template_id}", status_code=204)
def delete_strategy_template(template_id: int) -> None:
    result = _col().delete_one({"int_id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(404, f"Strategy template {template_id} not found")


@router.patch("/{template_id}/active")
def set_active(template_id: int, body: dict[str, Any]) -> dict[str, Any]:
    active = bool(body.get("active", True))
    doc = _col().find_one_and_update(
        {"int_id": template_id},
        {"$set": {"active": active, "updated_at": _now()}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(404, f"Strategy template {template_id} not found")
    return _strip(doc)
