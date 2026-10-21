"""Unit coverage for the backfill_resource_type_kind one-time migration.

Requires a live MongoDB reachable via SARAPP_MONGO_URI (see repo test
conventions) -- there is no in-process fake for the Mongo layer in this
codebase.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.migrations.backfill_resource_type_kind import backfill_resource_type_kind
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

_IDS = ["TEST-BF-KIND-1", "TEST-BF-KIND-2", "TEST-BF-KIND-3", "TEST-BF-KIND-4"]


def _reset():
    get_master_db()[MasterCollections.RESOURCE_TYPES].delete_many({"_id": {"$in": _IDS}})


def test_backfill_defaults_kind_from_resource_name_then_name_and_skips_existing():
    _reset()
    try:
        col = get_master_db()[MasterCollections.RESOURCE_TYPES]
        col.insert_many(
            [
                {
                    "_id": "TEST-BF-KIND-1",
                    "resource_type_id": "900001",
                    "name": "engine-1",
                    "resource_name": "Fire Engine",
                    # no kind at all
                },
                {
                    "_id": "TEST-BF-KIND-2",
                    "resource_type_id": "900002",
                    "name": "Type III Engine",
                    "resource_name": "",
                    "kind": "",
                },
                {
                    "_id": "TEST-BF-KIND-3",
                    "resource_type_id": "900003",
                    "name": "Already Classified",
                    "resource_name": "Already Classified",
                    "kind": "Custom Kind",
                },
                {
                    "_id": "TEST-BF-KIND-4",
                    "resource_type_id": "900004",
                    "name": "",
                    "resource_name": "",
                    "kind": None,
                },
            ]
        )

        updated = backfill_resource_type_kind(dry_run=False)
        assert updated >= 2

        assert col.find_one({"_id": "TEST-BF-KIND-1"})["kind"] == "Fire Engine"
        assert col.find_one({"_id": "TEST-BF-KIND-2"})["kind"] == "Type III Engine"
        # Already-classified record must never be overwritten.
        assert col.find_one({"_id": "TEST-BF-KIND-3"})["kind"] == "Custom Kind"
        # No name/resource_name at all -> no invented data, left untouched.
        assert col.find_one({"_id": "TEST-BF-KIND-4"})["kind"] is None

        # Idempotent: a second run changes nothing further.
        updated_again = backfill_resource_type_kind(dry_run=False)
        assert updated_again == 0
    finally:
        _reset()


def test_dry_run_does_not_write():
    _reset()
    try:
        col = get_master_db()[MasterCollections.RESOURCE_TYPES]
        col.insert_one(
            {
                "_id": "TEST-BF-KIND-1",
                "resource_type_id": "900001",
                "name": "engine-1",
                "resource_name": "Fire Engine",
            }
        )
        would_update = backfill_resource_type_kind(dry_run=True)
        assert would_update == 1
        assert "kind" not in col.find_one({"_id": "TEST-BF-KIND-1"})
    finally:
        _reset()
