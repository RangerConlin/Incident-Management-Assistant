"""Master hazard type library API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

SPE_SEVERITY_RANGE = (1, 5)
SPE_PROBABILITY_RANGE = (1, 5)
SPE_EXPOSURE_RANGE = (1, 4)
SPE_BANDS = (
    (80, "Very High", "Discontinue / Stop"),
    (60, "High", "Correct Immediately"),
    (40, "Substantial", "Correction Required"),
    (20, "Possible", "Attention Needed"),
    (1, "Slight", "Possibly Acceptable"),
)


class HazardTypesRepository(BaseRepository):
    collection_name = MasterCollections.HAZARD_TYPES
    soft_deletes = False


class DefaultSpeInput(BaseModel):
    severity: int = Field(ge=SPE_SEVERITY_RANGE[0], le=SPE_SEVERITY_RANGE[1])
    probability: int = Field(ge=SPE_PROBABILITY_RANGE[0], le=SPE_PROBABILITY_RANGE[1])
    exposure: int = Field(ge=SPE_EXPOSURE_RANGE[0], le=SPE_EXPOSURE_RANGE[1])


class SaveHazardTypeRequest(BaseModel):
    name: str
    category: str = "Other"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    ppe: list[str] = Field(default_factory=list)
    standard_safety_language: str = ""
    default_spe: DefaultSpeInput
    active: bool = True
    created_by: str = ""
    updated_by: str = ""


class SetActiveRequest(BaseModel):
    active: bool


def _repo() -> HazardTypesRepository:
    return HazardTypesRepository(get_master_db())


def _next_int_id(repo: HazardTypesRepository) -> int:
    docs = repo.find_many({"id": {"$exists": True}}, sort=[("id", -1)], limit=1)
    return int((docs[0] if docs else {}).get("id") or 0) + 1


def _spe_score(severity: int, probability: int, exposure: int) -> int:
    return severity * probability * exposure


def _spe_band(score: int) -> tuple[str, str]:
    for floor, degree, action in SPE_BANDS:
        if score >= floor:
            return degree, action
    return SPE_BANDS[-1][1], SPE_BANDS[-1][2]


def _score_default_spe(assessment: DefaultSpeInput) -> dict[str, Any]:
    score = _spe_score(assessment.severity, assessment.probability, assessment.exposure)
    band, action = _spe_band(score)
    return {
        "severity": assessment.severity,
        "probability": assessment.probability,
        "exposure": assessment.exposure,
        "score": score,
        "band": band,
        "action": action,
    }


def _normalize_text_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    data = dict(doc)
    data.pop("_id", None)
    return data


def _search_matches(doc: dict[str, Any], text: str) -> str | None:
    probe = text.casefold()
    for field, label in (
        ("name", "name"),
        ("category", "category"),
        ("description", "description"),
        ("standard_safety_language", "safety language"),
    ):
        if probe in str(doc.get(field) or "").casefold():
            return label
    for alias in doc.get("aliases") or []:
        if probe in str(alias).casefold():
            return "alias"
    for control in doc.get("controls") or []:
        if probe in str(control).casefold():
            return "control"
    for ppe_item in doc.get("ppe") or []:
        if probe in str(ppe_item).casefold():
            return "PPE"
    return None


def _payload_for_write(body: SaveHazardTypeRequest) -> dict[str, Any]:
    return {
        "name": body.name.strip(),
        "category": body.category.strip() or "Other",
        "description": body.description.strip(),
        "aliases": _normalize_text_list(body.aliases),
        "controls": _normalize_text_list(body.controls),
        "ppe": _normalize_text_list(body.ppe),
        "standard_safety_language": body.standard_safety_language.strip(),
        "default_spe": _score_default_spe(body.default_spe),
        "active": body.active,
        "created_by": body.created_by.strip(),
        "updated_by": body.updated_by.strip(),
    }


@router.get("")
def list_hazard_types(
    search_text: str = Query(""),
    category: str = Query("All"),
    active_filter: str = Query("Active"),
    include_inactive: bool = Query(False),
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if active_filter == "Active" and not include_inactive:
        query["active"] = True
    elif active_filter == "Inactive":
        query["active"] = False
    if category and category != "All":
        query["category"] = category

    docs = _repo().find_many(query, sort=[("name", 1)])
    if search_text.strip():
        docs = [doc for doc in docs if _search_matches(doc, search_text.strip()) is not None]
    return [_normalize(doc) for doc in docs]


@router.get("/search")
def search_hazard_types(
    q: str = Query(""),
    include_inactive: bool = Query(False),
    limit: int = Query(20),
) -> list[dict[str, Any]]:
    text = q.strip()
    if not text:
        return []
    base_query: dict[str, Any] = {} if include_inactive else {"active": True}
    docs = _repo().find_many(base_query, sort=[("name", 1)])
    results: list[dict[str, Any]] = []
    for doc in docs:
        matched_on = _search_matches(doc, text)
        if matched_on is None:
            continue
        results.append(
            {
                "id": doc.get("id"),
                "name": doc.get("name", ""),
                "category": doc.get("category", ""),
                "default_spe_band": ((doc.get("default_spe") or {}).get("band") or ""),
                "matched_on": matched_on,
            }
        )
        if len(results) >= limit:
            break
    return results


@router.post("", status_code=201)
def create_hazard_type(body: SaveHazardTypeRequest) -> dict[str, Any]:
    repo = _repo()
    doc = {
        "id": _next_int_id(repo),
        **_payload_for_write(body),
    }
    saved = repo.insert_one(doc)
    return _normalize(saved)


@router.get("/{hazard_type_id}")
def get_hazard_type(hazard_type_id: int) -> dict[str, Any]:
    doc = _repo().find_one({"id": hazard_type_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    return _normalize(doc)


@router.put("/{hazard_type_id}")
def save_hazard_type(hazard_type_id: int, body: SaveHazardTypeRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"id": hazard_type_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    updates = {
        "id": hazard_type_id,
        **_payload_for_write(body),
        "created_by": existing.get("created_by", ""),
    }
    repo.update_one(existing["_id"], updates)
    saved = repo.find_by_id(existing["_id"])
    return _normalize(saved or updates)


@router.post("/{hazard_type_id}/clone", status_code=201)
def clone_hazard_type(hazard_type_id: int) -> dict[str, Any]:
    repo = _repo()
    original = repo.find_one({"id": hazard_type_id})
    if original is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
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


@router.patch("/{hazard_type_id}/active")
def set_hazard_type_active(hazard_type_id: int, body: SetActiveRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"id": hazard_type_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    repo.update_one(existing["_id"], {"active": body.active})
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc) if doc else {}
