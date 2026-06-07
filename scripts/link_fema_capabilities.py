#!/usr/bin/env python3
"""
Link capabilities to resource types (FEMA/NIMS and AHJ Custom) using discipline,
kind, and name matching.

Reads the resource_types and resource_capabilities tables, applies rule-based
matching, and writes resource_type_capabilities rows.  Idempotent: running
it again replaces the same links.

Usage:
    python scripts/link_fema_capabilities.py
    python scripts/link_fema_capabilities.py --db path/to/custom.db
    python scripts/link_fema_capabilities.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.admin.resource_types.data.resource_type_repository import ResourceTypeRepository

# ---------------------------------------------------------------------------
# Discipline → base capability names applied to every resource type in that
# discipline, before any name-based refinements.
# ---------------------------------------------------------------------------
_DISC_CAPS: dict[str, list[str]] = {
    # FEMA RTLT discipline strings
    "Search and Rescue": [
        "Technical Rescue",
    ],
    # Florida variants (& vs and, no trailing qualifier)
    "Search & Rescue": [
        "Technical Rescue",
    ],
    "Fire / Hazardous Materials": [
        "Structural Firefighting",
    ],
    "Emergency Medical Services": [
        "Advanced Life Support (ALS)",
        "Basic Life Support (BLS)",
        "Mass Casualty Operations",
    ],
    "Animal Emergency Response": [
        "Large Animal Rescue",
        "Small Animal Sheltering",
        "Veterinary Care",
    ],
    "Incident Management": [
        "Incident Command",
        "Planning / Intelligence",
        "Operations Coordination",
        "Safety Officer",
        "EOC Operations",
    ],
    "Emergency Management": [
        "EOC Operations",
        "Planning / Intelligence",
    ],
    "Law Enforcement Operations": [
        "Traffic Control",
        "Crowd Management",
        "Tactical Law Enforcement",
    ],
    # Florida variants
    "Law Enforcement": [
        "Traffic Control",
        "Crowd Management",
        "Tactical Law Enforcement",
    ],
    "Mass Care Services": [
        "Emergency Shelter Operations",
        "Evacuation Support",
        "Access and Functional Needs Support",
    ],
    "Medical and Public Health": [
        "Public Health Surveillance",
        "Mass Casualty Operations",
    ],
    "Public Works": [
        "Water Supply and Distribution",
        "Damage Assessment",
    ],
    "Communications": [
        "Voice Radio Communications",
        "Satellite Communications",
        "Mobile Command Operations",
        "Interoperability / Radio Patching",
        "Data / Network Communications",
        "Alert & Warning",
    ],
    "Logistics and Transportation": [
        "Ground Transport",
        "Supply Chain / Ordering",
        "Base Camp / Staging Support",
    ],
    "Geographic Info Systems and Info Technology": [
        "Planning / Intelligence",
        "Data / Network Communications",
    ],
    "Hazard Mitigation": [
        "Hazard Mitigation",
        "Damage Assessment",
    ],
    "Damage Assessment": [
        "Damage Assessment",
    ],
    "Cybersecurity": [
        "Cybersecurity Operations",
    ],
    "Prevention": [
        "CBRN Detection",
    ],
    # Florida-specific discipline strings (PDF artifact repetitions normalized via prefix match)
    "Command / Overhead": [
        "Incident Command",
        "EOC Operations",
        "Planning / Intelligence",
    ],
    "Public Information": [
        "Public Information",
    ],
    # "Resource Management..." (truncated repetition) handled via prefix matching below
    # "Communications..." (truncated repetition) handled via prefix matching below
}

# ---------------------------------------------------------------------------
# Kind → additional capability names (additive on top of discipline caps).
# Applied only when discipline does not already cover it.
# ---------------------------------------------------------------------------
_KIND_CAPS: dict[str, list[str]] = {
    "vehicle": ["Ground Transport"],
    "facility": ["Base Camp / Staging Support"],
    "aircraft": ["Air Transport"],
}

# ---------------------------------------------------------------------------
# Name keyword rules — each entry: (keywords, caps_to_add, caps_to_remove).
# keywords: all must appear (case-insensitive) in the resource type name.
# Applied after discipline + kind caps.
# ---------------------------------------------------------------------------
_NAME_RULES: list[tuple[list[str], list[str], list[str]]] = [
    # Search & Rescue specifics
    (["canine", "disaster"], ["K9 Search", "Structural Collapse Search & Rescue"], []),
    (["canine", "land"],     ["K9 Search", "Wildland Search Operations"], []),
    (["canine", "water"],    ["K9 Search", "Dive / Underwater Search"], []),
    (["canine", "detection", "explosives"], ["K9 Search", "Explosive Ordnance Disposal"], ["Technical Rescue"]),
    (["structural collapse"], ["Structural Collapse Search & Rescue"], []),
    (["urban search"],        ["Structural Collapse Search & Rescue"], []),
    (["us&r"],                ["Structural Collapse Search & Rescue"], []),
    (["swiftwater"],          ["Water / Swift Water Rescue"], []),
    (["stillwater"],          ["Water / Swift Water Rescue"], []),
    (["flood"],               ["Water / Swift Water Rescue"], []),
    (["waterborne", "search"], ["Water / Swift Water Rescue", "Maritime / Port Security"], []),
    (["mine", "rescue"],      ["Confined Space Rescue"], []),
    (["cave", "rescue"],      ["Confined Space Rescue"], []),
    (["mountain"],            ["High Angle / Rope Rescue"], []),
    (["air search"],          ["Air Transport", "Wildland Search Operations"], []),
    (["airborne reconnaissance"], ["Air Transport", "Wildland Search Operations"], []),
    (["fixed wing search"],   ["Air Transport", "Wildland Search Operations"], []),
    (["helicopter", "rescue"], ["Air Transport"], []),
    (["land search"],         ["Wildland Search Operations"], []),
    (["radio direction finding"], ["Voice Radio Communications"], ["Technical Rescue"]),

    # Fire & Hazmat specifics
    (["wildland"],            ["Wildland Firefighting"], ["Structural Firefighting"]),
    (["hand crew"],           ["Wildland Firefighting"], ["Structural Firefighting"]),
    (["aerial apparatus"],    ["Aerial Firefighting"], []),
    (["helicopter", "firefighting"], ["Aerial Firefighting"], []),
    (["fire boat"],           ["Structural Firefighting", "Maritime / Port Security"], []),
    (["hazardous materials"], ["Hazardous Materials Response"], []),
    (["hazmat"],              ["Hazardous Materials Response"], []),
    (["foam"],                ["Foam / Class B Fire Suppression"], []),
    (["fuel tender"],         ["Fuel and POL Services"], ["Structural Firefighting"]),
    (["water tender"],        ["Water Supply and Distribution"], []),
    (["crew transport"],      ["Ground Transport"], ["Structural Firefighting"]),
    (["incident management team", "firefighting"], ["Incident Command", "Planning / Intelligence", "Operations Coordination"], ["Structural Firefighting"]),
    (["area command"],        ["Incident Command"], []),
    (["interagency buying"],  ["Supply Chain / Ordering", "Finance and Administration"], ["Structural Firefighting"]),
    (["mobile communications unit"], ["Mobile Command Operations", "Voice Radio Communications", "Interoperability / Radio Patching"], ["Structural Firefighting"]),

    # EMS specifics
    (["air ambulance"],       ["Aeromedical Transport"], ["Advanced Life Support (ALS)", "Basic Life Support (BLS)"]),
    (["advanced life support"], ["Advanced Life Support (ALS)"], ["Basic Life Support (BLS)"]),
    (["basic life support"],  ["Basic Life Support (BLS)"], ["Advanced Life Support (ALS)"]),
    (["als"],                 ["Advanced Life Support (ALS)"], []),
    (["bls"],                 ["Basic Life Support (BLS)"], []),
    (["ambulance"],           ["Ground Transport"], []),
    (["ambulance task force"], ["Mass Casualty Operations"], []),

    # Incident Management specifics
    (["cism"],                ["Mental Health / Crisis Intervention"], ["Safety Officer"]),
    (["critical incident stress"], ["Mental Health / Crisis Intervention"], ["Safety Officer"]),
    (["evacuation coordination"], ["Evacuation Support"], []),
    (["airborne communications relay"], ["Air Transport", "Voice Radio Communications", "Satellite Communications"], ["Incident Command", "Safety Officer"]),
    (["mobile communications center"], ["Mobile Command Operations", "Voice Radio Communications", "Interoperability / Radio Patching"], ["Safety Officer"]),
    (["mobile eoc"],          ["Mobile Command Operations", "EOC Operations"], ["Safety Officer"]),
    (["suas"],                ["Air Transport"], ["Incident Command", "Safety Officer"]),
    (["unmanned aircraft"],   ["Air Transport"], ["Incident Command", "Safety Officer"]),

    # Law Enforcement specifics
    (["bomb response"],       ["Explosive Ordnance Disposal"], ["Tactical Law Enforcement", "Traffic Control", "Crowd Management"]),
    (["canine detection", "explosives"], ["K9 Search", "Explosive Ordnance Disposal"], ["Tactical Law Enforcement", "Traffic Control", "Crowd Management"]),
    (["special weapons and tactics"], ["Tactical Law Enforcement"], ["Traffic Control", "Crowd Management"]),
    (["crisis negotiation"],  ["Tactical Law Enforcement"], ["Traffic Control", "Crowd Management"]),
    (["mobile field force"],  ["Crowd Management", "Tactical Law Enforcement"], ["Traffic Control"]),
    (["patrol team"],         ["Traffic Control"], ["Tactical Law Enforcement", "Crowd Management"]),
    (["public safety dive"],  ["Dive / Underwater Search"], ["Tactical Law Enforcement", "Traffic Control", "Crowd Management"]),
    (["waterborne response"], ["Maritime / Port Security", "Water / Swift Water Rescue"], ["Tactical Law Enforcement", "Traffic Control", "Crowd Management"]),
    (["law enforcement aviation"], ["Air Transport"], []),
    (["law enforcement observation aircraft"], ["Air Transport"], []),

    # Mass Care specifics
    (["kitchen"],             ["Feeding Operations"], ["Emergency Shelter Operations"]),
    (["food service"],        ["Feeding Operations"], ["Emergency Shelter Operations"]),
    (["point of distribution"], ["Supply Chain / Ordering"], ["Emergency Shelter Operations"]),
    (["distribution of emergency supplies"], ["Supply Chain / Ordering"], ["Emergency Shelter Operations"]),
    (["donations"],           ["Donations and Volunteer Management"], ["Emergency Shelter Operations"]),
    (["donated goods"],       ["Donations and Volunteer Management"], ["Emergency Shelter Operations"]),
    (["receiving, staging"],  ["Base Camp / Staging Support", "Supply Chain / Ordering"], ["Emergency Shelter Operations"]),
    (["mass evacuee"],        ["Evacuation Support"], []),
    (["shelter facility selection"], ["Emergency Shelter Operations"], []),
    (["shelter management"],  ["Emergency Shelter Operations"], []),
    (["evacuation shelter"],  ["Emergency Shelter Operations", "Evacuation Support"], []),

    # Medical and Public Health specifics
    (["behavioral health"],   ["Mental Health / Crisis Intervention"], ["Mass Casualty Operations"]),
    (["isolation and quarantine"], ["Public Health Surveillance"], []),
    (["epidemiol"],           ["Public Health Surveillance"], []),
    (["laboratory"],          ["Public Health Surveillance"], []),
    (["pharmacy"],            ["Pharmaceutical Cache"], ["Mass Casualty Operations"]),
    (["pharmacist"],          ["Pharmaceutical Cache"], ["Mass Casualty Operations"]),
    (["medical countermeasure"], ["Pharmaceutical Cache", "Mass Casualty Operations"], []),
    (["point of dispensing"], ["Pharmaceutical Cache", "Mass Casualty Operations"], []),
    (["palliative care"],     ["Mental Health / Crisis Intervention"], ["Mass Casualty Operations"]),
    (["radiological services"], ["CBRN Detection"], []),
    (["receiving, staging", "storage"], ["Base Camp / Staging Support", "Supply Chain / Ordering"], []),
    (["fatality management"], ["Mass Casualty Operations"], ["Public Health Surveillance"]),
    (["morgue"],              ["Mass Casualty Operations"], ["Public Health Surveillance"]),
    (["public health and medical team in a shelter"], ["Emergency Shelter Operations", "Access and Functional Needs Support"], []),
    (["healthcare resource coordination"], ["Supply Chain / Ordering"], []),

    # Public Works specifics
    (["wastewater"],          ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["sewer"],               ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["water pump"],          ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["water treatment"],     ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["water distribution"],  ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["water main"],          ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["water sector"],        ["Water Supply and Distribution"], []),
    (["water valve"],         ["Water Supply and Distribution"], ["Damage Assessment"]),
    (["debris assessment"],   ["Debris Removal and Clearance", "Damage Assessment"], []),
    (["debris monitoring"],   ["Debris Removal and Clearance"], []),
    (["public works support"], ["Damage Assessment"], []),
    (["post-disaster building safety"], ["Damage Assessment"], []),

    # Animal Emergency specifics
    (["animal search and rescue"], ["Large Animal Rescue", "K9 Search"], ["Small Animal Sheltering"]),
    (["animal sheltering", "cohabitated"], ["Small Animal Sheltering", "Emergency Shelter Operations", "Access and Functional Needs Support"], ["Large Animal Rescue"]),
    (["animal sheltering", "collocated"], ["Small Animal Sheltering", "Emergency Shelter Operations", "Access and Functional Needs Support"], ["Large Animal Rescue"]),
    (["animal sheltering", "animal-only"], ["Small Animal Sheltering"], ["Large Animal Rescue"]),
    (["animal evacuation"],   ["Evacuation Support"], []),
    (["animal depopulation"], [], ["Small Animal Sheltering"]),
    (["companion animal decontamination"], ["Decontamination Operations", "Small Animal Sheltering"], ["Large Animal Rescue"]),
    (["veterinary medical"],  ["Veterinary Care"], ["Large Animal Rescue", "Small Animal Sheltering"]),
    (["animal and agriculture damage"], ["Damage Assessment"], ["Large Animal Rescue", "Veterinary Care"]),

    # Prevention / CBRN
    (["radiation detector"],  ["CBRN Detection"], []),
    (["radiological nuclear detection"], ["CBRN Detection"], []),
    (["radio-isotope"],       ["CBRN Detection"], []),

    # Emergency Management specifics
    (["disaster cost recovery"], ["Finance and Administration"], []),
    (["human services disaster assessment"], ["Damage Assessment"], []),
    (["human services recovery"], ["Donations and Volunteer Management"], []),
    (["housing task force"],  ["Evacuation Support"], []),
    (["post-disaster building safety evaluation"], ["Damage Assessment"], []),

    # Logistics specifics
    (["logistics staging"],   ["Base Camp / Staging Support"], []),
    (["logistics support"],   ["Supply Chain / Ordering"], []),
    (["distribution support"], ["Supply Chain / Ordering"], []),

    # Communications specifics
    (["land mobile radio"],   ["Voice Radio Communications", "Interoperability / Radio Patching"], ["Satellite Communications", "Mobile Command Operations", "Data / Network Communications", "Alert & Warning"]),
    (["virtual operations support"], ["Data / Network Communications"], ["Voice Radio Communications", "Satellite Communications", "Mobile Command Operations", "Interoperability / Radio Patching", "Alert & Warning"]),

    # GIS specifics
    (["gis field data collection"], ["Planning / Intelligence"], []),
    (["gis map support"],     ["Planning / Intelligence"], []),

    # Generic EOC (the one resource type with blank discipline)
    (["emergency operations center management"], ["EOC Operations", "Incident Command", "Planning / Intelligence", "Operations Coordination"], []),

    # ------------------------------------------------------------------ #
    # Florida FFCA-SERP specifics
    # ------------------------------------------------------------------ #

    # Overhead / command positions
    (["eoc finance"],         ["Finance and Administration", "EOC Operations"], ["Planning / Intelligence"]),
    (["eoc operations section chief"], ["EOC Operations", "Operations Coordination", "Incident Command"], ["Planning / Intelligence"]),
    (["planning section chief"], ["Planning / Intelligence", "EOC Operations"], ["Incident Command"]),
    (["logistics section chief"], ["Supply Chain / Ordering", "Base Camp / Staging Support", "EOC Operations"], ["Planning / Intelligence", "Incident Command"]),
    (["incident management team (imt)"], ["Incident Command", "Planning / Intelligence", "Operations Coordination", "Finance and Administration", "Safety Officer", "EOC Operations"], []),
    (["serp", "liaison"],     ["EOC Operations", "Planning / Intelligence", "Operations Coordination"], ["Incident Command"]),
    (["serp", "specialist"],  ["EOC Operations", "Planning / Intelligence"], ["Incident Command"]),
    (["serp seoc"],           ["EOC Operations", "Planning / Intelligence"], ["Incident Command"]),

    # Communications / dispatch
    (["telecommunicator emergency response"], ["Voice Radio Communications", "Alert & Warning", "Interoperability / Radio Patching"], ["EOC Operations", "Planning / Intelligence"]),
    (["telecommunicator"],    ["Voice Radio Communications", "Alert & Warning"], ["EOC Operations", "Planning / Intelligence"]),
    (["radio technician"],    ["Voice Radio Communications", "Interoperability / Radio Patching"], ["EOC Operations", "Planning / Intelligence"]),
    (["mobile communications unit"], ["Mobile Command Operations", "Voice Radio Communications", "Interoperability / Radio Patching"], ["EOC Operations", "Planning / Intelligence"]),

    # EMS vehicles
    (["ambulance", "ground"], ["Ground Transport", "Advanced Life Support (ALS)", "Basic Life Support (BLS)"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),
    (["ambulance strike team"], ["Ground Transport", "Mass Casualty Operations"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),
    (["mass casualty support vehicle"], ["Mass Casualty Operations", "Ground Transport"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),
    (["multi-patient medical transport"], ["Mass Casualty Operations", "Ground Transport"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),
    (["rescue", "ems", "strike"], ["Advanced Life Support (ALS)", "Mass Casualty Operations"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),
    (["rescue", "ems"],       ["Advanced Life Support (ALS)", "Technical Rescue", "Mass Casualty Operations"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),
    (["emergency medical task force"], ["Advanced Life Support (ALS)", "Basic Life Support (BLS)", "Mass Casualty Operations"], ["Incident Command", "EOC Operations", "Planning / Intelligence"]),

    # Fire apparatus
    (["brush/woods"],         ["Wildland Firefighting"], ["Structural Firefighting"]),
    (["air supply truck"],    ["Structural Firefighting", "Hazardous Materials Response"], ["Structural Firefighting"]),  # SCBA refill
    (["crash fire rescue"],   ["Structural Firefighting", "Aerial Firefighting"], []),  # ARFF
    (["firefighter rehab"],   ["Structural Firefighting", "Wildland Firefighting"], []),
    (["portable fire pump"],  ["Structural Firefighting", "Water Supply and Distribution"], []),
    (["water tender"],        ["Water Supply and Distribution", "Structural Firefighting"], []),
    (["structural task force"], ["Structural Firefighting"], []),
    (["fire engine strike team", "wildland"], ["Wildland Firefighting"], ["Structural Firefighting"]),
    (["fire engine strike"],  ["Structural Firefighting"], []),
    (["fire engine", "pumper"], ["Structural Firefighting"], []),
    (["fire investigator"],   ["Structural Firefighting", "Wildland Firefighting"], ["Structural Firefighting"]),
    (["helicopters, firefighting"], ["Aerial Firefighting", "Air Transport"], ["Structural Firefighting"]),
    (["light truck"],         ["Ground Transport"], ["Structural Firefighting"]),
    (["all terrain vehicle"], ["Ground Transport"], ["Structural Firefighting"]),
    (["atv"],                 ["Ground Transport"], ["Structural Firefighting"]),
    (["field mobile mechanic"], ["Equipment Maintenance", "Ground Transport"], ["Structural Firefighting"]),
    (["foam bulk"],           ["Foam / Class B Fire Suppression"], ["Structural Firefighting"]),
    (["foam tender"],         ["Foam / Class B Fire Suppression", "Structural Firefighting"], []),

    # Law enforcement (Florida)
    (["bomb team"],           ["Explosive Ordnance Disposal"], ["Traffic Control", "Crowd Management", "Tactical Law Enforcement"]),

    # Public information
    (["public information officer"], ["Public Information"], ["Traffic Control", "Crowd Management", "Tactical Law Enforcement"]),

    # SAR (Florida subtypes)
    (["canine search & rescue team", "disaster"], ["K9 Search", "Structural Collapse Search & Rescue"], ["Technical Rescue"]),
    (["canine search & rescue team", "land cadaver"], ["K9 Search", "Wildland Search Operations"], ["Technical Rescue"]),
    (["canine search & rescue team", "water"], ["K9 Search", "Dive / Underwater Search"], ["Technical Rescue"]),
    (["canine search & rescue team", "wilderness air scent"], ["K9 Search", "Wildland Search Operations"], ["Technical Rescue"]),
    (["canine search & rescue team", "wilderness tracking"], ["K9 Search", "Wildland Search Operations"], ["Technical Rescue"]),
    (["heavy rescue"],        ["Technical Rescue", "Structural Collapse Search & Rescue"], []),
    (["surface water rescue"], ["Water / Swift Water Rescue"], ["Technical Rescue"]),
    (["technical rescue team"], ["Technical Rescue", "Confined Space Rescue", "High Angle / Rope Rescue"], []),
    (["trench rescue team"],  ["Trench Rescue", "Technical Rescue"], []),
    (["wilderness search & rescue"], ["Wildland Search Operations"], ["Technical Rescue"]),
    (["urban search & rescue task force", "florida"], ["Structural Collapse Search & Rescue", "Technical Rescue", "Confined Space Rescue", "Water / Swift Water Rescue", "Trench Rescue"], []),
]


def _normalize_discipline(raw: str) -> str:
    """Clean PDF-artifact repeated discipline strings like 'CommsCommunicationsComms'."""
    s = raw.strip()
    # Detect repetition: try progressively longer prefixes
    for n in range(4, len(s) // 2 + 1):
        prefix = s[:n]
        if s.startswith(prefix * 2):
            return prefix
    # Prefix-match known FL disciplines from truncated strings
    for key in _DISC_CAPS:
        if s.startswith(key[:min(len(key), 20)]):
            return key
    return s


def _match_caps(name: str, discipline: str, kind: str) -> set[str]:
    """Return the set of capability names to link to a resource type."""
    name_lower = name.lower()
    disc_key = _normalize_discipline(discipline)
    kind_lower = kind.lower().strip()

    caps: set[str] = set()

    # 1. Discipline baseline
    for cap in _DISC_CAPS.get(disc_key, []):
        caps.add(cap)

    # 2. Kind additions
    for cap in _KIND_CAPS.get(kind_lower, []):
        caps.add(cap)

    # 3. Name rules (add and remove)
    for keywords, adds, removes in _NAME_RULES:
        if all(re.search(r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])', name_lower) for kw in keywords):
            for cap in adds:
                caps.add(cap)
            for cap in removes:
                caps.discard(cap)

    return caps


def link(db_path: Path | None = None, dry_run: bool = False) -> None:
    repo = ResourceTypeRepository(db_path)

    # Load capability name → id
    cap_rows = repo.list_capabilities(include_inactive=True)
    cap_by_name: dict[str, int] = {row["name"]: row["id"] for row in cap_rows}
    print(f"Capabilities available: {len(cap_by_name)}")

    # Load FEMA resource types with their discipline and kind via direct SQL
    db = Path(db_path) if db_path else repo.db_path
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT rt.id, rt.name, rt.category,
               COALESCE(MIN(fm.discipline), '') AS discipline,
               COALESCE(MIN(fm.kind), '')       AS kind
        FROM resource_types rt
        LEFT JOIN resource_type_fema_mappings fm ON fm.resource_type_id = rt.id
        WHERE rt.source IN ('FEMA/NIMS', 'AHJ Custom')
        GROUP BY rt.id
        ORDER BY discipline, rt.name
    """).fetchall()
    conn.close()

    print(f"FEMA resource types to link: {len(rows)}\n")

    unknown_caps: set[str] = set()
    linked = 0
    skipped = 0

    for row in rows:
        rt_id   = int(row["id"])
        name    = row["name"]
        disc    = row["discipline"]
        kind    = row["kind"]

        cap_names = _match_caps(name, disc, kind)

        # Resolve names to IDs; log any that don't exist in the DB
        cap_ids: list[int] = []
        for cap_name in sorted(cap_names):
            if cap_name in cap_by_name:
                cap_ids.append(cap_by_name[cap_name])
            else:
                unknown_caps.add(cap_name)

        if not cap_ids:
            skipped += 1
            if dry_run:
                print(f"  SKIP  [{disc[:28]:28s}]  {name}")
            continue

        if dry_run:
            cap_list = ", ".join(sorted(cap_names))
            print(f"  LINK  [{disc[:28]:28s}]  {name}")
            print(f"         -> {cap_list}")
        else:
            repo.set_resource_type_capabilities(rt_id, cap_ids)

        linked += 1

    print()
    print("=" * 60)
    print(f"Resource types linked: {linked}")
    print(f"Resource types with no matching caps: {skipped}")
    if unknown_caps:
        print(f"\nWARNING — cap names in rules but not in DB:")
        for name in sorted(unknown_caps):
            print(f"  '{name}'")
    if dry_run:
        print("\n(dry-run — no changes written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Link capabilities to FEMA resource types")
    parser.add_argument("--db", metavar="PATH", help="Path to SQLite DB (default: data/master.db)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be linked without writing anything")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None

    print("FEMA Resource Type -> Capability Linker")
    print("=" * 60)
    link(db_path=db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
