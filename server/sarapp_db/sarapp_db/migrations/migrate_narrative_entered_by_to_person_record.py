"""One-time migration from legacy narrative person IDs to person records.

Legacy narrative entries stored the visible ``person_id`` in ``entered_by``.
The canonical shape stores the unique ``person_record`` instead.

Run with ``SARAPP_MONGO_URI`` set in the environment::

    python -m sarapp_db.migrations.migrate_narrative_entered_by_to_person_record --dry-run

Ambiguous person IDs are reported and skipped because person_id is allowed to
be duplicated.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_client
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


class TasksRepository(BaseRepository):
    collection_name = IncidentCollections.TASKS
    soft_deletes = False


def _person_records(client) -> tuple[dict[str, int], set[str]]:
    by_id: dict[str, int] = {}
    duplicates: set[str] = set()
    for person in PersonnelRepository(client["sarapp_master"]).find_many({}):
        visible_id = str(person.get("person_id") or "").strip()
        record = person.get("person_record")
        if not visible_id or record is None:
            continue
        if visible_id in by_id:
            duplicates.add(visible_id)
        else:
            by_id[visible_id] = int(record)
    for visible_id in duplicates:
        by_id.pop(visible_id, None)
    return by_id, duplicates


def _migrate_database(db, by_id: dict[str, int], dry_run: bool) -> dict[str, int]:
    repo = TasksRepository(db)
    stats = {"tasks_scanned": 0, "entries_migrated": 0, "ambiguous_entries": 0}
    for task in repo.find_many({"narrative.0": {"$exists": True}}):
        stats["tasks_scanned"] += 1
        updates: dict[str, Any] = {}
        for index, entry in enumerate(task.get("narrative") or []):
            raw = str(entry.get("entered_by") or "").strip()
            if not raw:
                continue
            record = by_id.get(raw)
            if record is None:
                stats["ambiguous_entries"] += 1
                continue
            updates[f"narrative.{index}.entered_by"] = str(record)
            stats["entries_migrated"] += 1
        if updates and not dry_run:
            repo.apply_update(task["_id"], {"$set": updates})
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        client = get_client()
        by_id, duplicates = _person_records(client)
    except Exception as exc:
        log.error("Unable to connect to MongoDB: %s", exc)
        sys.exit(1)

    log.info("Unique person_id mappings: %d", len(by_id))
    log.info("Duplicate person_ids skipped: %d", len(duplicates))
    totals = {"tasks_scanned": 0, "entries_migrated": 0, "ambiguous_entries": 0}
    for name in client.list_database_names():
        if not name.startswith("sarapp_incident_"):
            continue
        stats = _migrate_database(client[name], by_id, args.dry_run)
        for key, value in stats.items():
            totals[key] += value
    log.info("Migration complete%s: %s", " (dry run)" if args.dry_run else "", totals)


if __name__ == "__main__":
    main()
