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


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip Mongo's _id and alias int_id -> id for the Qt UI layer.

    Every list/get/create/update endpoint in this router must pass its
    result through here: the panels, dialogs, and controller all key off
    `row["id"]`, not the Mongo-native `int_id`.
    """
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    doc["id"] = doc.get("int_id")
    return doc


# ---------------------------------------------------------------------------
# Organization Types
# ---------------------------------------------------------------------------

DEFAULT_ORGANIZATION_TYPES: list[tuple[str, str]] = [
    ("Air Agency", "Aviation-based response organization (fixed-wing, rotor, UAS)."),
    ("Ground SAR", "Ground search and rescue team or unit."),
    ("Law Enforcement", "Police, sheriff, or other law enforcement agency."),
    ("Fire/Rescue", "Fire department or fire/rescue agency."),
    ("EMS", "Emergency medical services provider."),
    ("Government", "General government agency or department."),
    ("Volunteer Organization", "Volunteer-staffed response or support organization."),
    ("NGO", "Non-governmental organization providing support or relief services."),
    ("Federal", "Federal government agency."),
    ("State", "State government agency."),
    ("County", "County government agency."),
    ("Municipal", "City or municipal government agency."),
    ("Military", "Military or National Guard unit."),
    ("Private Contractor", "Privately contracted resource or support provider."),
    ("Amateur Radio", "Amateur radio operator group (e.g. ARES, RACES)."),
    ("Aviation Support", "Ground support for aviation operations (fuel, maintenance, base ops)."),
    ("Communications Unit", "Dedicated communications support unit."),
    ("Other", "Organization type not covered by another category."),
]

_default_types_seeded = False


def _seed_default_types_if_needed(col) -> None:
    """Idempotently insert the canonical default organization types.

    Guarded by a process-level flag so this only queries Mongo once per
    process; safe to call on every request like the index-creation helpers
    in mongo/indexes.py.
    """
    global _default_types_seeded
    if _default_types_seeded:
        return
    existing = {d.get("name") for d in col.find({}, {"name": 1})}
    for name, description in DEFAULT_ORGANIZATION_TYPES:
        if name in existing:
            continue
        col.insert_one({
            "int_id": _next_int_id(col),
            "name": name,
            "description": description,
            "is_active": 1,
            "sort_order": 0,
            "created_at": _utcnow(),
        })
    _default_types_seeded = True


@router.get("/types")
def list_org_types(search: str = "") -> list[dict[str, Any]]:
    col = _org_types_col()
    _seed_default_types_if_needed(col)
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    return [_serialize(d) for d in docs]


@router.post("/types", status_code=201)
def create_org_type(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _org_types_col()
    doc = {
        "int_id": _next_int_id(col),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "is_active": body.get("is_active", 1),
        "sort_order": body.get("sort_order", 0),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    return _serialize(doc)


@router.get("/types/{type_id}")
def get_org_type(type_id: int) -> dict[str, Any]:
    doc = _org_types_col().find_one({"int_id": type_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization type not found")
    return _serialize(doc)


@router.patch("/types/{type_id}")
def update_org_type(type_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _org_types_col()
    updates = {}
    for field in ("name", "description", "is_active", "sort_order"):
        if field in body:
            updates[field] = body[field]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = col.update_one({"int_id": type_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Organization type not found")
    doc = col.find_one({"int_id": type_id})
    return _serialize(doc)


@router.delete("/types/{type_id}", status_code=204)
def delete_org_type(type_id: int) -> None:
    result = _org_types_col().delete_one({"int_id": type_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Organization type not found")


# ---------------------------------------------------------------------------
# Rank Structures
# ---------------------------------------------------------------------------

# Each entry: (structure name, linked organization type name, ranks lowest-to-highest)
DEFAULT_RANK_STRUCTURES: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    ("Fire Department (Standard)", "Fire/Rescue", [
        ("FF", "Firefighter", "FF"),
        ("ENG", "Engineer/Driver", "ENG"),
        ("LT", "Lieutenant", "LT"),
        ("CPT", "Captain", "CPT"),
        ("BC", "Battalion Chief", "BC"),
        ("DC", "Deputy Chief", "DC"),
        ("CHIEF", "Fire Chief", "CHIEF"),
    ]),
    ("Law Enforcement (Standard)", "Law Enforcement", [
        ("OFC", "Officer", "OFC"),
        ("CPL", "Corporal", "CPL"),
        ("SGT", "Sergeant", "SGT"),
        ("LT", "Lieutenant", "LT"),
        ("CPT", "Captain", "CPT"),
        ("DC", "Deputy Chief", "DC"),
        ("CHIEF", "Chief", "CHIEF"),
    ]),
    ("EMS (Standard)", "EMS", [
        ("EMT", "EMT", "EMT"),
        ("AEMT", "Advanced EMT", "AEMT"),
        ("PARA", "Paramedic", "PARA"),
        ("SUP", "Supervisor", "SUP"),
        ("CPT", "EMS Captain", "CPT"),
        ("CHIEF", "EMS Chief", "CHIEF"),
    ]),
    ("Search and Rescue (Standard)", "Ground SAR", [
        ("TM", "Team Member", "TM"),
        ("ATL", "Assistant Team Leader", "ATL"),
        ("TL", "Team Leader", "TL"),
        ("OPS", "Operations Leader", "OPS"),
        ("IC", "Incident Commander", "IC"),
    ]),
    ("Volunteer / NGO (Standard)", "Volunteer Organization", [
        ("VOL", "Volunteer", "VOL"),
        ("SVOL", "Senior Volunteer", "SVOL"),
        ("TL", "Team Lead", "TL"),
        ("COORD", "Coordinator", "COORD"),
        ("DIR", "Director", "DIR"),
    ]),
    ("Civil Air Patrol (Standard)", "Air Agency", [
        ("CADET", "Cadet", "CADET"),
        ("2LT", "Second Lieutenant", "2d Lt"),
        ("1LT", "First Lieutenant", "1st Lt"),
        ("CAPT", "Captain", "Capt"),
        ("MAJ", "Major", "Maj"),
        ("LTC", "Lieutenant Colonel", "Lt Col"),
        ("COL", "Colonel", "Col"),
    ]),
]

_default_rank_structures_seeded = False


def _seed_default_rank_structures_if_needed(col) -> None:
    """Idempotently insert the canonical rank structure templates and ranks."""
    global _default_rank_structures_seeded
    if _default_rank_structures_seeded:
        return
    _seed_default_types_if_needed(_org_types_col())
    existing = {d.get("name") for d in col.find({}, {"name": 1})}
    for name, org_type_name, ranks in DEFAULT_RANK_STRUCTURES:
        if name in existing:
            continue
        type_doc = _org_types_col().find_one({"name": org_type_name}, {"int_id": 1})
        doc = {
            "int_id": _next_int_id(col),
            "name": name,
            "description": f"Standard rank structure for {org_type_name} organizations.",
            "organization_type_id": type_doc.get("int_id") if type_doc else None,
            "is_template": 1,
            "is_system_template": 1,
            "is_active": 1,
            "sort_order": 0,
            "created_at": _utcnow(),
        }
        col.insert_one(doc)
        for idx, (rank_code, rank_name, short_display) in enumerate(ranks):
            _ranks_col().insert_one({
                "int_id": _next_int_id(_ranks_col()),
                "rank_structure_id": doc["int_id"],
                "rank_code": rank_code,
                "rank_name": rank_name,
                "short_display": short_display,
                "sort_order": idx,
                "is_active": 1,
                "created_at": _utcnow(),
            })
    _default_rank_structures_seeded = True


def _org_type_name(org_type_id: int | None) -> str | None:
    if org_type_id is None:
        return None
    doc = _org_types_col().find_one({"int_id": org_type_id}, {"name": 1})
    return doc.get("name") if doc else None


def _enrich_rank_structure(doc: dict[str, Any]) -> dict[str, Any]:
    doc = _serialize(doc)
    doc["organization_type_name"] = _org_type_name(doc.get("organization_type_id"))
    return doc


@router.get("/rank-structures")
def list_rank_structures(search: str = "") -> list[dict[str, Any]]:
    col = _rank_structures_col()
    _seed_default_rank_structures_if_needed(col)
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    return [_enrich_rank_structure(d) for d in docs]


@router.post("/rank-structures", status_code=201)
def create_rank_structure(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _rank_structures_col()
    doc = {
        "int_id": _next_int_id(col),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "organization_type_id": body.get("organization_type_id"),
        "is_template": body.get("is_template", 0),
        "is_system_template": body.get("is_system_template", 0),
        "is_active": body.get("is_active", 1),
        "sort_order": body.get("sort_order", 0),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    ranks = body.get("ranks") or []
    for idx, rank in enumerate(ranks):
        _ranks_col().insert_one({
            "int_id": _next_int_id(_ranks_col()),
            "rank_structure_id": doc["int_id"],
            "rank_code": rank.get("rank_code", ""),
            "rank_name": rank.get("rank_name", ""),
            "short_display": rank.get("short_display", ""),
            "sort_order": rank.get("sort_order", idx),
            "is_active": rank.get("is_active", 1),
            "created_at": _utcnow(),
        })
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    return _enrich_rank_structure(doc)


@router.get("/rank-structures/{structure_id}")
def get_rank_structure(structure_id: int) -> dict[str, Any]:
    doc = _rank_structures_col().find_one({"int_id": structure_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    return _enrich_rank_structure(doc)


@router.patch("/rank-structures/{structure_id}")
def update_rank_structure(
    structure_id: int,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    col = _rank_structures_col()
    updates = {}
    for field in (
        "name", "description", "organization_type_id",
        "is_template", "is_system_template", "is_active", "sort_order",
    ):
        if field in body:
            updates[field] = body[field]
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
    return _enrich_rank_structure(doc)


@router.delete("/rank-structures/{structure_id}", status_code=204)
def delete_rank_structure(structure_id: int) -> None:
    result = _rank_structures_col().delete_one({"int_id": structure_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    _ranks_col().delete_many({"rank_structure_id": structure_id})
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": structure_id,
        "action": "delete",
        "timestamp": _utcnow(),
    })


@router.post("/rank-structures/{structure_id}/duplicate")
def duplicate_rank_structure(structure_id: int, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    col = _rank_structures_col()
    src = col.find_one({"int_id": structure_id})
    if not src:
        raise HTTPException(status_code=404, detail="Rank structure not found")
    new_doc = {
        "int_id": _next_int_id(col),
        "name": body.get("name") or f"{src.get('name')} (Copy)",
        "description": src.get("description"),
        "organization_type_id": body.get("organization_type_id", src.get("organization_type_id")),
        "is_template": int(bool(body.get("is_template", src.get("is_template", 0)))),
        "is_system_template": 0,
        "is_active": src.get("is_active", 1),
        "sort_order": src.get("sort_order", 0),
        "created_at": _utcnow(),
    }
    col.insert_one(new_doc)
    for rank in _ranks_col().find({"rank_structure_id": structure_id}).sort("sort_order", 1):
        _ranks_col().insert_one({
            "int_id": _next_int_id(_ranks_col()),
            "rank_structure_id": new_doc["int_id"],
            "rank_code": rank.get("rank_code", ""),
            "rank_name": rank.get("rank_name", ""),
            "short_display": rank.get("short_display", ""),
            "sort_order": rank.get("sort_order", 0),
            "is_active": rank.get("is_active", 1),
            "created_at": _utcnow(),
        })
    _rank_audit_col().insert_one({
        "_id": _new_id(),
        "rank_structure_id": new_doc["int_id"],
        "action": "duplicate",
        "source_id": structure_id,
        "timestamp": _utcnow(),
    })
    return _enrich_rank_structure(new_doc)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

_ORGANIZATION_FIELDS = (
    "name", "short_name", "parent_organization_id", "organization_type_id",
    "default_rank_structure_id", "is_active", "notes", "external_id",
    "callsign_prefix", "sort_order",
)


def _effective_rank_structure_id(col, doc: dict[str, Any]) -> int | None:
    """Walk the parent chain when this org has no rank structure of its own."""
    seen: set[int] = set()
    current = doc
    while current is not None:
        explicit = current.get("default_rank_structure_id")
        if explicit is not None:
            return explicit
        parent_id = current.get("parent_organization_id")
        if parent_id is None or parent_id in seen:
            return None
        seen.add(parent_id)
        current = col.find_one({"int_id": parent_id})
    return None


def _enrich_organization(col, doc: dict[str, Any]) -> dict[str, Any]:
    effective_id = _effective_rank_structure_id(col, doc)
    doc = _serialize(doc)
    doc["effective_rank_structure_id"] = effective_id
    doc["rank_structure_inherited"] = (
        effective_id is not None and doc.get("default_rank_structure_id") is None
    )
    if effective_id is not None:
        rs = _rank_structures_col().find_one({"int_id": effective_id}, {"name": 1})
        doc["effective_rank_structure_name"] = rs.get("name") if rs else None
    else:
        doc["effective_rank_structure_name"] = None
    return doc


@router.get("/organizations")
def list_organizations(search: str = "") -> list[dict[str, Any]]:
    col = _organizations_col()
    query = {} if not search else {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"short_name": {"$regex": search, "$options": "i"}},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    return [_enrich_organization(col, d) for d in docs]


@router.post("/organizations", status_code=201)
def create_organization(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _organizations_col()
    doc = {"int_id": _next_int_id(col)}
    for field in _ORGANIZATION_FIELDS:
        doc[field] = body.get(field)
    if doc.get("is_active") is None:
        doc["is_active"] = 1
    if doc.get("sort_order") is None:
        doc["sort_order"] = 0
    doc["created_at"] = _utcnow()
    col.insert_one(doc)
    _org_audit_col().insert_one({
        "_id": _new_id(),
        "organization_id": doc["int_id"],
        "action": "create",
        "timestamp": _utcnow(),
    })
    return _enrich_organization(col, doc)


@router.get("/organizations/{org_id}")
def get_organization(org_id: int) -> dict[str, Any]:
    col = _organizations_col()
    doc = col.find_one({"int_id": org_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _enrich_organization(col, doc)


@router.patch("/organizations/{org_id}")
def update_organization(org_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _organizations_col()
    updates = {field: body[field] for field in _ORGANIZATION_FIELDS if field in body}
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
    return _enrich_organization(col, doc)


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
            {"rank_name": {"$regex": search, "$options": "i"}},
            {"rank_code": {"$regex": search, "$options": "i"}},
        ]
    docs = list(col.find(query).sort("sort_order", 1))
    return [_serialize(d) for d in docs]


@router.post("/ranks", status_code=201)
def create_rank(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _ranks_col()
    doc = {
        "int_id": _next_int_id(col),
        "rank_structure_id": body.get("rank_structure_id"),
        "rank_code": body.get("rank_code", ""),
        "rank_name": body.get("rank_name", ""),
        "short_display": body.get("short_display", ""),
        "sort_order": body.get("sort_order", 0),
        "is_active": body.get("is_active", 1),
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    return _serialize(doc)


@router.get("/ranks/{rank_id}")
def get_rank(rank_id: int) -> dict[str, Any]:
    doc = _ranks_col().find_one({"int_id": rank_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Rank not found")
    return _serialize(doc)


@router.patch("/ranks/{rank_id}")
def update_rank(rank_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _ranks_col()
    updates = {}
    for field in ("rank_code", "rank_name", "short_display", "sort_order", "is_active"):
        if field in body:
            updates[field] = body[field]
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = col.update_one({"int_id": rank_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rank not found")
    doc = col.find_one({"int_id": rank_id})
    return _serialize(doc)


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
