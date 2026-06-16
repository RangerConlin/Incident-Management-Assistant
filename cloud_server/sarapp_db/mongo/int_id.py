"""Integer ID helpers for MongoDB collections that need sequential int IDs."""

from __future__ import annotations


def _ensure_int_ids(col) -> int:
    """Backfill int_id on any documents that are missing it. Returns current max."""
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    counter = int(max_doc["int_id"]) if max_doc else 0
    for doc in col.find({"int_id": {"$exists": False}}):
        counter += 1
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": counter}})
    return counter


def next_int_id(col) -> int:
    """Return the next available int_id for a collection."""
    max_doc = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (int(max_doc["int_id"]) if max_doc else 0) + 1
