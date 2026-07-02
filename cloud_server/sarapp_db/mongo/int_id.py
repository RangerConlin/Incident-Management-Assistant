"""Sequential integer record-ID helpers for MongoDB collections."""

from __future__ import annotations


def _ensure_record_ids(col, field: str) -> int:
    """Backfill *_record on any documents missing it. Returns current max."""
    max_doc = col.find_one({field: {"$exists": True}}, sort=[(field, -1)])
    counter = int(max_doc[field]) if max_doc else 0
    for doc in col.find({field: {"$exists": False}}):
        counter += 1
        col.update_one({"_id": doc["_id"]}, {"$set": {field: counter}})
    return counter


def next_record_id(col, field: str) -> int:
    """Return the next available record ID for a collection."""
    max_doc = col.find_one({field: {"$exists": True}}, sort=[(field, -1)])
    return (int(max_doc[field]) if max_doc else 0) + 1


def next_int_id(col, field: str = "int_id") -> int:
    """Return the next available integer ID for a collection (default field: int_id)."""
    max_doc = col.find_one({field: {"$exists": True}}, sort=[(field, -1)])
    return (int(max_doc[field]) if max_doc else 0) + 1


def _ensure_int_ids(col, field: str = "int_id") -> int:
    """Backfill int_id on any documents missing it. Returns current max."""
    return _ensure_record_ids(col, field)
