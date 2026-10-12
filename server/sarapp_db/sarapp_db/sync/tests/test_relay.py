"""Unit tests for apply_incoming's pure last-write-wins policy."""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.sync.relay import apply_incoming

DB_NAME = "TEST_SYNC_RELAY_DB"
COLLECTION = "personnel"


def _db():
    return get_client()[DB_NAME]


def _reset():
    get_client().drop_database(DB_NAME)


def test_apply_incoming_inserts_new_document():
    _reset()
    try:
        doc = {"_id": "p1", "name": "Alice", "updated_at": "2026-01-01T00:00:00"}
        result = apply_incoming(_db(), COLLECTION, doc)

        assert result == "inserted"
        assert _db()[COLLECTION].find_one({"_id": "p1"})["name"] == "Alice"
    finally:
        _reset()


def test_apply_incoming_overwrites_when_incoming_is_newer():
    _reset()
    try:
        _db()[COLLECTION].insert_one({"_id": "p1", "name": "Alice", "updated_at": "2026-01-01T00:00:00"})

        result = apply_incoming(
            _db(), COLLECTION, {"_id": "p1", "name": "Alice Updated", "updated_at": "2026-01-02T00:00:00"}
        )

        assert result == "applied"
        assert _db()[COLLECTION].find_one({"_id": "p1"})["name"] == "Alice Updated"
    finally:
        _reset()


def test_apply_incoming_skips_identical_resend():
    _reset()
    try:
        doc = {"_id": "p1", "name": "Alice", "updated_at": "2026-01-01T00:00:00"}
        _db()[COLLECTION].insert_one(doc)

        result = apply_incoming(_db(), COLLECTION, dict(doc))

        assert result == "skipped_same_or_older"
    finally:
        _reset()


def test_apply_incoming_skips_when_existing_is_newer():
    """Pure last-write-wins: an older incoming edit never overwrites a
    newer existing one — no conflict is logged, it's just discarded."""
    _reset()
    try:
        _db()[COLLECTION].insert_one({"_id": "p1", "name": "Alice Newer", "updated_at": "2026-01-05T00:00:00"})

        result = apply_incoming(
            _db(), COLLECTION, {"_id": "p1", "name": "Alice Older Edit", "updated_at": "2026-01-02T00:00:00"}
        )

        assert result == "skipped_same_or_older"
        assert _db()[COLLECTION].find_one({"_id": "p1"})["name"] == "Alice Newer"
    finally:
        _reset()


def test_apply_incoming_applies_on_tied_timestamp():
    """When timestamps are exactly equal, the incoming write still wins —
    ties don't favor the existing document."""
    _reset()
    try:
        _db()[COLLECTION].insert_one({"_id": "p1", "name": "Alice", "updated_at": "2026-01-05T00:00:00"})

        result = apply_incoming(
            _db(), COLLECTION, {"_id": "p1", "name": "Alice Tied Edit", "updated_at": "2026-01-05T00:00:00"}
        )

        assert result == "applied"
        assert _db()[COLLECTION].find_one({"_id": "p1"})["name"] == "Alice Tied Edit"
    finally:
        _reset()


def test_apply_incoming_tombstone_deletes_existing_document():
    _reset()
    try:
        _db()[COLLECTION].insert_one({"_id": "p1", "name": "Alice", "updated_at": "2026-01-01T00:00:00"})

        result = apply_incoming(_db(), COLLECTION, {"_id": "p1", "deleted": True, "updated_at": "2026-01-02T00:00:00"})

        assert result == "deleted"
        assert _db()[COLLECTION].find_one({"_id": "p1"}) is None
    finally:
        _reset()


def test_apply_incoming_tombstone_for_already_absent_document_is_a_noop():
    _reset()
    try:
        result = apply_incoming(_db(), COLLECTION, {"_id": "never-existed", "deleted": True, "updated_at": "2026-01-01T00:00:00"})

        assert result == "already_absent"
    finally:
        _reset()


def test_apply_incoming_tombstone_loses_to_a_strictly_later_edit():
    """Last-write-wins applies to edit-vs-delete races too: an edit made
    strictly after the deletion survives, the delete is simply discarded."""
    _reset()
    try:
        _db()[COLLECTION].insert_one({"_id": "p1", "name": "Alice Edited Later", "updated_at": "2026-01-05T00:00:00"})

        result = apply_incoming(_db(), COLLECTION, {"_id": "p1", "deleted": True, "updated_at": "2026-01-02T00:00:00"})

        assert result == "skipped_same_or_older"
        assert _db()[COLLECTION].find_one({"_id": "p1"})["name"] == "Alice Edited Later"
    finally:
        _reset()


def test_apply_incoming_is_idempotent_for_repeated_pulls():
    _reset()
    try:
        doc = {"_id": "p1", "name": "Alice", "updated_at": "2026-01-02T00:00:00"}
        apply_incoming(_db(), COLLECTION, doc)

        # Re-applying the exact same doc a second time (e.g. a retried pull)
        # is a harmless no-op.
        result = apply_incoming(_db(), COLLECTION, dict(doc))

        assert result == "skipped_same_or_older"
    finally:
        _reset()
