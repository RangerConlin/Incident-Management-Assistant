"""Default organization-type list and rank-structure templates.

Ported from the pre-MongoDB-cutover SQLite repository (see git history for
modules/personnel/units_organizations/models/repository.py prior to the
"Complete personnel module MongoDB migration" commit) — that version seeded
this data automatically on first repository instantiation; the migration
dropped the seeding step entirely. This module restores it, seeding via the
same /api/master/* endpoints every other write in this repository uses.
"""

from __future__ import annotations

from typing import Any

from utils.api_client import api_client, APIError

# (name, description, sort_order) — unchanged from the original SQLite seed list.
ORGANIZATION_TYPES: list[tuple[str, str, int]] = [
    ("Air Agency", "Aviation-focused public safety or regulatory agency", 10),
    ("Ground SAR", "Ground search and rescue organizations", 20),
    ("Law Enforcement", "Police, sheriff, or patrol agencies", 30),
    ("Fire/Rescue", "Fire service and rescue organizations", 40),
    ("EMS", "Emergency medical services organizations", 50),
    ("Government", "General government organizations", 60),
    ("Volunteer Organization", "Volunteer-run organizations", 70),
    ("NGO", "Non-governmental organizations", 80),
    ("Federal", "Federal/national level organizations", 90),
    ("State", "State or provincial organizations", 100),
    ("County", "County or regional organizations", 110),
    ("Municipal", "City or municipal organizations", 120),
    ("Military", "Military organizations", 130),
    ("Private Contractor", "Private companies/contractors", 140),
    ("Amateur Radio", "Amateur radio/ARES/RACES groups", 150),
    ("Aviation Support", "Air support/aviation assistance units", 160),
    ("Communications Unit", "Radio/comms units and shops", 170),
    ("Other", "Other/uncategorized organizations", 180),
]

# (name, description, organization_type_name, ranks) — organization_type_name
# is looked up against ORGANIZATION_TYPES above; if there's no exact match
# (as with "Fire Department" / "Search and Rescue" / "Volunteer / NGO" below,
# which don't match any seeded type name — a pre-existing mismatch carried
# over unchanged from the original seed data) the template is just created
# without an organization_type_id link, same as before.
# Each rank tuple is (sort_order, rank_code, rank_name, short_display).
RANK_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Fire Department (Standard)",
        "description": "Common municipal fire service rank progression",
        "organization_type_name": "Fire Department",
        "ranks": [
            (0, "FF", "Firefighter", "FF"),
            (1, "ENG", "Engineer / Driver", "ENG"),
            (2, "LT", "Lieutenant", "LT"),
            (3, "CPT", "Captain", "CPT"),
            (4, "BC", "Battalion Chief", "BC"),
            (5, "DC", "Division Chief", "DC"),
            (6, "AC", "Assistant Chief", "AC"),
            (7, "DCH", "Deputy Chief", "D/Chief"),
            (8, "CH", "Fire Chief", "Chief"),
        ],
    },
    {
        "name": "Law Enforcement (Standard)",
        "description": "Typical police/sheriff rank progression",
        "organization_type_name": "Law Enforcement",
        "ranks": [
            (0, "PO", "Police Officer", "Officer"),
            (1, "SPO", "Senior Police Officer", "Sr Ofc"),
            (2, "CPL", "Corporal", "Cpl"),
            (3, "SGT", "Sergeant", "Sgt"),
            (4, "LT", "Lieutenant", "Lt"),
            (5, "CPT", "Captain", "Capt"),
            (6, "MAJ", "Major / Commander", "Maj"),
            (7, "DCH", "Deputy Chief", "D/Chief"),
            (8, "CH", "Chief of Police", "Chief"),
        ],
    },
    {
        "name": "EMS (Standard)",
        "description": "Common EMS rank progression",
        "organization_type_name": "EMS",
        "ranks": [
            (0, "EMT", "EMT", "EMT"),
            (1, "AEMT", "Advanced EMT", "AEMT"),
            (2, "PM", "Paramedic", "Medic"),
            (3, "FTO", "Field Training Officer", "FTO"),
            (4, "SUP", "Supervisor", "Supv"),
            (5, "CPT", "Captain", "Capt"),
            (6, "BC", "Battalion Chief", "BC"),
            (7, "CH", "Chief", "Chief"),
        ],
    },
    {
        "name": "Search and Rescue (Standard)",
        "description": "Typical SAR team role progression",
        "organization_type_name": "Search and Rescue",
        "ranks": [
            (0, "MEM", "Member", "Member"),
            (1, "SMEM", "Senior Member", "Sr Mbr"),
            (2, "TL", "Team Leader", "TL"),
            (3, "OPL", "Operations Leader", "Ops Lead"),
            (4, "PLN", "Planning Lead", "Plans"),
            (5, "LOG", "Logistics Lead", "Log"),
            (6, "SC", "Section Chief", "Sec Chief"),
            (7, "IC", "Incident Commander", "IC"),
        ],
    },
    {
        "name": "Volunteer / NGO (Standard)",
        "description": "Generic volunteer/NGO leadership progression",
        "organization_type_name": "Volunteer / NGO",
        "ranks": [
            (0, "VOL", "Volunteer", "Vol"),
            (1, "LV", "Lead Volunteer", "Lead Vol"),
            (2, "TL", "Team Leader", "TL"),
            (3, "COOR", "Coordinator", "Coord"),
            (4, "MGR", "Manager", "Mgr"),
            (5, "DIR", "Director", "Dir"),
        ],
    },
]


def seed_if_needed() -> None:
    """Idempotently ensure default organization types and rank-structure
    templates (with their ranks) exist. Safe to call on every repository
    instantiation — each insert is guarded by a name lookup first.
    """
    try:
        _seed_organization_types()
        _seed_rank_templates()
    except APIError:
        # No server reachable (e.g. offline) — nothing to seed against right now.
        pass


def _seed_organization_types() -> None:
    existing_names = {t.get("name") for t in (api_client.get("/api/master/types") or [])}
    for name, description, sort_order in ORGANIZATION_TYPES:
        if name in existing_names:
            continue
        api_client.post("/api/master/types", json={"name": name, "description": description, "sort_order": sort_order})


def _seed_rank_templates() -> None:
    existing_types = {t.get("name"): t.get("int_id") for t in (api_client.get("/api/master/types") or [])}
    existing_structures = {
        s.get("name"): s.get("int_id")
        for s in (api_client.get("/api/master/rank-structures") or [])
        if s.get("is_system_template")
    }

    for template in RANK_TEMPLATES:
        name = template["name"]
        structure_id = existing_structures.get(name)
        if structure_id is None:
            org_type_id = existing_types.get(template["organization_type_name"])
            created = api_client.post("/api/master/rank-structures", json={
                "name": name,
                "description": template["description"],
                "organization_type_id": org_type_id,
                "is_system_template": True,
            })
            structure_id = created.get("int_id") if created else None
        if structure_id is None:
            continue

        existing_ranks = api_client.get("/api/master/ranks", params={"structure_id": structure_id}) or []
        if existing_ranks:
            continue
        for sort_order, rank_code, rank_name, _short_display in template["ranks"]:
            api_client.post("/api/master/ranks", json={
                "rank_structure_id": structure_id,
                "name": rank_name,
                "abbreviation": rank_code,
                "rank_order": sort_order,
            })
