"""Remove retired personnel emergency blood-type and insurance fields.

Run once against each LAN/cloud server and once against the central catalog:

    python -m sarapp_db.migrations.remove_personnel_blood_type_and_insurance
    python -m sarapp_db.migrations.remove_personnel_blood_type_and_insurance --dry-run

The migration cleans the configured master personnel catalog and every
``sarapp_incident_*`` database reachable through ``SARAPP_MONGO_URI``.
"""
from __future__ import annotations

import argparse
import logging
from typing import Any

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import DB_INCIDENT_PREFIX, get_client, get_master_db
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

_RETIRED_PATHS = {
    "emergency_info.blood_type": "",
    "emergency_info.insurance": "",
}


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL


class IncidentPersonnelRepository(BaseRepository):
    collection_name = IncidentCollections.INCIDENT_PERSONNEL
    soft_deletes = False


def _clean_repository(repo: BaseRepository, *, dry_run: bool) -> int:
    query = {"$or": [{path: {"$exists": True}} for path in _RETIRED_PATHS]}
    documents = repo.find_many(query, include_deleted=True)
    if not dry_run:
        for document in documents:
            repo.apply_update(
                document["_id"],
                {"$unset": dict(_RETIRED_PATHS)},
                touch_updated_at=False,
            )
    return len(documents)


def remove_retired_fields(*, dry_run: bool = False) -> dict[str, Any]:
    client = get_client()
    master_count = _clean_repository(
        PersonnelRepository(get_master_db()),
        dry_run=dry_run,
    )
    incident_counts: dict[str, int] = {}
    for database_name in client.list_database_names():
        if not database_name.startswith(DB_INCIDENT_PREFIX):
            continue
        count = _clean_repository(
            IncidentPersonnelRepository(client[database_name]),
            dry_run=dry_run,
        )
        if count:
            incident_counts[database_name] = count
    return {"master": master_count, "incidents": incident_counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = remove_retired_fields(dry_run=args.dry_run)
    suffix = " (dry run)" if args.dry_run else ""
    log.info("Matched %d master personnel record(s)%s.", stats["master"], suffix)
    for database_name, count in stats["incidents"].items():
        log.info("Matched %d record(s) in %s%s.", count, database_name, suffix)


if __name__ == "__main__":
    main()
