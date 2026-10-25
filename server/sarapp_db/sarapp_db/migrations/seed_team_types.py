"""Seed the central Team Type Catalog with cross-discipline system defaults.

This is an idempotent catalog migration, not incident/demo data. Existing
records are matched by code (or name for older rows), retained, and only
receive canonical fields that are missing. Administrator edits are never
overwritten. Run it against the central catalog so normal catalog sync pulls
the definitions to connected servers::

    python -m sarapp_db.migrations.seed_team_types
    python -m sarapp_db.migrations.seed_team_types --dry-run
"""
from __future__ import annotations

import argparse
import logging
import re
from typing import Any

from pymongo.database import Database

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.int_id import next_int_id
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


class _TeamTypeRepository(BaseRepository):
    collection_name = MasterCollections.TEAM_TYPES
    soft_deletes = False


class _CapabilityRepository(BaseRepository):
    collection_name = MasterCollections.RESOURCE_CAPABILITIES
    soft_deletes = False


_CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("Ground Search", "Search & Rescue"),
    ("Direction Finding", "Search & Rescue"),
    ("Aerial Reconnaissance", "Aviation"),
    ("Uncrewed Aircraft Operations", "Aviation"),
    ("K9 Search", "Search & Rescue"),
    ("Technical Rescue", "Fire & Rescue"),
    ("Fire Suppression", "Fire & Rescue"),
    ("Water Supply", "Fire & Rescue"),
    ("Vehicle Extrication", "Fire & Rescue"),
    ("Hazardous Materials Response", "Fire & Rescue"),
    ("Basic Life Support", "EMS"),
    ("Advanced Life Support", "EMS"),
    ("Patient Transport", "EMS"),
    ("Law Enforcement", "Law Enforcement"),
    ("Traffic Control", "Law Enforcement"),
    ("Damage Assessment", "Emergency Management"),
    ("EOC Support", "Emergency Management"),
    ("Road Clearance", "Public Works"),
    ("Utility Restoration", "Public Works"),
    ("Heavy Equipment Operations", "Public Works"),
    ("Event Staffing", "Planned Events"),
    ("Parking Management", "Planned Events"),
    ("General Support", "General"),
)


def _type(
    name: str,
    code: str,
    category: str,
    color_key: str,
    icon_key: str,
    capabilities: tuple[str, ...] = (),
    *,
    sections: tuple[str, ...] = ("personnel", "vehicles", "equipment", "logs"),
    minimum_personnel: int = 0,
    minimum_vehicles: int = 0,
    minimum_aircraft: int = 0,
    is_drone: bool = False,
    is_aviation: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "type_short": code,
        "category": category,
        "description": f"{name} used as an incident operational team.",
        "scope": "system",
        "organization_id": None,
        "color_key": color_key,
        "text_color_key": "team_text_auto",
        "icon_key": icon_key,
        "capabilities": capabilities,
        "minimum_personnel": minimum_personnel,
        "required_roles": [],
        "minimum_vehicles": minimum_vehicles,
        "minimum_aircraft": minimum_aircraft,
        "minimum_equipment": 0,
        "detail_sections": list(sections),
        "resource_type_id": None,
        "is_drone": is_drone,
        "is_aviation": is_aviation,
        "is_active": True,
        "version": 1,
    }


_TEAM_TYPES: tuple[dict[str, Any], ...] = (
    _type("Ground Team", "GT", "Search & Rescue", "team_type_search_rescue", "team", ("Ground Search",)),
    _type("Urban Direction Finding Team", "UDF", "Search & Rescue", "team_type_search_rescue", "direction_finding", ("Direction Finding",)),
    _type("Land Search and Rescue Team", "LSAR", "Search & Rescue", "team_type_search_rescue", "team", ("Ground Search",)),
    _type("Direction Finding Team", "DF", "Search & Rescue", "team_type_search_rescue", "direction_finding", ("Direction Finding",)),
    _type("Ground/UAS Team", "GT/UAS", "Search & Rescue", "team_type_search_rescue", "uas", ("Ground Search", "Uncrewed Aircraft Operations"), is_drone=True),
    _type("UDF/UAS Team", "UDF/UAS", "Search & Rescue", "team_type_search_rescue", "uas", ("Direction Finding", "Uncrewed Aircraft Operations"), is_drone=True),
    _type("UAS Team", "UAS", "Aviation", "team_type_aviation", "uas", ("Uncrewed Aircraft Operations", "Aerial Reconnaissance"), is_drone=True, is_aviation=True),
    _type("K9 Search Team", "K9", "Search & Rescue", "team_type_search_rescue", "k9", ("K9 Search",)),
    _type("Technical Rescue Team", "TECH", "Fire & Rescue", "team_type_fire", "technical_rescue", ("Technical Rescue",)),
    _type("Engine Company", "ENG", "Fire & Rescue", "team_type_fire", "engine", ("Fire Suppression", "Water Supply"), minimum_vehicles=1),
    _type("Truck Company", "TRK", "Fire & Rescue", "team_type_fire", "truck", ("Fire Suppression", "Technical Rescue"), minimum_vehicles=1),
    _type("Rescue Company", "RES", "Fire & Rescue", "team_type_fire", "rescue", ("Technical Rescue", "Vehicle Extrication"), minimum_vehicles=1),
    _type("Brush Unit", "BRSH", "Fire & Rescue", "team_type_fire", "brush", ("Fire Suppression",), minimum_vehicles=1),
    _type("HazMat Team", "HAZ", "Fire & Rescue", "team_type_fire", "hazmat", ("Hazardous Materials Response",)),
    _type("Ambulance Crew", "AMB", "EMS", "team_type_ems", "ambulance", ("Basic Life Support", "Patient Transport"), minimum_vehicles=1),
    _type("Medical Team", "MED", "EMS", "team_type_ems", "medical", ("Basic Life Support",)),
    _type("EMS Supervisor", "EMS-S", "EMS", "team_type_ems", "ems_supervisor", ("Basic Life Support",)),
    _type("Patrol Unit", "PAT", "Law Enforcement", "team_type_law_enforcement", "patrol", ("Law Enforcement",), minimum_vehicles=1),
    _type("Traffic Control Team", "TRF", "Law Enforcement", "team_type_law_enforcement", "traffic_control", ("Traffic Control",)),
    _type("Law Enforcement K9 Team", "LE-K9", "Law Enforcement", "team_type_law_enforcement", "k9", ("Law Enforcement", "K9 Search")),
    _type("Tactical Team", "TAC", "Law Enforcement", "team_type_law_enforcement", "tactical", ("Law Enforcement",)),
    _type("Fixed-Wing Aircrew", "AIR", "Aviation", "team_type_aviation", "fixed_wing", ("Aerial Reconnaissance",), sections=("aircrew", "aircraft", "equipment", "logs"), minimum_aircraft=1, is_aviation=True),
    _type("Helicopter Crew", "HELO", "Aviation", "team_type_aviation", "helicopter", ("Aerial Reconnaissance",), sections=("aircrew", "aircraft", "equipment", "logs"), minimum_aircraft=1, is_aviation=True),
    _type("Damage Assessment Team", "DA", "Emergency Management", "team_type_emergency_management", "damage_assessment", ("Damage Assessment",)),
    _type("EOC Support Team", "EOC", "Emergency Management", "team_type_emergency_management", "eoc", ("EOC Support",)),
    _type("Road Crew", "ROAD", "Public Works", "team_type_public_works", "road", ("Road Clearance",), minimum_vehicles=1),
    _type("Utilities Crew", "UTIL-C", "Public Works", "team_type_public_works", "utilities", ("Utility Restoration",), minimum_vehicles=1),
    _type("Heavy Equipment Crew", "HEAVY", "Public Works", "team_type_public_works", "heavy_equipment", ("Heavy Equipment Operations",), minimum_vehicles=1),
    _type("Course Marshal Team", "MARSHAL", "Planned Events", "team_type_planned_event", "course_marshal", ("Event Staffing",)),
    _type("Parking Team", "PARK", "Planned Events", "team_type_planned_event", "parking", ("Parking Management",)),
    _type("Volunteer Team", "VOL", "Planned Events", "team_type_planned_event", "volunteer", ("Event Staffing", "General Support")),
    _type("Utility/Support Team", "UTIL", "General", "team_type_general", "support", ("General Support",)),
)


def _exact(value: str) -> dict[str, str]:
    return {"$regex": f"^{re.escape(value)}$", "$options": "i"}


def seed_team_types(*, db: Database | None = None, dry_run: bool = False) -> dict[str, int]:
    target_db = db if db is not None else get_master_db()
    team_repo = _TeamTypeRepository(target_db)
    capability_repo = _CapabilityRepository(target_db)

    capability_ids: dict[str, str] = {}
    capabilities_inserted = 0
    for name, category in _CAPABILITIES:
        existing = capability_repo.find_one({"name": _exact(name)})
        if existing:
            capability_ids[name] = str(existing.get("capability_id") or "")
            continue
        capability_id = str(next_int_id(capability_repo._col, "capability_id"))
        capability_ids[name] = capability_id
        if not dry_run:
            capability_repo.insert_one(
                {
                    "capability_id": capability_id,
                    "name": name,
                    "category": category,
                    "description": "",
                    "aliases": [],
                    "is_active": True,
                    "notes": "",
                }
            )
        capabilities_inserted += 1

    inserted = 0
    upgraded = 0
    skipped = 0
    for definition in _TEAM_TYPES:
        code = definition["type_short"]
        existing = team_repo.find_one({"type_short": _exact(code)})
        if existing is None:
            existing = team_repo.find_one({"name": _exact(definition["name"])})

        canonical = {key: value for key, value in definition.items() if key != "capabilities"}
        canonical["capability_ids"] = [
            capability_ids[name] for name in definition["capabilities"] if capability_ids.get(name)
        ]

        if existing is None:
            canonical["int_id"] = next_int_id(team_repo._col) if not dry_run else 0
            if not dry_run:
                team_repo.insert_one(canonical)
            inserted += 1
            continue

        missing = {key: value for key, value in canonical.items() if key not in existing}
        if missing:
            if not dry_run:
                team_repo.update_one(existing["_id"], missing)
            upgraded += 1
        else:
            skipped += 1

    result = {
        "capabilities_inserted": capabilities_inserted,
        "team_types_inserted": inserted,
        "team_types_upgraded": upgraded,
        "team_types_skipped": skipped,
    }
    log.info("Team Type Catalog seed complete%s: %s", " (dry run)" if dry_run else "", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    seed_team_types(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
