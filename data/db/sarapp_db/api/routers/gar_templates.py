"""Master GAR (Green-Amber-Red) risk-assessment template library.

A GAR template is an admin-editable scoring rubric: groups of hazard rows,
each row offering a few discrete, objective options with a point value
(optionally flagged as a hard No-Go, which overrides the point total
outright). This is deliberately not the stock USCG 6-factor model (free
1-10 dials per factor) — that produces inconsistent scores between
assessors. Every org that uses this software can define its own template
(a generic default ships here; an org can add one mirroring its own paper
ORM form) without any code change.

Scoring itself (``score_selections``) is also defined here and imported by
``operations.py``, which resolves assessed Team GAR submissions against
whichever template was used.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class GarTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.GAR_TEMPLATES
    soft_deletes = False


def _repo() -> GarTemplatesRepository:
    return GarTemplatesRepository(get_master_db())


def _next_int_id(repo: GarTemplatesRepository) -> int:
    docs = repo.find_many({"id": {"$exists": True}}, sort=[("id", -1)], limit=1)
    return int((docs[0] if docs else {}).get("id") or 0) + 1


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    data = dict(doc)
    data.pop("_id", None)
    return data


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class GarOption(BaseModel):
    id: str
    label: str
    points: int = 0
    no_go: bool = False


class GarRow(BaseModel):
    id: str
    label: str
    options: list[GarOption] = Field(min_length=1)


class GarGroup(BaseModel):
    id: str
    name: str
    rows: list[GarRow] = Field(min_length=1)


class GarBand(BaseModel):
    floor: int
    label: str
    required_reviewer: str = ""


class SaveGarTemplateRequest(BaseModel):
    name: str
    source: str = ""
    description: str = ""
    groups: list[GarGroup] = Field(min_length=1)
    bands: list[GarBand] = Field(min_length=1)
    active: bool = True
    created_by: str = ""
    updated_by: str = ""


class SetActiveRequest(BaseModel):
    active: bool


class GarSelection(BaseModel):
    group_id: str
    row_id: str
    option_id: str


def _validate_template_shape(body: SaveGarTemplateRequest) -> None:
    group_ids: set[str] = set()
    for group in body.groups:
        if group.id in group_ids:
            raise HTTPException(422, f"Duplicate group id: {group.id}")
        group_ids.add(group.id)
        row_ids: set[str] = set()
        for row in group.rows:
            if row.id in row_ids:
                raise HTTPException(422, f"Duplicate row id '{row.id}' in group '{group.id}'")
            row_ids.add(row.id)
            option_ids: set[str] = set()
            for option in row.options:
                if option.id in option_ids:
                    raise HTTPException(
                        422, f"Duplicate option id '{option.id}' in row '{row.id}'"
                    )
                option_ids.add(option.id)


def _payload_for_write(body: SaveGarTemplateRequest) -> dict[str, Any]:
    _validate_template_shape(body)
    return {
        "name": body.name.strip(),
        "source": body.source.strip(),
        "description": body.description.strip(),
        "groups": [group.model_dump() for group in body.groups],
        "bands": sorted(
            (band.model_dump() for band in body.bands), key=lambda b: -int(b["floor"])
        ),
        "active": body.active,
        "created_by": body.created_by.strip(),
        "updated_by": body.updated_by.strip(),
    }


@router.get("")
def list_gar_templates(include_inactive: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {} if include_inactive else {"active": True}
    docs = _repo().find_many(query, sort=[("name", 1)])
    return [_normalize(doc) for doc in docs]


@router.post("", status_code=201)
def create_gar_template(body: SaveGarTemplateRequest) -> dict[str, Any]:
    repo = _repo()
    doc = {"id": _next_int_id(repo), **_payload_for_write(body)}
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.get("/{template_id}")
def get_gar_template(template_id: int) -> dict[str, Any]:
    doc = _repo().find_one({"id": template_id})
    if doc is None:
        raise HTTPException(404, "GAR template not found")
    return _normalize(doc)


@router.put("/{template_id}")
def save_gar_template(template_id: int, body: SaveGarTemplateRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"id": template_id})
    if existing is None:
        raise HTTPException(404, "GAR template not found")
    updates = {
        "id": template_id,
        **_payload_for_write(body),
        "created_by": existing.get("created_by", ""),
    }
    repo.update_one(existing["_id"], updates)
    saved = repo.find_by_id(existing["_id"])
    return _normalize(saved or updates)


@router.post("/{template_id}/clone", status_code=201)
def clone_gar_template(template_id: int) -> dict[str, Any]:
    repo = _repo()
    original = repo.find_one({"id": template_id})
    if original is None:
        raise HTTPException(404, "GAR template not found")
    base_name = str(original.get("name") or "").strip()
    copy_num = 1
    while repo.find_one({"name": f"{base_name} Copy {copy_num}"}):
        copy_num += 1
    clone = {
        key: value
        for key, value in original.items()
        if key not in {"_id", "created_at", "updated_at", "created_by", "updated_by", "id"}
    }
    clone["id"] = _next_int_id(repo)
    clone["name"] = f"{base_name} Copy {copy_num}"
    clone["created_by"] = ""
    clone["updated_by"] = ""
    saved = repo.insert_one(clone)
    return _normalize(saved)


@router.patch("/{template_id}/active")
def set_gar_template_active(template_id: int, body: SetActiveRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"id": template_id})
    if existing is None:
        raise HTTPException(404, "GAR template not found")
    repo.update_one(existing["_id"], {"active": body.active})
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc) if doc else {}


# ---------------------------------------------------------------------------
# Scoring engine — used by operations.py when a team GAR assessment is saved.
# Pure function of (template document, selections); no DB access of its own,
# so it is also unit-testable without Mongo.
# ---------------------------------------------------------------------------

def score_selections(template: dict[str, Any], selections: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve a set of (group_id, row_id, option_id) selections against a
    template. Every row in the template must have exactly one selection.
    Raises ValueError (caller translates to HTTP 422) on any mismatch.

    Returns a fully denormalized result — resolved row/option labels and
    points, the summed score, whether any selected option forced a No-Go,
    and the resulting band label + required reviewer — so the caller can
    snapshot it onto the assessment without depending on the template
    staying unchanged for history to remain meaningful.
    """
    row_index: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for group in template.get("groups") or []:
        for row in group.get("rows") or []:
            row_index[(group["id"], row["id"])] = (group, row)

    resolved: list[dict[str, Any]] = []
    total = 0
    no_go = False
    seen_keys: set[tuple[str, str]] = set()
    for sel in selections:
        key = (sel["group_id"], sel["row_id"])
        if key in seen_keys:
            raise ValueError(f"Duplicate selection for row {key}")
        seen_keys.add(key)
        entry = row_index.get(key)
        if entry is None:
            raise ValueError(f"Unknown row {key} for this template")
        group, row = entry
        option = next(
            (opt for opt in row.get("options") or [] if opt["id"] == sel["option_id"]), None
        )
        if option is None:
            raise ValueError(f"Unknown option '{sel['option_id']}' for row {key}")
        points = int(option.get("points") or 0)
        total += points
        row_no_go = bool(option.get("no_go"))
        no_go = no_go or row_no_go
        resolved.append(
            {
                "group_id": group["id"],
                "group_name": group.get("name") or "",
                "row_id": row["id"],
                "row_label": row.get("label") or "",
                "option_id": option["id"],
                "option_label": option.get("label") or "",
                "points": points,
                "no_go": row_no_go,
            }
        )

    if seen_keys != set(row_index.keys()):
        missing = set(row_index.keys()) - seen_keys
        raise ValueError(f"Missing selection for rows: {sorted(missing)}")

    bands = sorted(template.get("bands") or [], key=lambda b: -int(b["floor"]))
    if not bands:
        raise ValueError("Template has no bands defined")

    if no_go:
        band_label = "No-Go"
        required_reviewer = bands[0].get("required_reviewer", "")
    else:
        chosen = bands[-1]
        for band in bands:
            if total >= int(band["floor"]):
                chosen = band
                break
        band_label = chosen.get("label", "")
        required_reviewer = chosen.get("required_reviewer", "")

    return {
        "selections": resolved,
        "score": total,
        "band": band_label,
        "required_reviewer": required_reviewer,
        "no_go": no_go,
    }
