"""Reference library router — documents and collections in master MongoDB."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.mongo.database_manager import DB_MASTER

router = APIRouter()


def _docs_col():
    return get_client()[DB_MASTER]["library_documents"]


def _cols_col():
    return get_client()[DB_MASTER]["library_collections"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _next_int_id(col) -> int:
    doc = list(col.find().sort("int_id", -1).limit(1))
    return (doc[0].get("int_id", 0) if doc else 0) + 1


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/documents")
def list_documents(
    category: str = "",
    search: str = "",
    archived: bool = False,
) -> list[dict[str, Any]]:
    col = _docs_col()
    query: dict[str, Any] = {"archived": {"$ne": True}} if not archived else {}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
            {"agency": {"$regex": search, "$options": "i"}},
        ]
    docs = list(col.find(query).sort("title", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/documents", status_code=201)
def add_document(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _docs_col()
    now = _utcnow()
    doc = {
        "_id": _new_id(),
        "int_id": _next_int_id(col),
        "title": body.get("title", ""),
        "category": body.get("category", ""),
        "subcategory": body.get("subcategory"),
        "tags": body.get("tags") or [],
        "agency": body.get("agency"),
        "jurisdiction": body.get("jurisdiction"),
        "description": body.get("description"),
        "file_path": body.get("file_path", ""),
        "file_hash": body.get("file_hash", ""),
        "file_ext": body.get("file_ext"),
        "file_size": body.get("file_size"),
        "version": body.get("version"),
        "archived": False,
        "created_by": body.get("created_by"),
        "modified_by": body.get("created_by"),
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/documents/{doc_id}")
def get_document(doc_id: int) -> dict[str, Any]:
    doc = _docs_col().find_one({"int_id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.pop("_id", None)
    return doc


@router.patch("/documents/{doc_id}")
def update_document(doc_id: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _docs_col()
    updates = {k: v for k, v in body.items() if k not in ("int_id", "_id", "created_at", "created_by")}
    updates["updated_at"] = _utcnow()
    result = col.update_one({"int_id": doc_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = col.find_one({"int_id": doc_id})
    doc.pop("_id", None)
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
def archive_document(doc_id: int) -> None:
    result = _docs_col().update_one({"int_id": doc_id}, {"$set": {"archived": True, "updated_at": _utcnow()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@router.get("/collections")
def list_collections() -> list[dict[str, Any]]:
    docs = list(_cols_col().find().sort("name", 1))
    for d in docs:
        d.pop("_id", None)
    return docs


@router.post("/collections", status_code=201)
def create_collection(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    col = _cols_col()
    doc = {
        "_id": _new_id(),
        "int_id": _next_int_id(col),
        "name": body.get("name", ""),
        "description": body.get("description"),
        "created_by": body.get("created_by"),
        "document_ids": [],
        "created_at": _utcnow(),
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/collections/{collection_id}/documents/{doc_id}", status_code=204)
def link_document_to_collection(collection_id: int, doc_id: int) -> None:
    col = _cols_col()
    result = col.update_one(
        {"int_id": collection_id},
        {"$addToSet": {"document_ids": doc_id}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Collection not found")


@router.delete("/collections/{collection_id}/documents/{doc_id}", status_code=204)
def unlink_document_from_collection(collection_id: int, doc_id: int) -> None:
    _cols_col().update_one(
        {"int_id": collection_id},
        {"$pull": {"document_ids": doc_id}},
    )
