"""FastAPI router — task_types and team_types lookup table CRUD."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class TaskTypesRepository(BaseRepository):
    collection_name = MasterCollections.TASK_TYPES
    # Keyed by sequential `int_id`, not `_id`; `is_active` is a plain
    # application flag used for soft-delete-by-convention here, not
    # BaseRepository's `deleted` field.
    soft_deletes = False


class TeamTypesRepository(BaseRepository):
    collection_name = MasterCollections.TEAM_TYPES
    soft_deletes = False


class IncidentTypesRepository(BaseRepository):
    collection_name = MasterCollections.INCIDENT_TYPES
    soft_deletes = False


def _task_types_repo() -> TaskTypesRepository:
    return TaskTypesRepository(get_master_db())


def _team_types_repo() -> TeamTypesRepository:
    return TeamTypesRepository(get_master_db())


def _incident_types_repo() -> IncidentTypesRepository:
    return IncidentTypesRepository(get_master_db())


def _ensure_int_ids(repo: BaseRepository) -> None:
    """Lazily assign sequential int_ids to seeded docs that lack them."""
    col = repo._col
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1


def _doc_to_row(doc: dict, extra_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": doc.get("int_id"),
        "name": doc.get("name", ""),
        "category": doc.get("category", ""),
        "description": doc.get("description", ""),
        "is_active": 1 if doc.get("is_active", True) else 0,
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }
    for f in extra_fields:
        row[f] = doc.get(f)
    return row


# ---------------------------------------------------------------------------
# Generic helpers shared by both endpoints
# ---------------------------------------------------------------------------

def _list_repo(repo: BaseRepository, filter_text: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
    _ensure_int_ids(repo)
    filt: dict[str, Any] = {}
    if not include_inactive:
        filt["is_active"] = {"$ne": False}
    docs = repo.find_many(filt, sort=[("name", 1)])
    if filter_text:
        term = filter_text.strip().lower()
        docs = [
            d for d in docs
            if term in (d.get("name") or "").lower()
            or term in (d.get("description") or "").lower()
            or term in (d.get("category") or "").lower()
        ]
    return docs


def _get_repo(repo: BaseRepository, int_id: int) -> dict | None:
    return repo.find_one({"int_id": int_id})


def _exists_repo(repo: BaseRepository, name: str, exclude_id: Optional[int] = None) -> bool:
    filt: dict[str, Any] = {"name": {"$regex": f"^{name}$", "$options": "i"}}
    if exclude_id is not None:
        filt["int_id"] = {"$ne": exclude_id}
    return repo.find_one(filt) is not None


def _create_repo(repo: BaseRepository, data: dict) -> int:
    _ensure_int_ids(repo)
    top = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    int_id = (top["int_id"] + 1) if top else 1
    doc = {
        "int_id": int_id,
        "name": (data.get("name") or "").strip(),
        "category": (data.get("category") or "").strip(),
        "description": (data.get("description") or "").strip(),
        "default_priority": data.get("default_priority", "Normal"),
        "is_active": True,
        **{k: v for k, v in data.items()
           if k not in ("name", "category", "description", "default_priority",
                        "is_active", "created_at", "updated_at")},
    }
    repo.insert_one(doc)
    return int_id


def _update_repo(repo: BaseRepository, int_id: int, data: dict) -> None:
    existing = repo.find_one({"int_id": int_id})
    if not existing:
        return
    update: dict[str, Any] = {}
    for field in ("name", "category", "description", "default_priority"):
        if field in data:
            update[field] = (data[field] or "").strip() if isinstance(data[field], str) else data[field]
    repo.update_one(existing["_id"], update)


def _soft_delete_repo(repo: BaseRepository, int_id: int) -> None:
    existing = repo.find_one({"int_id": int_id})
    if existing:
        repo.update_one(existing["_id"], {"is_active": False})


def _restore_repo(repo: BaseRepository, int_id: int) -> None:
    existing = repo.find_one({"int_id": int_id})
    if existing:
        repo.update_one(existing["_id"], {"is_active": True})


# ---------------------------------------------------------------------------
# Task-types request/response models
# ---------------------------------------------------------------------------

class UpsertLookupRequest(BaseModel):
    name: str
    category: str = ""
    description: str = ""
    default_priority: str = "Normal"
    is_active: Optional[int] = 1


# ---------------------------------------------------------------------------
# /api/lookup/task-types
# ---------------------------------------------------------------------------

@router.get("/task-types")
def list_task_types(filter_text: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
    repo = _task_types_repo()
    docs = _list_repo(repo, filter_text, include_inactive)
    return [
        {**_doc_to_row(d), "default_priority": d.get("default_priority", "Normal")}
        for d in docs
    ]


@router.get("/task-types/exists")
def task_type_exists(name: str, exclude_id: Optional[int] = None) -> dict[str, bool]:
    repo = _task_types_repo()
    return {"exists": _exists_repo(repo, name, exclude_id)}


@router.get("/task-types/{int_id}")
def get_task_type(int_id: int) -> dict[str, Any]:
    repo = _task_types_repo()
    doc = _get_repo(repo, int_id)
    if not doc:
        raise HTTPException(404, f"Task type {int_id} not found")
    return {**_doc_to_row(doc), "default_priority": doc.get("default_priority", "Normal")}


@router.post("/task-types", status_code=201)
def create_task_type(body: UpsertLookupRequest) -> dict[str, Any]:
    repo = _task_types_repo()
    int_id = _create_repo(repo, body.model_dump())
    return {"id": int_id}


@router.put("/task-types/{int_id}")
def update_task_type(int_id: int, body: UpsertLookupRequest) -> dict[str, Any]:
    repo = _task_types_repo()
    if not _get_repo(repo, int_id):
        raise HTTPException(404, f"Task type {int_id} not found")
    _update_repo(repo, int_id, body.model_dump())
    return {"ok": True}


@router.delete("/task-types/{int_id}")
def delete_task_type(int_id: int) -> dict[str, Any]:
    repo = _task_types_repo()
    _soft_delete_repo(repo, int_id)
    return {"ok": True}


@router.patch("/task-types/{int_id}/restore")
def restore_task_type(int_id: int) -> dict[str, Any]:
    repo = _task_types_repo()
    _restore_repo(repo, int_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# /api/lookup/team-types
# ---------------------------------------------------------------------------

_TEAM_EXTRA = ("type_short", "organization", "is_drone", "is_aviation")


@router.get("/team-types")
def list_team_types(filter_text: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
    repo = _team_types_repo()
    docs = _list_repo(repo, filter_text, include_inactive)
    return [_doc_to_row(d, _TEAM_EXTRA) for d in docs]


@router.get("/team-types/exists")
def team_type_exists(name: str, exclude_id: Optional[int] = None) -> dict[str, bool]:
    repo = _team_types_repo()
    return {"exists": _exists_repo(repo, name, exclude_id)}


@router.get("/team-types/{int_id}")
def get_team_type(int_id: int) -> dict[str, Any]:
    repo = _team_types_repo()
    doc = _get_repo(repo, int_id)
    if not doc:
        raise HTTPException(404, f"Team type {int_id} not found")
    return _doc_to_row(doc, _TEAM_EXTRA)


@router.post("/team-types", status_code=201)
def create_team_type(body: UpsertLookupRequest) -> dict[str, Any]:
    repo = _team_types_repo()
    int_id = _create_repo(repo, body.model_dump())
    return {"id": int_id}


@router.put("/team-types/{int_id}")
def update_team_type(int_id: int, body: UpsertLookupRequest) -> dict[str, Any]:
    repo = _team_types_repo()
    if not _get_repo(repo, int_id):
        raise HTTPException(404, f"Team type {int_id} not found")
    _update_repo(repo, int_id, body.model_dump())
    return {"ok": True}


@router.delete("/team-types/{int_id}")
def delete_team_type(int_id: int) -> dict[str, Any]:
    repo = _team_types_repo()
    _soft_delete_repo(repo, int_id)
    return {"ok": True}


@router.patch("/team-types/{int_id}/restore")
def restore_team_type(int_id: int) -> dict[str, Any]:
    repo = _team_types_repo()
    _restore_repo(repo, int_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# /api/lookup/incident-types
# ---------------------------------------------------------------------------

_DEFAULT_INCIDENT_TYPES = [
    "Agricultural Event", "Air Show / Fly-In", "Community Preparedness Fair",
    "Concert / Outdoor Entertainment", "County / State Fair",
    "Disaster Drill / ICS Exercise", "Disaster Shelter Operations",
    "Disaster Supply Distribution", "ELT Reports", "Earthquake Response",
    "Festival / Fair", "Flood Response", "Hurricane Response",
    "Ice Storm / Winter Emergency", "Major Infrastructure Failure",
    "Marathon / Race Event", "Missing Aircraft", "Missing Person",
    "Parade / March", "Public Demonstration / Rally", "Public Health Emergency",
    "Public Health Event (e.g., vaccine clinic)", "Sporting Event",
    "Tornado Response", "Wildfire Response",
]


@router.get("/incident-types")
def list_incident_types() -> list[str]:
    repo = _incident_types_repo()
    docs = repo.find_many({}, sort=[("name", 1)])
    if docs:
        return [d["name"] for d in docs if d.get("name")]
    return _DEFAULT_INCIDENT_TYPES
