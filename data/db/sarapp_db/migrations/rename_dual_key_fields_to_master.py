"""One-time migration: rename each dual-key collection's local record field
to its `*_record_master` field, on the central catalog only.

Before this migration, the central catalog (cloud_router's embedded
`sarapp_central_master`, see `Design Documents/Instructions/
cloud_router_architecture.md`) assigned the same local record field every
local catalog does (`person_record`, `equipment_record`, `vehicle_record`,
`aircraft_record`). That overloaded the field: it's meant to be a
server-local id that collides across servers, while the central catalog
needs an agency-wide id that never collides. Since the central catalog has
only ever had one writer, its existing values are already safe to treat as
that agency-wide id outright — this is a pure field rename per collection,
not a data transform. See `Design Documents/Instructions/
mongodb_schema_decisions.md` ("Personnel: central-vs-local record ids") and
each collection's router (`personnel.py`, `equipment.py`, `vehicles.py`,
`aircraft.py`).

This only ever touches `sarapp_central_master` — every local server's own
`sarapp_master` is untouched; those keep assigning their local field exactly
as before and simply gain the new, initially-null `*_record_master` field
going forward.

Run with ``SARAPP_MONGO_URI`` set in the environment::

    python -m sarapp_db.migrations.rename_dual_key_fields_to_master --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys

from sarapp_db.mongo.database_manager import DB_CENTRAL_MASTER, get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# collection -> (local field, master field). Add an entry here for each
# central catalog collection using a local-id/master-id pair.
_DUAL_KEY_FIELDS: dict[str, tuple[str, str]] = {
    "personnel": ("person_record", "person_record_master"),
    "equipment": ("equipment_record", "equipment_record_master"),
    "vehicles": ("vehicle_record", "vehicle_record_master"),
    "aircraft": ("aircraft_record", "aircraft_record_master"),
    "hazard_types": ("id", "id_master"),
    "gar_templates": ("id", "id_master"),
    "canned_comm_entries": ("id", "id_master"),
    "hospitals": ("id", "id_master"),
    "objective_templates": ("int_id", "int_id_master"),
    "strategy_templates": ("int_id", "int_id_master"),
    "radio_channels": ("channel_id", "channel_id_master"),
    "safety_analysis_templates": ("template_id", "template_id_master"),
}


def _rename_collection(col, local_field: str, master_field: str, *, dry_run: bool) -> dict[str, int]:
    docs = list(col.find({local_field: {"$exists": True}}))
    renamed = 0
    skipped_conflict = 0
    for doc in docs:
        if doc.get(master_field) is not None:
            skipped_conflict += 1
            log.warning(
                "Skipping %s._id=%s: %s already set (%s); leaving %s untouched.",
                col.name,
                doc["_id"],
                master_field,
                doc.get(master_field),
                local_field,
            )
            continue
        if not dry_run:
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {master_field: doc[local_field]}, "$unset": {local_field: ""}},
            )
        renamed += 1
    return {"found": len(docs), "renamed": renamed, "skipped_conflict": skipped_conflict}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        client = get_client()
    except Exception as exc:
        log.error("Unable to connect to MongoDB: %s", exc)
        sys.exit(1)

    db = client[DB_CENTRAL_MASTER]
    for collection, (local_field, master_field) in _DUAL_KEY_FIELDS.items():
        stats = _rename_collection(db[collection], local_field, master_field, dry_run=args.dry_run)
        log.info(
            "%s%s: %s",
            collection,
            " (dry run)" if args.dry_run else "",
            stats,
        )


if __name__ == "__main__":
    main()
