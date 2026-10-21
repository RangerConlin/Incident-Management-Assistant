"""One-time migration from teams.members_json to member_person_records.

Run this before deploying clients that use the mobile participation context.
The production application intentionally reads only the canonical array.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository


class TeamsRepository(BaseRepository):
    collection_name = IncidentCollections.TEAMS
    soft_deletes = False


def _member_ids(value: Any) -> list[int]:
    if isinstance(value, str):
        value = json.loads(value or "[]")
    if not isinstance(value, list):
        return []
    return sorted({int(item) for item in value})


def migrate(incident_id: str) -> int:
    repo = TeamsRepository(get_incident_db(incident_id))
    changed = 0
    for team in repo.find_many({"members_json": {"$exists": True}}):
        repo.apply_update(
            team["_id"],
            {
                "$set": {"member_person_records": _member_ids(team.get("members_json"))},
                "$unset": {"members_json": ""},
            },
        )
        changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incident_id")
    args = parser.parse_args()
    print(f"Migrated {migrate(args.incident_id)} team records.")


if __name__ == "__main__":
    main()
