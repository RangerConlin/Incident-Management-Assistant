"""Master hazard type library API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class HazardTypesRepository(BaseRepository):
    collection_name = MasterCollections.HAZARD_TYPES
    # Keyed by string `hazard_type_id`, not `_id`; `is_active` is a plain
    # application flag (not a BaseRepository soft-delete marker).
    soft_deletes = False


def _repo() -> HazardTypesRepository:
    return HazardTypesRepository(get_master_db())


def _next_int_id(repo: HazardTypesRepository) -> int:
    """Allocate the next integer hazard_type_id (max existing + 1)."""
    col = repo._col
    max_doc = col.find_one(
        {"hazard_type_id": {"$exists": True}},
        sort=[("hazard_type_id", -1)],
        projection={"hazard_type_id": 1},
    )
    if max_doc and max_doc.get("hazard_type_id", "").isdigit():
        # Sort is lexicographic; iterate to find true numeric max
        candidates = [
            int(d["hazard_type_id"])
            for d in col.find(
                {"hazard_type_id": {"$regex": r"^\d+$"}},
                {"hazard_type_id": 1},
            )
            if d.get("hazard_type_id", "").isdigit()
        ]
        return max(candidates, default=0) + 1
    return 1


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    """Add computed fields the UI expects."""
    d = dict(doc)
    d.pop("_id", None)
    ht_id_str = d.get("hazard_type_id", "")
    d["id"] = int(ht_id_str) if ht_id_str.isdigit() else None
    mitigations = d.get("mitigations") or []
    d["mitigation_count"] = len(mitigations)
    ppe_items = d.get("ppe_items") or []
    d["ppe_preview"] = ", ".join(p["ppe_text"] for p in ppe_items[:3] if p.get("ppe_text"))
    return d


def _search_matches(doc: dict[str, Any], text: str) -> str | None:
    """Return which field matched, or None if no match."""
    t = text.lower()
    for field, label in (
        ("name", "name"),
        ("display_name", "display name"),
        ("category", "category"),
        ("source", "source"),
        ("description", "description"),
        ("default_safety_message", "safety message"),
        ("notes", "notes"),
    ):
        if t in (doc.get(field) or "").lower():
            return label
    for alias in doc.get("aliases") or []:
        if t in (alias or "").lower():
            return "alias"
    for m in doc.get("mitigations") or []:
        if t in (m.get("mitigation_text") or "").lower():
            return "mitigation"
    for p in doc.get("ppe_items") or []:
        if t in (p.get("ppe_text") or "").lower():
            return "PPE"
    return None


# ------------------------------------------------------------------
# List

@router.get("")
def list_hazard_types(
    search_text: str = Query(""),
    category: str = Query("All"),
    source: str = Query("All"),
    risk_level: str = Query("All"),
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
    if risk_level and risk_level != "All":
        query["default_risk_level"] = risk_level

    docs = _repo().find_many(query, sort=[("name", 1)])

    if search_text.strip():
        t = search_text.strip().lower()
        docs = [d for d in docs if _search_matches(d, t)]

    return [_normalize(d) for d in docs]


# ------------------------------------------------------------------
# Search (for the search-box widget)

@router.get("/search")
def search_hazard_types(
    q: str = Query(""),
    include_inactive: bool = Query(False),
    limit: int = Query(20),
) -> list[dict[str, Any]]:
    text = q.strip()
    if not text:
        return []
    base_query: dict[str, Any] = {} if include_inactive else {"is_active": True}
    docs = _repo().find_many(base_query, sort=[("name", 1)])
    results = []
    for doc in docs:
        matched_on = _search_matches(doc, text)
        if matched_on is not None:
            ht_id_str = doc.get("hazard_type_id", "")
            results.append({
                "hazard_type_id": int(ht_id_str) if ht_id_str.isdigit() else None,
                "hazard_type_text": doc.get("display_name") or doc.get("name", ""),
                "category": doc.get("category", ""),
                "default_risk_level": doc.get("default_risk_level", ""),
                "source": doc.get("source", ""),
                "matched_on": matched_on,
            })
        if len(results) >= limit:
            break
    return results


# ------------------------------------------------------------------
# Create

class SaveHazardTypeRequest(BaseModel):
    name: str
    display_name: str = ""
    category: str = "Other"
    source: str = "AHJ Custom"
    owner_agency: str = ""
    description: str = ""
    default_risk_level: str = "Unknown"
    default_likelihood: str = "Unknown"
    default_severity: str = "Unknown"
    default_control_measure: str = ""
    default_ppe: str = ""
    default_safety_message: str = ""
    is_active: bool = True
    notes: str = ""
    created_by: str = ""
    updated_by: str = ""
    aliases: list[str] = []
    mitigations: list[dict[str, Any]] = []
    ppe_items: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    resource_defaults: list[dict[str, Any]] = []


@router.post("", status_code=201)
def create_hazard_type(body: SaveHazardTypeRequest) -> dict[str, Any]:
    repo = _repo()
    new_int_id = _next_int_id(repo)
    doc: dict[str, Any] = {
        "hazard_type_id": str(new_int_id),
        **body.model_dump(exclude={"created_by"}),
        "created_by": body.created_by,
    }
    doc = repo.insert_one(doc)
    return _normalize(doc)


# ------------------------------------------------------------------
# Hazards by resource type — used by HazardPrefillService

@router.get("/by-resource-type/{resource_type_id}")
def get_hazards_for_resource_type(resource_type_id: int) -> list[dict[str, Any]]:
    """Return hazard types whose resource_defaults list includes this resource_type_id."""
    repo = _repo()
    docs = repo.find_many({
        "resource_defaults": {
            "$elemMatch": {"resource_type_id": resource_type_id}
        }
    })
    return [_normalize(d) for d in docs]


# ------------------------------------------------------------------
# Get one — defined AFTER /search to avoid path conflict

@router.get("/{hazard_type_id}")
def get_hazard_type(hazard_type_id: str) -> dict[str, Any]:
    doc = _repo().find_one({"hazard_type_id": hazard_type_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    return _normalize(doc)


# ------------------------------------------------------------------
# Full save (create or update)

@router.put("/{hazard_type_id}")
def save_hazard_type(hazard_type_id: str, body: SaveHazardTypeRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"hazard_type_id": hazard_type_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    updates = {
        **body.model_dump(),
        "hazard_type_id": hazard_type_id,
    }
    updates.setdefault("created_by", existing.get("created_by", ""))
    repo.update_one(existing["_id"], updates)
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc)


# ------------------------------------------------------------------
# Clone

@router.post("/{hazard_type_id}/clone", status_code=201)
def clone_hazard_type(hazard_type_id: str) -> dict[str, Any]:
    repo = _repo()
    original = repo.find_one({"hazard_type_id": hazard_type_id})
    if original is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    new_int_id = _next_int_id(repo)
    base_name = original.get("name", "")
    # Generate a unique copy name
    copy_num = 1
    while repo.find_one({"name": f"{base_name} Copy {copy_num}"}):
        copy_num += 1
    clone = {k: v for k, v in original.items() if k not in ("_id", "created_at", "updated_at")}
    clone["hazard_type_id"] = str(new_int_id)
    clone["name"] = f"{base_name} Copy {copy_num}"
    clone["display_name"] = f"{original.get('display_name', base_name)} Copy {copy_num}".strip()
    clone["created_by"] = ""
    clone["updated_by"] = ""
    clone = repo.insert_one(clone)
    return _normalize(clone)


# ------------------------------------------------------------------
# Set active flag

class SetActiveRequest(BaseModel):
    active: bool


@router.patch("/{hazard_type_id}/active")
def set_hazard_type_active(hazard_type_id: str, body: SetActiveRequest) -> dict[str, Any]:
    repo = _repo()
    existing = repo.find_one({"hazard_type_id": hazard_type_id})
    if existing is None:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    repo.update_one(existing["_id"], {"is_active": body.active})
    doc = repo.find_by_id(existing["_id"])
    return _normalize(doc) if doc else {}
