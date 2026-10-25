from __future__ import annotations

from sarapp_db.migrations.migrate_team_type_presentation import migrate
from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.mongo_client import get_client


def test_migration_converts_keys_and_removes_scope_fields() -> None:
    db = get_client()["test_team_type_presentation_migration"]
    collection = db[MasterCollections.TEAM_TYPES]
    collection.delete_many({})
    try:
        collection.insert_one({
            "_id": "legacy-team-type", "type_short": "GT", "scope": "system",
            "organization_id": None, "color_key": "team_type_search_rescue",
            "text_color_key": "team_text_white", "icon_key": "direction_finding",
        })

        assert migrate(db=db) == {"team_types_converted": 1}
        row = collection.find_one({"_id": "legacy-team-type"})
        assert row["background_color"] == "#228b22"
        assert row["text_color"] == "#ffffff"
        assert row["icon_key"] == "df"
        for retired in ("scope", "organization_id", "color_key", "text_color_key"):
            assert retired not in row

        assert migrate(db=db) == {"team_types_converted": 0}
    finally:
        collection.delete_many({})
