"""One-time seed: insert the "MIWGF 52 - Ground Team ORM" GAR template.

Transcribed from CAP Michigan Wing Form 52 ("Michigan Wing Operational Risk
Management - Ground Team Operations", MIWGF 52, Feb 16) — a real paper ORM
form supplied by the user as a reference example, not drafted content. Point
values, option text, and risk bands are copied as closely as the group/row/
option template shape allows:
  - Two rows carry a hard No-Go in the source form ("N/G" in place of a
    point value) rather than a numeric option: Team Health/Rest "Poor,
    fatigued" and Vehicle "Vehicle Safety Issues". Those options are
    represented here with ``no_go: True``; their point value is a filler
    consistent with the row's other options; it never actually drives the
    outcome because a No-Go always overrides the point-based band.
  - "Night Operations" only has two options (No/Yes) in the source form —
    there is no "moderate" middle tier for that row, unlike every other row.
  - Band floors (0 / 85 / 110 / 170) and required-reviewer labels (Ground
    Team Leader / Ground Branch Director / Operations Section Chief /
    Incident Commander) are copied directly from the form's "Overall
    Assessment" table.

Idempotent: does nothing if a template with this name already exists.

Run with SARAPP_MONGO_URI set in the environment:

    python -m sarapp_db.migrations.seed_miwgf52_gar_template

Add --dry-run to preview without writing anything.
"""
from __future__ import annotations

import argparse
import logging

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import dual_key_field
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TEMPLATE_NAME = "MIWGF 52 - Ground Team ORM"


class _GarTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.GAR_TEMPLATES
    soft_deletes = False


def _option(id_: str, label: str, points: int, *, no_go: bool = False) -> dict:
    return {"id": id_, "label": label, "points": points, "no_go": no_go}


def _row(id_: str, label: str, options: list[dict]) -> dict:
    return {"id": id_, "label": label, "options": options}


def _group(id_: str, name: str, rows: list[dict]) -> dict:
    return {"id": id_, "name": name, "rows": rows}


def build_miwgf52_template() -> dict:
    groups = [
        _group(
            "team_information",
            "Team Information",
            [
                _row(
                    "gtl_experience",
                    "GTL Experience/Training",
                    [
                        _option("low", "> 31 missions", 0),
                        _option("moderate", "> 11 < 30 missions", 5),
                        _option("high", "< 10 missions", 10),
                    ],
                ),
                _row(
                    "gtl_age",
                    "GTL Age",
                    [
                        _option("low", "> 25", 0),
                        _option("moderate", "> 21 < 25", 5),
                        _option("high", "< 21", 10),
                    ],
                ),
                _row(
                    "gtl_currency",
                    "GTL Currency",
                    [
                        _option("low", "> 1 mission (in 90 days)", 0),
                        _option("moderate", "> 1 mission (in 180 days)", 10),
                        _option("high", "> 1 mission (in year)", 20),
                    ],
                ),
                _row(
                    "team_health",
                    "Team Health/Rest",
                    [
                        _option("low", "Good", 0),
                        _option("moderate", "Fair", 15),
                        _option("high", "Poor, fatigued", 20, no_go=True),
                    ],
                ),
            ],
        ),
        _group(
            "vehicle_equipment",
            "Vehicle and Equipment Factors",
            [
                _row(
                    "vehicle",
                    "Vehicle",
                    [
                        _option("low", "Fully functional & equipped", 0),
                        _option("moderate", "No safety issues, some defective equipment", 5),
                        _option("high", "Vehicle Safety Issues", 15, no_go=True),
                    ],
                ),
                _row(
                    "mileage",
                    "Mileage",
                    [
                        _option("low", "< 80,000", 0),
                        _option("moderate", "> 80,000 < 140,000", 5),
                        _option("high", "> 140,000", 15),
                    ],
                ),
            ],
        ),
        _group(
            "mission_specific",
            "Mission Specific",
            [
                _row(
                    "operations_tempo",
                    "Operations Tempo",
                    [
                        _option("low", "2-3 ground teams", 0),
                        _option("moderate", "1 or 4-5 ground teams", 5),
                        _option("high", "> 5 ground teams", 10),
                    ],
                ),
                _row(
                    "communications",
                    "Communications",
                    [
                        _option("low", "Good comm via radio", 0),
                        _option("moderate", "< 15 mins from comm contact via phone or radio", 5),
                        _option("high", "> 15 mins from comm contact via phone or radio", 10),
                    ],
                ),
                _row(
                    "mission_type",
                    "Mission Type",
                    [
                        _option("low", "Mounted in Vehicle", 0),
                        _option("moderate", "Dismount Possible", 10),
                        _option("high", "Dismount Likely", 15),
                    ],
                ),
            ],
        ),
        _group(
            "environmental",
            "Environmental Factors",
            [
                _row(
                    "temperature",
                    "Temperature (°F)",
                    [
                        _option("low", ">35° < 79°", 0),
                        _option("moderate", "> 10° < 35° or > 79° < 91°", 5),
                        _option("high", "< 10° or > 91°", 15),
                    ],
                ),
                _row(
                    "wind",
                    "Wind",
                    [
                        _option("low", "< 11 mph", 0),
                        _option("moderate", "> 11 < 28 mph", 5),
                        _option("high", "> 28 mph", 10),
                    ],
                ),
                _row(
                    "precipitation",
                    "Precipitation",
                    [
                        _option("low", "None", 0),
                        _option("moderate", "Light", 5),
                        _option("high", "Heavy", 10),
                    ],
                ),
                _row(
                    "light_conditions",
                    "Light Conditions",
                    [
                        _option("low", "Sunny or Overcast", 0),
                        _option("moderate", "Near Dark", 5),
                        _option("high", "Night", 15),
                    ],
                ),
                _row(
                    "road_conditions",
                    "Road Conditions",
                    [
                        _option("low", "Dry", 0),
                        _option("moderate", "Slick", 10),
                        _option("high", "Snow and Ice", 20),
                    ],
                ),
                _row(
                    "michigan_terrain",
                    "Michigan Terrain",
                    [
                        _option("low", "Flat, open, and dry", 0),
                        _option("moderate", "Rolling, moderate cover", 5),
                        _option("high", "Rugged, heavy cover", 10),
                    ],
                ),
                _row(
                    "night_operations",
                    "Night Operations",
                    [
                        _option("low", "No", 0),
                        _option("high", "Yes", 10),
                    ],
                ),
                _row(
                    "operation_area",
                    "Operation Area",
                    [
                        _option("low", "Lower Michigan", 0),
                        _option("moderate", "Lower Peninsula, N of 44°", 5),
                        _option("high", "Upper Peninsula", 15),
                    ],
                ),
            ],
        ),
    ]

    bands = [
        {"floor": 170, "label": "High Risk", "required_reviewer": "Incident Commander"},
        {"floor": 110, "label": "Moderate Risk", "required_reviewer": "Operations Section Chief"},
        {"floor": 85, "label": "Low - Mod Risk", "required_reviewer": "Ground Branch Director"},
        {"floor": 0, "label": "Low Risk", "required_reviewer": "Ground Team Leader"},
    ]

    return {
        "name": TEMPLATE_NAME,
        "source": "CAP Michigan Wing",
        "description": (
            "Transcribed from CAP Michigan Wing Form 52 (MIWGF 52, Feb 16), the Ground Team "
            "Operations ORM worksheet. Point values and bands are copied from the source form; "
            "edit here if your wing's form has since been revised."
        ),
        "groups": groups,
        "bands": bands,
        "active": True,
        "created_by": "",
        "updated_by": "",
    }


def seed(*, dry_run: bool = False) -> bool:
    repo = _GarTemplatesRepository(get_master_db())
    existing = repo.find_one({"name": TEMPLATE_NAME})
    if existing:
        field = dual_key_field(repo._db, "id", "id_master")
        log.info("Template '%s' already exists (%s=%s) — nothing to do.", TEMPLATE_NAME, field, existing.get(field))
        return False

    doc = build_miwgf52_template()
    field = dual_key_field(repo._db, "id", "id_master")
    docs = repo.find_many({field: {"$exists": True}}, sort=[(field, -1)], limit=1)
    doc[field] = int((docs[0] if docs else {}).get(field) or 0) + 1

    if dry_run:
        log.info("[dry-run] Would insert template '%s' with %s=%s", TEMPLATE_NAME, field, doc[field])
        return True

    repo.insert_one(doc)
    log.info("Inserted template '%s' with %s=%s", TEMPLATE_NAME, field, doc[field])
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing anything.")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
