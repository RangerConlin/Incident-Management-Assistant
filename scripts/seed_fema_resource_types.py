#!/usr/bin/env python3
"""
Seed the Resource Type Library from FEMA RTLT scraped data.

Reads data/fema_resource_types_raw.json (produced by fema_rtlt_scraper.py)
and inserts ResourceType records with FemaNimsMapping entries into master.db.

Idempotent: records whose name already exists are skipped (not overwritten).
Records with an 'error' key in the JSON are also skipped.

Usage:
    python scripts/seed_fema_resource_types.py
    python scripts/seed_fema_resource_types.py --db path/to/custom.db
    python scripts/seed_fema_resource_types.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup so we can import app modules from the project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.admin.resource_types.data.resource_type_repository import ResourceTypeRepository
from modules.admin.resource_types.models.resource_type_models import (
    FemaNimsMapping,
    RESOURCE_CATEGORIES,
    ResourceType,
)

INPUT_PATH = PROJECT_ROOT / "data" / "fema_resource_types_raw.json"

# ---------------------------------------------------------------------------
# FEMA kind → our RESOURCE_CATEGORIES mapping
# ---------------------------------------------------------------------------
_KIND_TO_CATEGORY: dict[str, str] = {
    "personnel": "Personnel",
    "team": "Team",
    "task force": "Team",
    "strike team": "Team",
    "unit": "Team",
    "crew": "Team",
    "vehicle": "Vehicle",
    "aircraft": "Aircraft",
    "equipment": "Equipment",
    "supply": "Supply",
    "supplies": "Supply",
    "facility": "Facility",
    "cache": "Equipment Kit / Cache",
    "kit": "Equipment Kit / Cache",
    "communications": "Communications",
}


def _map_category(kind: str) -> str:
    """Map a FEMA kind string to one of our RESOURCE_CATEGORIES."""
    lower = kind.lower().strip()
    for key, cat in _KIND_TO_CATEGORY.items():
        if key in lower:
            return cat
    return "Other"


# ---------------------------------------------------------------------------
# Discipline → human-readable string normalisation
# ---------------------------------------------------------------------------
_DISCIPLINE_NORMALISE: dict[str, str] = {
    "animal emergency management": "Animal Emergency Management",
    "incident management": "Incident Management",
    "emergency medical services": "Emergency Medical Services",
    "fire/hazardous materials": "Fire / Hazardous Materials",
    "fire / hazardous materials": "Fire / Hazardous Materials",
    "law enforcement": "Law Enforcement",
    "mass care": "Mass Care",
    "public works/engineering": "Public Works / Engineering",
    "public works / engineering": "Public Works / Engineering",
    "search and rescue": "Search and Rescue",
    "public health and medical": "Public Health and Medical",
    "public health": "Public Health and Medical",
    "donations and volunteer management": "Donations and Volunteer Management",
    "utilities": "Utilities",
}


def _normalise_discipline(raw: str) -> str:
    key = raw.lower().strip()
    return _DISCIPLINE_NORMALISE.get(key, raw.strip())


# ---------------------------------------------------------------------------
# Discipline number → name fallback (from ID prefix, e.g. "4-508-1273" → 4)
# ---------------------------------------------------------------------------
_DISC_NUM_TO_NAME: dict[str, str] = {
    "1": "Animal Emergency Management",
    "2": "Incident Management",
    "3": "Emergency Medical Services",
    "4": "Fire / Hazardous Materials",
    "5": "Law Enforcement",
    "6": "Mass Care",
    "7": "Public Works / Engineering",
    "8": "Search and Rescue",
    "9": "Public Health and Medical",
    "10": "Donations and Volunteer Management",
    "11": "Utilities",
    "12": "Public Health and Medical",
    "13": "Transportation",
}


def _disc_from_id(resource_id: str) -> str:
    """Return discipline name derived from the leading digit(s) of the RTLT ID."""
    prefix = resource_id.split("-")[0]
    return _DISC_NUM_TO_NAME.get(prefix, "")


# ---------------------------------------------------------------------------
# Type level normalisation
# ---------------------------------------------------------------------------
_TYPE_SORT: dict[str, int] = {
    "Type I": 1, "Type II": 2, "Type III": 3, "Type IV": 4,
}


def _sort_type_levels(levels: list[str]) -> list[str]:
    return sorted(set(levels), key=lambda t: _TYPE_SORT.get(t, 99))


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------

def _build_resource_type(rec: dict) -> ResourceType:
    """Convert one scraped record into a ResourceType ready for saving."""

    name = rec.get("name", "").strip()
    kind = rec.get("kind", "").strip()
    discipline_raw = rec.get("discipline", "").strip()
    resource_id = rec.get("id", "")
    reference_url = rec.get("reference_url", "")
    description = rec.get("description", "").strip()
    type_levels = _sort_type_levels(rec.get("type_levels", []))

    # Resolve discipline — prefer parsed value, fall back to numeric prefix
    discipline = _normalise_discipline(discipline_raw) if discipline_raw else _disc_from_id(resource_id)

    category = _map_category(kind)

    # Build FemaNimsMapping entries — one per type level if known, else one catch-all
    fema_mappings: list[FemaNimsMapping] = []
    if type_levels:
        for level in type_levels:
            fema_mappings.append(FemaNimsMapping(
                resource_type_id=0,   # filled in by repository on save
                nims_name=name,
                discipline=discipline,
                type_code=resource_id,
                kind=kind,
                reference_url=reference_url,
                typed_level=level,
            ))
    else:
        fema_mappings.append(FemaNimsMapping(
            resource_type_id=0,
            nims_name=name,
            discipline=discipline,
            type_code=resource_id,
            kind=kind,
            reference_url=reference_url,
            typed_level="",
        ))

    return ResourceType(
        name=name,
        planning_display_name=name,
        category=category,
        source="FEMA/NIMS",
        owner_agency="FEMA / NIMS",
        description=description,
        is_active=True,
        fema_mappings=fema_mappings,
        created_by="fema_seed",
        updated_by="fema_seed",
    )


def seed(db_path: Path | None = None, dry_run: bool = False) -> None:
    if not INPUT_PATH.exists():
        print(f"ERROR: Input file not found: {INPUT_PATH}")
        print("Run scripts/fema_rtlt_scraper.py first.")
        sys.exit(1)

    with open(INPUT_PATH, encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    print(f"Loaded {len(records)} records from {INPUT_PATH}")

    repo = ResourceTypeRepository(db_path)

    # Pre-load existing names to avoid duplicate key errors
    existing = {row["name"] for row in repo.list_resource_types(active_filter="All")}
    print(f"Existing resource types in DB: {len(existing)}")

    skipped_error = 0
    skipped_existing = 0
    inserted = 0
    failed = 0

    for rec in records:
        if "error" in rec:
            skipped_error += 1
            continue

        name = rec.get("name", "").strip()
        if not name:
            skipped_error += 1
            continue

        if name in existing:
            skipped_existing += 1
            continue

        rt = _build_resource_type(rec)

        if dry_run:
            print(f"  DRY-RUN  {rt.name[:60]:62s}  [{rt.category}]")
            inserted += 1
            continue

        try:
            repo.save_resource_type(rt)
            inserted += 1
            existing.add(name)
        except Exception as exc:
            print(f"  FAILED   {name[:60]}: {exc}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Inserted:         {inserted}")
    print(f"Skipped (exists): {skipped_existing}")
    print(f"Skipped (errors): {skipped_error}")
    print(f"Failed:           {failed}")
    if dry_run:
        print("\n(dry-run — no changes written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FEMA resource types into master.db")
    parser.add_argument("--db", metavar="PATH", help="Path to SQLite DB (default: data/master.db)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be inserted without writing anything")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None

    print("FEMA Resource Type Seeder")
    print("=" * 60)
    seed(db_path=db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
