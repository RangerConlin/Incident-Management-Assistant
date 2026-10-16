"""One-time seed: populate `MasterCollections.FACILITY_TYPES` with a
starter set of facility types and their custom `field_schema` (see
`server/sarapp_db/sarapp_db/api/routers/master_facilities.py` for what a
field_schema entry means).

Hospitals are NOT a facility type here — they have their own
long-standing master catalog (`MasterCollections.HOSPITALS` /
`hospitals.py`) and are deliberately out of scope for this catalog.

Run with SARAPP_MONGO_URI set in the environment, against whichever
database get_master_db() resolves to (a local catalog by default, or the
central catalog with SARAPP_MASTER_DB_NAME=sarapp_central_master):

    python -m sarapp_db.migrations.seed_facility_types
    python -m sarapp_db.migrations.seed_facility_types --dry-run
"""
from __future__ import annotations

import argparse
import logging

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import next_int_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

_FACILITY_TYPES = [
    {
        "name": "Airport/Airstrip",
        "description": "Fixed-wing/helicopter airfield usable as a base or staging point.",
        "field_schema": [
            {"key": "runway_length_ft", "label": "Runway Length (ft)", "input_type": "number", "value_type": "int"},
            {"key": "runway_surface", "label": "Runway Surface", "input_type": "text", "value_type": "str"},
            {"key": "has_control_tower", "label": "Control Tower", "input_type": "checkbox", "value_type": "bool"},
            {"key": "fuel_available", "label": "Fuel Available", "input_type": "checkbox", "value_type": "bool"},
            {"key": "fuel_types", "label": "Fuel Types", "input_type": "text", "value_type": "str"},
        ],
    },
    {
        "name": "Shelter",
        "description": "Mass-care/evacuee shelter location.",
        "field_schema": [
            {"key": "capacity_people", "label": "Capacity (people)", "input_type": "number", "value_type": "int"},
            {"key": "ada_accessible", "label": "ADA Accessible", "input_type": "checkbox", "value_type": "bool"},
            {"key": "pet_friendly", "label": "Pet Friendly", "input_type": "checkbox", "value_type": "bool"},
            {"key": "has_showers", "label": "Showers", "input_type": "checkbox", "value_type": "bool"},
        ],
    },
    {
        "name": "Staging Area",
        "description": "Resource/vehicle staging location.",
        "field_schema": [
            {"key": "capacity_vehicles", "label": "Capacity (vehicles)", "input_type": "number", "value_type": "int"},
            {"key": "surface_type", "label": "Surface Type", "input_type": "text", "value_type": "str"},
            {"key": "has_restrooms", "label": "Restrooms", "input_type": "checkbox", "value_type": "bool"},
        ],
    },
    {
        "name": "EOC",
        "description": "Emergency Operations Center.",
        "field_schema": [
            {"key": "seating_capacity", "label": "Seating Capacity", "input_type": "number", "value_type": "int"},
            {"key": "has_backup_power", "label": "Backup Power", "input_type": "checkbox", "value_type": "bool"},
            {"key": "bandwidth_mbps", "label": "Bandwidth (Mbps)", "input_type": "number", "value_type": "int"},
        ],
    },
    {
        "name": "Fuel Point",
        "description": "Fuel distribution point for vehicles/aircraft.",
        "field_schema": [
            {"key": "fuel_types", "label": "Fuel Types", "input_type": "text", "value_type": "str"},
            {"key": "tank_capacity_gal", "label": "Tank Capacity (gal)", "input_type": "number", "value_type": "int"},
        ],
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    col = get_master_db()[MasterCollections.FACILITY_TYPES]

    inserted = 0
    skipped = 0
    for sort_order, type_def in enumerate(_FACILITY_TYPES):
        if col.find_one({"name": type_def["name"]}):
            skipped += 1
            log.warning("Skipping name=%s: already present.", type_def["name"])
            continue
        doc = {
            "int_id": next_int_id(col) if not args.dry_run else None,
            "name": type_def["name"],
            "description": type_def["description"],
            "field_schema": type_def["field_schema"],
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
