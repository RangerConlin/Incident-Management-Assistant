"""Coverage for the one-time Team Type Catalog seed migration."""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.migrations.seed_team_types import (  # noqa: E402
    _CAPABILITIES,
    _TEAM_TYPES,
    seed_team_types,
)
from sarapp_db.mongo.collection_names import MasterCollections  # noqa: E402
from sarapp_db.mongo.database_manager import get_client  # noqa: E402

_TEST_DB_NAME = "TEST_TEAM_TYPE_SEED"


def _db():
    return get_client()[_TEST_DB_NAME]


def _reset() -> None:
    db = _db()
    codes = [definition["type_short"] for definition in _TEAM_TYPES]
    capability_names = [name for name, _category in _CAPABILITIES]
    db[MasterCollections.TEAM_TYPES].delete_many({"type_short": {"$in": codes}})
    db[MasterCollections.RESOURCE_CAPABILITIES].delete_many({"name": {"$in": capability_names}})


def test_seed_is_idempotent_and_preserves_existing_edits() -> None:
    _reset()
    try:
        db = _db()
        db[MasterCollections.TEAM_TYPES].insert_one(
            {
                "_id": "TEST-SEED-TEAM-TYPE-GT",
                "int_id": 900001,
                "name": "Locally Customized Ground Team",
                "type_short": "GT",
                "color_key": "team_type_general",
                "minimum_personnel": 99,
            }
        )

        first = seed_team_types(db=db)
        assert first["capabilities_inserted"] == len(_CAPABILITIES)
        assert first["team_types_inserted"] == len(_TEAM_TYPES) - 1
        assert first["team_types_upgraded"] == 1

        customized = db[MasterCollections.TEAM_TYPES].find_one({"type_short": "GT"})
        assert customized["name"] == "Locally Customized Ground Team"
        assert customized["color_key"] == "team_type_general"
        assert customized["minimum_personnel"] == 99
        assert customized["category"] == "Search & Rescue"
        assert customized["text_color_key"] == "team_text_auto"
        assert customized["capability_ids"]

        second = seed_team_types(db=db)
        assert second["capabilities_inserted"] == 0
        assert second["team_types_inserted"] == 0
        assert second["team_types_upgraded"] == 0
        assert second["team_types_skipped"] == len(_TEAM_TYPES)
    finally:
        _reset()


def test_seed_dry_run_does_not_write() -> None:
    _reset()
    try:
        db = _db()
        result = seed_team_types(db=db, dry_run=True)
        assert result["team_types_inserted"] == len(_TEAM_TYPES)
        assert db[MasterCollections.TEAM_TYPES].count_documents(
            {"type_short": {"$in": [definition["type_short"] for definition in _TEAM_TYPES]}}
        ) == 0
    finally:
        _reset()
