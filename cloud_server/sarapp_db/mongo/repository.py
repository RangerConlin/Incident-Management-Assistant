"""
Generic base repository for SARApp MongoDB collections.

Provides common CRUD operations reusable by all module-specific repositories.
Module repositories should subclass BaseRepository and set `collection_name`.

Design decisions:
    - All document IDs are strings (UUID4). No reliance on MongoDB ObjectId.
    - Records are never hard-deleted by default. soft_delete sets deleted=True.
    - updated_at is managed here when the caller requests it.
    - Pagination is offset-based (skip/limit) for simplicity.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from sarapp_db.mongo.errors import RepositoryError

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


class BaseRepository:
    """
    Generic MongoDB repository.

    Subclass and set `collection_name` to build a module-specific repository.
    """

    collection_name: str = ""

    def __init__(self, db: Database) -> None:
        if not self.collection_name:
            raise RepositoryError(f"{self.__class__.__name__} must define collection_name.")
        self._db = db
        self._col = db[self.collection_name]

    def insert_one(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a document, generating a string _id if one is not provided."""
        doc = dict(document)
        if "_id" not in doc or not doc["_id"]:
            doc["_id"] = _new_id()
        now = _utcnow_iso()
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        doc.setdefault("deleted", False)
        try:
            self._col.insert_one(doc)
        except Exception as exc:
            raise RepositoryError(f"insert_one failed on '{self.collection_name}': {exc}") from exc
        return doc

    def update_one(
        self,
        doc_id: str,
        updates: Dict[str, Any],
        *,
        touch_updated_at: bool = True,
    ) -> bool:
        """Apply $set updates to the document with the given _id."""
        if touch_updated_at:
            updates = {**updates, "updated_at": _utcnow_iso()}
        try:
            result = self._col.update_one({"_id": doc_id}, {"$set": updates})
        except Exception as exc:
            raise RepositoryError(f"update_one failed on '{self.collection_name}' id='{doc_id}': {exc}") from exc
        return result.matched_count > 0

    def soft_delete(self, doc_id: str) -> bool:
        """Mark a document as deleted without removing it from the collection."""
        return self.update_one(doc_id, {"deleted": True}, touch_updated_at=True)

    def find_one(
        self,
        query: Dict[str, Any],
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Return the first document matching query, or None."""
        if not include_deleted:
            query = {**query, "deleted": False}
        try:
            return self._col.find_one(query)
        except Exception as exc:
            raise RepositoryError(f"find_one failed on '{self.collection_name}': {exc}") from exc

    def find_by_id(self, doc_id: str, *, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Return a document by its string _id."""
        return self.find_one({"_id": doc_id}, include_deleted=include_deleted)

    def find_many(
        self,
        query: Dict[str, Any],
        *,
        include_deleted: bool = False,
        sort: Optional[List] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return all documents matching query."""
        if not include_deleted:
            query = {**query, "deleted": False}
        try:
            cursor = self._col.find(query)
            if sort:
                cursor = cursor.sort(sort)
            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as exc:
            raise RepositoryError(f"find_many failed on '{self.collection_name}': {exc}") from exc

    def count(self, query: Optional[Dict[str, Any]] = None, *, include_deleted: bool = False) -> int:
        """Return the number of documents matching query."""
        q: Dict[str, Any] = query or {}
        if not include_deleted:
            q = {**q, "deleted": False}
        try:
            return self._col.count_documents(q)
        except Exception as exc:
            raise RepositoryError(f"count failed on '{self.collection_name}': {exc}") from exc

    def paginate(
        self,
        query: Dict[str, Any],
        *,
        page: int = 1,
        page_size: int = 50,
        sort: Optional[List] = None,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """Return a page of results with pagination metadata."""
        page = max(1, page)
        page_size = max(1, page_size)
        skip = (page - 1) * page_size
        total = self.count(query, include_deleted=include_deleted)
        items = self.find_many(query, include_deleted=include_deleted, sort=sort, skip=skip, limit=page_size)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {"items": items, "page": page, "page_size": page_size, "total": total, "total_pages": total_pages}
