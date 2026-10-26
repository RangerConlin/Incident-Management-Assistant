"""Convert legacy global notification read state to per-recipient state.

Run once before deploying clients that use recipient-specific acknowledgement.
The migration is idempotent and processes every incident database.
"""

from __future__ import annotations

import argparse

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import DB_INCIDENT_PREFIX
from sarapp_db.mongo.mongo_client import get_client


def migrate(*, dry_run: bool = False) -> dict[str, int]:
    client = get_client()
    changed = 0
    for database_name in client.list_database_names():
        if not database_name.startswith(DB_INCIDENT_PREFIX):
            continue
        collection = client[database_name][IncidentCollections.NOTIFICATIONS]
        for row in collection.find({"recipient_states": {"$exists": False}}):
            recipients = (row.get("delivery") or {}).get("recipients") or []
            states = [
                {
                    "person_record": int(person_record),
                    "read": bool(row.get("read", False)),
                    **({"acknowledged_at": row["acknowledged_at"]} if row.get("acknowledged_at") else {}),
                    **({"dismissed_at": row["dismissed_at"]} if row.get("dismissed_at") else {}),
                }
                for person_record in recipients
            ]
            changed += 1
            if not dry_run:
                collection.update_one(
                    {"_id": row["_id"]},
                    {
                        "$set": {"recipient_states": states},
                        "$unset": {
                            "read": "",
                            "acknowledged_at": "",
                            "acknowledged_by": "",
                            "dismissed_at": "",
                            "dismissed_by": "",
                        },
                    },
                )
    return {"notifications_converted": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
