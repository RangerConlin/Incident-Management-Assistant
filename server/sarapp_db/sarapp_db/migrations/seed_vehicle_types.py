"""One-time seed: populate `MasterCollections.VEHICLE_TYPES` with a
starter set of vehicle types (see
`server/sarapp_db/sarapp_db/api/routers/vehicles.py` for how the catalog
backs the vehicle edit form's Type combo box).

Run with SARAPP_MONGO_URI set in the environment, against whichever
database get_master_db() resolves to (a local catalog by default, or the
central catalog with SARAPP_MASTER_DB_NAME=sarapp_central_master):

    python -m sarapp_db.migrations.seed_vehicle_types
    python -m sarapp_db.migrations.seed_vehicle_types --dry-run
"""
from __future__ import annotations

import argparse
import logging

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import next_int_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

_VEHICLE_TYPES = [
    {"name": "Passenger Vehicle", "description": "Sedan, SUV, or other light passenger vehicle."},
    {"name": "Utility", "description": "Pickup, van, or other light utility vehicle."},
    {"name": "Support", "description": "General support vehicle not covered by a more specific type."},
    {"name": "Ambulance", "description": "Ground ambulance/medical transport unit."},
    {"name": "Engine/Pumper", "description": "Fire engine/pumper apparatus."},
    {"name": "Brush Truck", "description": "Wildland/brush firefighting apparatus."},
    {"name": "Water Tender", "description": "Water tender/tanker apparatus."},
    {"name": "Command Vehicle", "description": "Mobile command post/incident command vehicle."},
    {"name": "ATV/UTV", "description": "All-terrain or utility task vehicle."},
    {"name": "Snowmobile", "description": "Snowmobile."},
    {"name": "Boat", "description": "Watercraft, including trailered boats."},
    {"name": "Trailer", "description": "Equipment, utility, or cargo trailer."},
    {"name": "Other", "description": "Any vehicle not covered by another type."},
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    col = get_master_db()[MasterCollections.VEHICLE_TYPES]

    inserted = 0
    skipped = 0
    for sort_order, type_def in enumerate(_VEHICLE_TYPES):
        if col.find_one({"name": type_def["name"]}):
            skipped += 1
            log.warning("Skipping name=%s: already present.", type_def["name"])
            continue
        doc = {
            "int_id": next_int_id(col) if not args.dry_run else None,
            "name": type_def["name"],
            "description": type_def["description"],
            "is_active": 1,
            "sort_order": sort_order,
        }
        if not args.dry_run:
            col.insert_one(doc)
        inserted += 1

    log.info(
        "Seed complete%s: %d inserted, %d skipped (already present).",
        " (dry run)" if args.dry_run else "",
        inserted,
        skipped,
    )


if __name__ == "__main__":
    main()
