"""Seed canonical SAR incident objective templates into sarapp_master.

This is a small, idempotent seed utility for the master objective template
collection. It creates a reusable starter set for common SAR incident types
such as wilderness, water, winter, urban, and extended operations.

Usage:
    python data/db/seed_objective_templates.py

With a custom MongoDB URI:
    SARAPP_MONGO_URI=mongodb://... python data/db/seed_objective_templates.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running from the repo root.
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import DatabaseManager
from sarapp_db.mongo.int_id import next_int_id


OBJECTIVE_TEMPLATE_SEEDS: list[dict[str, Any]] = [
    {
        "code": "SAR-CMD-01",
        "title": "Establish incident command and planning rhythm",
        "description": "Set up unified command, confirm the incident organization, and schedule planning cycles for the search period.",
        "default_section": "Planning",
        "priority": "Urgent",
        "tags": ["command", "planning", "unified-command", "search"],
    },
    {
        "code": "SAR-WLD-01",
        "title": "Initiate wilderness search sectoring",
        "description": "Divide the search area into manageable sectors, assign hasty and grid teams, and track clue collection in the field.",
        "default_section": "Operations",
        "priority": "Urgent",
        "tags": ["wilderness", "hasty-team", "grid-search", "search-sectors"],
    },
    {
        "code": "SAR-URB-01",
        "title": "Organize urban clue-based search operations",
        "description": "Coordinate canvass, witness interviews, and area searches when the incident involves neighborhoods, parks, or developed areas.",
        "default_section": "Operations",
        "priority": "High",
        "tags": ["urban", "clue-search", "canvass", "missing-person"],
    },
    {
        "code": "SAR-WTR-01",
        "title": "Coordinate water and shoreline search operations",
        "description": "Integrate boat, shoreline, and dive resources while maintaining safe launch points, shoreline control, and recovery documentation.",
        "default_section": "Operations",
        "priority": "Urgent",
        "tags": ["water-rescue", "shoreline", "dive-team", "recovery"],
    },
    {
        "code": "SAR-WINT-01",
        "title": "Manage winter exposure and avalanche risk",
        "description": "Track weather, terrain, avalanche, and hypothermia hazards while staging warming, shelter, and rapid extraction support.",
        "default_section": "Safety",
        "priority": "Urgent",
        "tags": ["winter", "avalanche", "hypothermia", "risk-management"],
    },
    {
        "code": "SAR-AIR-01",
        "title": "Integrate air assets into the search plan",
        "description": "Coordinate helicopter, fixed-wing, and drone support with ground teams to avoid overlap and improve coverage of high-probability areas.",
        "default_section": "Operations",
        "priority": "High",
        "tags": ["air-search", "aviation", "uav", "deconfliction"],
    },
    {
        "code": "SAR-LOG-01",
        "title": "Sustain logistics for extended search operations",
        "description": "Maintain communications, lighting, fuel, food, shelter, transport, and base-camp support for an extended incident period.",
        "default_section": "Logistics",
        "priority": "High",
        "tags": ["logistics", "base-camp", "transport", "sustainment"],
    },
    {
        "code": "SAR-PIO-01",
        "title": "Maintain family liaison and public information updates",
        "description": "Provide approved status updates, manage family contact points, and coordinate public messaging so rumors do not outpace verified information.",
        "default_section": "Public Information",
        "priority": "Normal",
        "tags": ["pio", "family-liaison", "messaging", "public-information"],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _clean_tags(values: list[Any]) -> list[str]:
    tags: list[str] = []
    for value in values:
        tag = str(value).strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _seed_templates(col) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    now = _now()

    for seed in OBJECTIVE_TEMPLATE_SEEDS:
        code = str(seed["code"]).strip()
        if not code:
            continue
        existing = col.find_one({"code": code})
        if existing is not None:
            skipped += 1
            continue
        doc = {
            "_id": _new_id(),
            "int_id": next_int_id(col),
            "code": code,
            "title": str(seed["title"]).strip(),
            "description": str(seed["description"]).strip(),
            "default_section": str(seed["default_section"]).strip() or None,
            "priority": str(seed.get("priority") or "Normal"),
            "active": True,
            "tags": _clean_tags(list(seed.get("tags") or [])),
            "created_at": now,
            "updated_at": now,
        }
        col.insert_one(doc)
        inserted += 1

    return inserted, skipped


def main() -> int:
    print("=" * 72)
    print("SARApp objective template seed")
    print("=" * 72)

    mgr = DatabaseManager()
    if not mgr.is_connected():
        print("ERROR: Cannot connect to MongoDB. Check SARAPP_MONGO_URI.")
        return 1

    master_db = mgr.get_master_db()
    col = master_db[MasterCollections.OBJECTIVE_TEMPLATES]

    inserted, skipped = _seed_templates(col)

    print(f"Collection: {master_db.name}.{MasterCollections.OBJECTIVE_TEMPLATES}")
    print(f"Inserted:   {inserted}")
    print(f"Skipped:    {skipped}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
