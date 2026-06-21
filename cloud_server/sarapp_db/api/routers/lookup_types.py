"""FastAPI router — task_types and team_types lookup table CRUD."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.database_manager import get_client
from sarapp_db.mongo.collection_names import MasterCollections

router = APIRouter()

def _master_db():
    return get_client()["sarapp_master"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _ensure_int_ids(col) -> None:
    """Lazily assign sequential int_ids to seeded docs that lack them."""
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

def _list_col(col, filter_text: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
    _ensure_int_ids(col)
    filt: dict[str, Any] = {}
    if not include_inactive:
        filt["is_active"] = {"$ne": False}
    docs = list(col.find(filt).sort("name", 1))
    if filter_text:
        term = filter_text.strip().lower()
        docs = [
            d for d in docs
            if term in (d.get("name") or "").lower()
            or term in (d.get("description") or "").lower()
            or term in (d.get("category") or "").lower()
        ]
    return docs


def _get_col(col, int_id: int) -> dict | None:
    return col.find_one({"int_id": int_id})


def _exists_col(col, name: str, exclude_id: Optional[int] = None) -> bool:
    filt: dict[str, Any] = {"name": {"$regex": f"^{name}$", "$options": "i"}}
    if exclude_id is not None:
        filt["int_id"] = {"$ne": exclude_id}
    return col.find_one(filt) is not None


def _create_col(col, data: dict) -> int:
    _ensure_int_ids(col)
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    int_id = (top["int_id"] + 1) if top else 1
    now = _now()
    col.insert_one({
        "_id": _new_id(),
        "int_id": int_id,
        "name": (data.get("name") or "").strip(),
        "category": (data.get("category") or "").strip(),
        "description": (data.get("description") or "").strip(),
        "default_priority": data.get("default_priority", "Normal"),
        "is_active": True,
        "created_at": data.get("created_at") or now,
        "updated_at": data.get("updated_at") or now,
        **{k: v for k, v in data.items()
           if k not in ("name", "category", "description", "default_priority",
                        "is_active", "created_at", "updated_at")},
    })
    return int_id


def _update_col(col, int_id: int, data: dict) -> None:
    update: dict[str, Any] = {"updated_at": _now()}
    for field in ("name", "category", "description", "default_priority"):
        if field in data:
            update[field] = (data[field] or "").strip() if isinstance(data[field], str) else data[field]
    col.update_one({"int_id": int_id}, {"$set": update})


def _soft_delete_col(col, int_id: int) -> None:
    col.update_one({"int_id": int_id}, {"$set": {"is_active": False, "updated_at": _now()}})


def _restore_col(col, int_id: int) -> None:
    col.update_one({"int_id": int_id}, {"$set": {"is_active": True, "updated_at": _now()}})


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
    col = _master_db()[MasterCollections.TASK_TYPES]
    docs = _list_col(col, filter_text, include_inactive)
    return [
        {**_doc_to_row(d), "default_priority": d.get("default_priority", "Normal")}
        for d in docs
    ]


@router.get("/task-types/exists")
def task_type_exists(name: str, exclude_id: Optional[int] = None) -> dict[str, bool]:
    col = _master_db()[MasterCollections.TASK_TYPES]
    return {"exists": _exists_col(col, name, exclude_id)}


@router.get("/task-types/{int_id}")
def get_task_type(int_id: int) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TASK_TYPES]
    doc = _get_col(col, int_id)
    if not doc:
        raise HTTPException(404, f"Task type {int_id} not found")
    return {**_doc_to_row(doc), "default_priority": doc.get("default_priority", "Normal")}


@router.post("/task-types", status_code=201)
def create_task_type(body: UpsertLookupRequest) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TASK_TYPES]
    int_id = _create_col(col, body.model_dump())
    return {"id": int_id}


@router.put("/task-types/{int_id}")
def update_task_type(int_id: int, body: UpsertLookupRequest) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TASK_TYPES]
    if not _get_col(col, int_id):
        raise HTTPException(404, f"Task type {int_id} not found")
    _update_col(col, int_id, body.model_dump())
    return {"ok": True}


@router.delete("/task-types/{int_id}")
def delete_task_type(int_id: int) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TASK_TYPES]
    _soft_delete_col(col, int_id)
    return {"ok": True}


@router.patch("/task-types/{int_id}/restore")
def restore_task_type(int_id: int) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TASK_TYPES]
    _restore_col(col, int_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# /api/lookup/team-types
# ---------------------------------------------------------------------------

_TEAM_EXTRA = ("type_short", "organization", "is_drone", "is_aviation")


@router.get("/team-types")
def list_team_types(filter_text: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    docs = _list_col(col, filter_text, include_inactive)
    return [_doc_to_row(d, _TEAM_EXTRA) for d in docs]


@router.get("/team-types/exists")
def team_type_exists(name: str, exclude_id: Optional[int] = None) -> dict[str, bool]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    return {"exists": _exists_col(col, name, exclude_id)}


@router.get("/team-types/{int_id}")
def get_team_type(int_id: int) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    doc = _get_col(col, int_id)
    if not doc:
        raise HTTPException(404, f"Team type {int_id} not found")
    return _doc_to_row(doc, _TEAM_EXTRA)


@router.post("/team-types", status_code=201)
def create_team_type(body: UpsertLookupRequest) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    int_id = _create_col(col, body.model_dump())
    return {"id": int_id}


@router.put("/team-types/{int_id}")
def update_team_type(int_id: int, body: UpsertLookupRequest) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    if not _get_col(col, int_id):
        raise HTTPException(404, f"Team type {int_id} not found")
    _update_col(col, int_id, body.model_dump())
    return {"ok": True}


@router.delete("/team-types/{int_id}")
def delete_team_type(int_id: int) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    _soft_delete_col(col, int_id)
    return {"ok": True}


@router.patch("/team-types/{int_id}/restore")
def restore_team_type(int_id: int) -> dict[str, Any]:
    col = _master_db()[MasterCollections.TEAM_TYPES]
    _restore_col(col, int_id)
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
    col = _master_db()[MasterCollections.INCIDENT_TYPES]
    docs = list(col.find({}, {"_id": 0, "name": 1}).sort("name", 1))
    if docs:
        return [d["name"] for d in docs if d.get("name")]
    return _DEFAULT_INCIDENT_TYPES
