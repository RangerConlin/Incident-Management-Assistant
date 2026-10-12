"""One-time cleanup for duplicate master personnel rows.

Use this to remove known-bad duplicate personnel records after the create path
has been fixed. The script is intentionally conservative:

- dry-run by default
- only deletes rows that match every supplied filter
- can preserve one matching row if requested

Examples:

    python -m sarapp_db.migrations.remove_duplicate_personnel_records ^
        --person-id 405021 --name "Id Lookup" --callsign INDIA --phone 405-021-0000

    python -m sarapp_db.migrations.remove_duplicate_personnel_records ^
        --person-id 405021 --name "Id Lookup" --callsign INDIA --phone 405-021-0000 --apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


class PersonnelRepository(BaseRepository):
    collection_name = MasterCollections.PERSONNEL
    soft_deletes = False


def _clean(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _matches(doc: dict[str, Any], filters: dict[str, str]) -> bool:
    for field, expected in filters.items():
        if _clean(doc.get(field)) != expected:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-id", default="", help="Visible person_id to match exactly.")
    parser.add_argument("--name", default="", help="Exact name to match.")
    parser.add_argument("--callsign", default="", help="Exact callsign to match.")
    parser.add_argument("--phone", default="", help="Exact phone to match.")
    parser.add_argument(
        "--preserve-first",
        action="store_true",
        help="Keep the lowest person_record among matching rows and delete the rest.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matching rows. Omit for dry-run.",
    )
    args = parser.parse_args()

    filters = {
        key: value
        for key, value in {
            "person_id": _clean(args.person_id),
            "name": _clean(args.name),
            "callsign": _clean(args.callsign),
            "phone": _clean(args.phone),
        }.items()
        if value
    }
    if not filters:
        log.error("At least one exact-match filter is required.")
        sys.exit(2)

    try:
        repo = PersonnelRepository(get_master_db())
    except Exception as exc:
        log.error("Unable to connect to MongoDB: %s", exc)
        sys.exit(1)

    matches = [doc for doc in repo.find_many({}, sort=[("person_record", 1)]) if _matches(doc, filters)]
    if not matches:
        log.info("No personnel rows matched %s", filters)
        return

    to_delete = list(matches)
    if args.preserve_first and len(to_delete) > 1:
        preserved = to_delete.pop(0)
        log.info(
            "Preserving person_record=%s name=%s",
            preserved.get("person_record"),
            preserved.get("name"),
        )

    log.info("Matched %d personnel rows", len(matches))
    for doc in to_delete:
        log.info(
            "%s person_record=%s person_id=%s name=%s callsign=%s phone=%s",
            "DELETE" if args.apply else "WOULD DELETE",
            doc.get("person_record"),
            doc.get("person_id"),
            doc.get("name"),
            doc.get("callsign"),
            doc.get("phone"),
        )

    if not args.apply:
        log.info("Dry run complete. Re-run with --apply to delete.")
        return

    deleted = 0
    for doc in to_delete:
        if repo.delete_one(doc["_id"]):
            deleted += 1
    log.info("Deleted %d personnel rows", deleted)


if __name__ == "__main__":
    main()
