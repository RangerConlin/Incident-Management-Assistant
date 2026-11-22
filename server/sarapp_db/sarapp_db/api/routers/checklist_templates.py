"""Master checklist-template catalog.

A checklist template is an admin-editable, reusable definition of ordered
sections and ordered items (see `sarapp_db.services.checklist_service` for
the shared item/section shape and validation). Every org that uses this
software can define its own templates, organized under free-text
categories, the same way hazard types and GAR templates already work —
there is deliberately no separate template-management system and no
per-module template editor; any feature module (Planned Events today,
others later) that wants a checklist instance from a template reads this
catalog and calls `api/routers/checklists.py`'s "from template" endpoint.

Modifying or deleting a template here never changes a checklist instance
that already snapshotted it (`checklist_service.snapshot_sections`) — this
catalog only has to keep its own state consistent, not rewrite history.

This catalog is writable from any server (not central-lockdown), the same
as `hazard_types.py` and `gar_templates.py` — it is an org-local reference
list, not one of the central-authoritative taxonomies (`organizations`,
`resource_types`, `forms`, `lookup_types`, `certification_types`,
`qualification_types`) that `_require_central` guards.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import dual_key_field
from sarapp_db.mongo.repository import BaseRepository
from sarapp_db.services.checklist_service import ITEM_TYPES, validate_template_shape

router = APIRouter()

_RECORD_FIELD = "id"
_MASTER_RECORD_FIELD = "id_master"


class ChecklistTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.CHECKLIST_TEMPLATES
    soft_deletes = False


def _repo() -> ChecklistTemplatesRepository:
    return ChecklistTemplatesRepository(get_master_db())


def _record_field(repo: ChecklistTemplatesRepository) -> str:
    return dual_key_field(repo._db, _RECORD_FIELD, _MASTER_RECORD_FIELD)


def _next_int_id(repo: ChecklistTemplatesRepository, field: str) -> int:
    docs = repo.find_many({field: {"$exists": True}}, sort=[(field, -1)], limit=1)
    return int((docs[0] if docs else {}).get(field) or 0) + 1


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    data = dict(doc)
    data.pop("_id", None)
    return data


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class ChecklistTemplateOption(BaseModel):
    id: str
    label: str


class ChecklistTemplateItem(BaseModel):
    id: str
    item_type: str
    label: str
    instructions: str = ""
    required: bool = False
    na_allowed: bool = False
    options: list[ChecklistTemplateOption] = Field(default_factory=list)
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class ChecklistTemplateSection(BaseModel):
    # A section's name may be blank. Sections themselves are optional — a
    # template with no meaningful grouping is simply one section with a
    # blank name, rather than a second parallel "items with no section"
    # list the rest of this feature would have to special-case.
    id: str
    name: str = ""
    items: list[ChecklistTemplateItem] = Field(default_factory=list)


class SaveChecklistTemplateRequest(BaseModel):
    name: str
    category: str = "Other"
    description: str = ""
    instructions: str = ""
    sections: list[ChecklistTemplateSection] = Field(min_length=1)
    active: bool = True
    created_by: str = ""
    updated_by: str = ""


class SetActiveRequest(BaseModel):
    active: bool


def _validate_item_types(body: SaveChecklistTemplateRequest) -> None:
    for section in body.sections:
        for item in section.items:
            if item.item_type not in ITEM_TYPES:
                raise HTTPException(422, f"Unknown item_type: {item.item_type!r}")


def _payload_for_write(body: SaveChecklistTemplateRequest) -> dict[str, Any]:
    _validate_item_types(body)
    sections = [section.model_dump() for section in body.sections]
    try:
        validate_template_shape(sections)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "name": body.name.strip(),
        "category": (body.category or "").strip() or "Other",
        "description": body.description.strip(),
        "instructions": body.instructions.strip(),
        "sections": sections,
        "active": body.active,
        "created_by": body.created_by.strip(),
        "updated_by": body.updated_by.strip(),
    }


@router.get("")
def list_checklist_templates(
    category: Optional[str] = None, include_inactive: bool = False
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {} if include_inactive else {"active": True}
    if category:
        query["category"] = category
    docs = _repo().find_many(query, sort=[("category", 1), ("name", 1)])
    return [_normalize(doc) for doc in docs]


@router.get("/categories")
def list_checklist_template_categories() -> list[str]:
    docs = _repo().find_many({})
    categories = {str(doc.get("category") or "").strip() for doc in docs}
    categories.discard("")
    return sorted(categories)


@router.post("", status_code=201)
def create_checklist_template(body: SaveChecklistTemplateRequest) -> dict[str, Any]:
    repo = _repo()
    field = _record_field(repo)
    doc = {field: _next_int_id(repo, field), **_payload_for_write(body)}
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.get("/{template_id}")
def get_checklist_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    doc = repo.find_one({_record_field(repo): template_id})
    if doc is None:
        raise HTTPException(404, "Checklist template not found")
    return _normalize(doc)


@router.put("/{template_id}")
def save_checklist_template(template_id: int, body: SaveChecklistTemplateRequest) -> dict[str, Any]:
    repo = _repo()
    field = _record_field(repo)
    existing = repo.find_one({field: template_id})
    if existing is None:
        raise HTTPException(404, "Checklist template not found")
    updates = {
        field: template_id,
        **_payload_for_write(body),
        "created_by": existing.get("created_by", ""),
    }
    repo.update_one(existing["_id"], updates)
    saved = repo.find_by_id(existing["_id"])
    return _normalize(saved or updates)


@router.post("/{template_id}/clone", status_code=201)
def clone_checklist_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    field = _record_field(repo)
    original = repo.find_one({field: template_id})
    if original is None:
        raise HTTPException(404, "Checklist template not found")
    base_name = str(original.get("name") or "").strip()
    copy_num = 1
    while repo.find_one({"name": f"{base_name} Copy {copy_num}"}):
        copy_num += 1
    clone = {
        key: value
        for key, value in original.items()
        if key not in {"_id", "created_at", "updated_at", "created_by", "updated_by", _RECORD_FIELD, _MASTER_RECORD_FIELD}
    }
    clone[field] = _next_int_id(repo, field)
    clone["name"] = f"{base_name} Copy {copy_num}"
    clone["created_by"] = ""
    clone["updated_by"] = ""
    saved = repo.insert_one(clone)
    return _normalize(saved)


@router.patch("/{template_id}/active")
def set_checklist_template_active(template_id: int, body: SetActiveRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({_record_field(repo): template_id})
    if existing is None:
        raise HTTPException(404, "Checklist template not found")
    repo.update_one(existing["_id"], {"active": body.active})
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc) if doc else {}
