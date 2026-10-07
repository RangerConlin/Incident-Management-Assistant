"""Sequential integer record-ID helpers for MongoDB collections."""

from __future__ import annotations

from pymongo.database import Database


def dual_key_field(db: Database, local_field: str, master_field: str) -> str:
    """Pick which record-id field a collection should mint/query against,
    given this db: `master_field` on the central catalog, `local_field`
    everywhere else (a local catalog's own sarapp_master).

    This is the general form of the person_record/person_record_master
    pattern — see Design Documents/Instructions/mongodb_schema_decisions.md
    ("Personnel: central-vs-local record ids") for the full reasoning.
    Every other "dual-key" master collection follows the same shape with
    its own field names.
    """
    from sarapp_db.mongo.database_manager import is_central_master_db

    return master_field if is_central_master_db(db) else local_field


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
