#!/usr/bin/env python3
"""
Seed standard emergency management capabilities into the Resource Type Library.

These capability tags represent common operational functions drawn from NIMS,
ICS, and FEMA resource typing disciplines.  They can be linked to resource types
for filtering, smart search, and planning workflows.

Idempotent: capabilities whose name already exists are skipped.

Usage:
    python scripts/seed_capabilities.py
    python scripts/seed_capabilities.py --db path/to/custom.db
    python scripts/seed_capabilities.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.admin.resource_types.data.resource_type_repository import ResourceTypeRepository
from modules.admin.resource_types.models.resource_type_models import ResourceCapability

# ---------------------------------------------------------------------------
# Capability definitions
# Each entry: name, category, description, aliases (list)
# ---------------------------------------------------------------------------
CAPABILITIES: list[dict] = [

    # ------------------------------------------------------------------ #
    # Search & Rescue
    # ------------------------------------------------------------------ #
    {
        "name": "Technical Rescue",
        "category": "Search & Rescue",
        "description": "Specialized rescue operations using ropes, rigging, shoring, and technical equipment.",
        "aliases": ["Technical Search and Rescue", "USAR"],
    },
    {
        "name": "Structural Collapse Search & Rescue",
        "category": "Search & Rescue",
        "description": "Search and rescue operations within or around collapsed structures.",
        "aliases": ["Collapse Rescue", "USAR Structural"],
    },
    {
        "name": "Confined Space Rescue",
        "category": "Search & Rescue",
        "description": "Entry and rescue operations in permit-required confined spaces.",
        "aliases": ["Confined Space Entry"],
    },
    {
        "name": "High Angle / Rope Rescue",
        "category": "Search & Rescue",
        "description": "Rescue operations on steep terrain, cliffs, or structures using rope systems.",
        "aliases": ["Rope Rescue", "Vertical Rescue", "High Angle Rescue"],
    },
    {
        "name": "Water / Swift Water Rescue",
        "category": "Search & Rescue",
        "description": "Rescue operations in moving or flood water environments.",
        "aliases": ["Swift Water Rescue", "Flood Rescue", "River Rescue"],
    },
    {
        "name": "Dive / Underwater Search",
        "category": "Search & Rescue",
        "description": "Underwater search, recovery, and rescue operations using SCUBA or surface-supplied systems.",
        "aliases": ["Dive Rescue", "Underwater Search", "Public Safety Diving"],
    },
    {
        "name": "Wildland Search Operations",
        "category": "Search & Rescue",
        "description": "Ground search operations in undeveloped terrain, wilderness, or backcountry.",
        "aliases": ["Wilderness Search", "Ground Search"],
    },
    {
        "name": "K9 Search",
        "category": "Search & Rescue",
        "description": "Search operations utilizing trained search dogs for live-find or human remains detection.",
        "aliases": ["Canine Search", "Dog Search", "K-9"],
    },
    {
        "name": "Trench Rescue",
        "category": "Search & Rescue",
        "description": "Rescue operations in trench cave-in and excavation emergencies.",
        "aliases": ["Trench Collapse"],
    },

    # ------------------------------------------------------------------ #
    # Fire & Hazmat
    # ------------------------------------------------------------------ #
    {
        "name": "Structural Firefighting",
        "category": "Fire & Hazmat",
        "description": "Suppression and rescue operations in commercial or residential structure fires.",
        "aliases": ["Structure Fire", "Interior Attack"],
    },
    {
        "name": "Wildland Firefighting",
        "category": "Fire & Hazmat",
        "description": "Suppression and containment of fires in wildland, brush, or interface environments.",
        "aliases": ["Wildfire Suppression", "Forest Fire", "WUI Firefighting"],
    },
    {
        "name": "Aerial Firefighting",
        "category": "Fire & Hazmat",
        "description": "Airborne delivery of water or fire retardant to suppress or contain fires.",
        "aliases": ["Air Attack", "Air Tanker Operations", "Helitack"],
    },
    {
        "name": "Hazardous Materials Response",
        "category": "Fire & Hazmat",
        "description": "Detection, containment, and mitigation of hazardous chemical, biological, or radiological releases.",
        "aliases": ["HazMat", "Hazmat Response", "Chemical Response"],
    },
    {
        "name": "Decontamination Operations",
        "category": "Fire & Hazmat",
        "description": "Removal of hazardous contaminants from personnel, equipment, or the public.",
        "aliases": ["Decon", "Mass Decontamination"],
    },
    {
        "name": "CBRN Detection",
        "category": "Fire & Hazmat",
        "description": "Detection and identification of chemical, biological, radiological, and nuclear agents.",
        "aliases": ["WMD Detection", "CBRNE", "Chemical Detection"],
    },
    {
        "name": "Foam / Class B Fire Suppression",
        "category": "Fire & Hazmat",
        "description": "Suppression of flammable liquid fires using AFFF or other foam concentrates.",
        "aliases": ["Class B Fire", "AFFF", "Foam Application"],
    },

    # ------------------------------------------------------------------ #
    # Medical
    # ------------------------------------------------------------------ #
    {
        "name": "Advanced Life Support (ALS)",
        "category": "Medical",
        "description": "Paramedic-level prehospital care including advanced airway management, IV/IO access, and medication administration.",
        "aliases": ["ALS", "Paramedic", "Advanced Cardiac Life Support"],
    },
    {
        "name": "Basic Life Support (BLS)",
        "category": "Medical",
        "description": "EMT-level prehospital care including CPR, splinting, bleeding control, and oxygen therapy.",
        "aliases": ["BLS", "EMT", "First Responder Medical"],
    },
    {
        "name": "Mass Casualty Operations",
        "category": "Medical",
        "description": "Triage, treatment, and transport coordination during multi-casualty or mass casualty incidents.",
        "aliases": ["MCI", "Mass Casualty Incident", "Triage"],
    },
    {
        "name": "Aeromedical Transport",
        "category": "Medical",
        "description": "Patient transport by rotary or fixed-wing aircraft with in-flight medical care.",
        "aliases": ["Air Ambulance", "Medevac", "Flight Medic"],
    },
    {
        "name": "Trauma / Surgical Care",
        "category": "Medical",
        "description": "Advanced trauma stabilization and surgical intervention capabilities.",
        "aliases": ["Surgical Cache", "ATLS", "Trauma Surgery"],
    },
    {
        "name": "Public Health Surveillance",
        "category": "Medical",
        "description": "Epidemiological monitoring and disease surveillance in emergency or post-disaster settings.",
        "aliases": ["Disease Surveillance", "Epidemiology", "Health Monitoring"],
    },
    {
        "name": "Pharmaceutical Cache",
        "category": "Medical",
        "description": "Stockpile or push-package of medications, vaccines, or medical countermeasures.",
        "aliases": ["Medical Cache", "SNS", "Medication Cache"],
    },
    {
        "name": "Mental Health / Crisis Intervention",
        "category": "Medical",
        "description": "Behavioral health support and crisis counseling for disaster survivors and responders.",
        "aliases": ["CISM", "Crisis Counseling", "Behavioral Health", "Psychological First Aid"],
    },

    # ------------------------------------------------------------------ #
    # Law Enforcement
    # ------------------------------------------------------------------ #
    {
        "name": "Tactical Law Enforcement",
        "category": "Law Enforcement",
        "description": "High-risk law enforcement operations including SWAT, hostage rescue, and active threat response.",
        "aliases": ["SWAT", "SRT", "Special Response Team"],
    },
    {
        "name": "Explosive Ordnance Disposal",
        "category": "Law Enforcement",
        "description": "Detection, assessment, and disposal of explosive devices and ordnance.",
        "aliases": ["EOD", "Bomb Squad", "IED Disposal"],
    },
    {
        "name": "Crowd Management",
        "category": "Law Enforcement",
        "description": "Monitoring, controlling, and managing large crowds at events or civil unrest situations.",
        "aliases": ["Civil Unrest", "Riot Control", "Crowd Control"],
    },
    {
        "name": "Traffic Control",
        "category": "Law Enforcement",
        "description": "Direction and management of vehicle traffic at scenes, evacuation routes, or road closures.",
        "aliases": ["Traffic Direction", "Road Closure", "Evacuation Traffic"],
    },
    {
        "name": "Maritime / Port Security",
        "category": "Law Enforcement",
        "description": "Law enforcement and security operations on or around navigable waterways and ports.",
        "aliases": ["Marine Patrol", "Port Security", "Coast Guard Coordination"],
    },
    {
        "name": "Cybersecurity Operations",
        "category": "Law Enforcement",
        "description": "Detection, mitigation, and response to cyber incidents affecting critical infrastructure.",
        "aliases": ["Cyber Response", "IT Security Incident"],
    },

    # ------------------------------------------------------------------ #
    # Communications
    # ------------------------------------------------------------------ #
    {
        "name": "Voice Radio Communications",
        "category": "Communications",
        "description": "Tactical and command voice radio operations using VHF, UHF, or 700/800 MHz systems.",
        "aliases": ["Radio Comms", "Tactical Radio", "Portable Radio"],
    },
    {
        "name": "Satellite Communications",
        "category": "Communications",
        "description": "Voice, data, and video communications via satellite when terrestrial infrastructure is degraded.",
        "aliases": ["SATCOM", "Satellite Phone", "VSAT"],
    },
    {
        "name": "Mobile Command Operations",
        "category": "Communications",
        "description": "Deployable command-and-control communications platform for field operations.",
        "aliases": ["Mobile Command Post", "MCP", "Command Vehicle"],
    },
    {
        "name": "Interoperability / Radio Patching",
        "category": "Communications",
        "description": "Bridging disparate radio systems to enable cross-agency voice communications.",
        "aliases": ["ISSI", "Console Patching", "Radio Interop"],
    },
    {
        "name": "Data / Network Communications",
        "category": "Communications",
        "description": "Field deployable data networking supporting CAD, GIS, or situational awareness systems.",
        "aliases": ["Tactical Network", "Field IT", "Cellular on Wheels"],
    },
    {
        "name": "Alert & Warning",
        "category": "Communications",
        "description": "Public alerting and warning dissemination using EAS, WEA, sirens, or social media.",
        "aliases": ["EAS", "Wireless Emergency Alert", "Public Warning"],
    },

    # ------------------------------------------------------------------ #
    # Logistics & Support
    # ------------------------------------------------------------------ #
    {
        "name": "Ground Transport",
        "category": "Logistics & Support",
        "description": "Movement of personnel, equipment, or supplies by road vehicle.",
        "aliases": ["Vehicle Transport", "Personnel Carrier", "Cargo Transport"],
    },
    {
        "name": "Air Transport",
        "category": "Logistics & Support",
        "description": "Movement of personnel, equipment, or supplies by rotary or fixed-wing aircraft.",
        "aliases": ["Airlift", "Helicopter Transport", "Fixed-Wing Transport"],
    },
    {
        "name": "Fuel and POL Services",
        "category": "Logistics & Support",
        "description": "Storage, transport, and dispensing of petroleum, oil, and lubricants for field operations.",
        "aliases": ["Fuel Supply", "POL", "Refueling"],
    },
    {
        "name": "Base Camp / Staging Support",
        "category": "Logistics & Support",
        "description": "Establishment and operation of base camps, staging areas, or spike camps.",
        "aliases": ["Base Camp", "Camp Services", "Staging Area"],
    },
    {
        "name": "Equipment Maintenance",
        "category": "Logistics & Support",
        "description": "Field maintenance, repair, and servicing of vehicles and equipment.",
        "aliases": ["Mechanic", "Field Maintenance", "Equipment Repair"],
    },
    {
        "name": "Supply Chain / Ordering",
        "category": "Logistics & Support",
        "description": "Procurement, ordering, tracking, and delivery of resources through supply chain channels.",
        "aliases": ["Procurement", "Supply Ordering", "Resource Ordering"],
    },
    {
        "name": "Feeding Operations",
        "category": "Logistics & Support",
        "description": "Preparation and distribution of meals for responders or affected populations.",
        "aliases": ["Food Unit", "Feeding", "Mobile Kitchen", "Catering"],
    },

    # ------------------------------------------------------------------ #
    # Command & Coordination
    # ------------------------------------------------------------------ #
    {
        "name": "Incident Command",
        "category": "Command & Coordination",
        "description": "Overall on-scene command authority and management under ICS.",
        "aliases": ["IC", "Incident Commander", "Unified Command"],
    },
    {
        "name": "Planning / Intelligence",
        "category": "Command & Coordination",
        "description": "Situational awareness collection, analysis, and incident action plan development.",
        "aliases": ["Situation Report", "SITL", "S-2", "Planning Section"],
    },
    {
        "name": "Operations Coordination",
        "category": "Command & Coordination",
        "description": "Coordination and direction of tactical operations under the Operations Section.",
        "aliases": ["Operations Section", "OPSC", "Tactical Coordination"],
    },
    {
        "name": "Finance and Administration",
        "category": "Command & Coordination",
        "description": "Cost tracking, time recording, procurement, and compensation/claims support.",
        "aliases": ["Finance Section", "FASC", "Cost Accounting"],
    },
    {
        "name": "Public Information",
        "category": "Command & Coordination",
        "description": "Media relations, public messaging, and Joint Information Center operations.",
        "aliases": ["PIO", "JIC", "Media Relations", "Public Affairs"],
    },
    {
        "name": "Safety Officer",
        "category": "Command & Coordination",
        "description": "Monitoring and assessment of hazardous and unsafe conditions in field operations.",
        "aliases": ["SOFR", "Safety"],
    },
    {
        "name": "EOC Operations",
        "category": "Command & Coordination",
        "description": "Emergency Operations Center management and coordination support.",
        "aliases": ["Emergency Operations Center", "EOC"],
    },

    # ------------------------------------------------------------------ #
    # Infrastructure & Utilities
    # ------------------------------------------------------------------ #
    {
        "name": "Emergency Power Generation",
        "category": "Infrastructure & Utilities",
        "description": "Temporary power supply using generators or mobile power units.",
        "aliases": ["Generator", "Temporary Power", "Mobile Generator"],
    },
    {
        "name": "Water Supply and Distribution",
        "category": "Infrastructure & Utilities",
        "description": "Potable water procurement, purification, storage, and distribution.",
        "aliases": ["Water Tanker", "Potable Water", "Water Purification"],
    },
    {
        "name": "Emergency Lighting",
        "category": "Infrastructure & Utilities",
        "description": "Portable or mobile lighting for night operations or power outage conditions.",
        "aliases": ["Light Tower", "Portable Lighting", "Scene Lighting"],
    },
    {
        "name": "Debris Removal and Clearance",
        "category": "Infrastructure & Utilities",
        "description": "Removal of debris from roads, structures, and public spaces to restore access.",
        "aliases": ["Debris Clearance", "Road Clearance", "Emergency Debris"],
    },
    {
        "name": "Damage Assessment",
        "category": "Infrastructure & Utilities",
        "description": "Evaluation and documentation of structural and infrastructure damage after a disaster.",
        "aliases": ["PDA", "Preliminary Damage Assessment", "Building Inspection"],
    },
    {
        "name": "Hazard Mitigation",
        "category": "Infrastructure & Utilities",
        "description": "Actions taken to reduce or eliminate long-term risk to life and property from hazards.",
        "aliases": ["Mitigation", "Risk Reduction"],
    },

    # ------------------------------------------------------------------ #
    # Mass Care
    # ------------------------------------------------------------------ #
    {
        "name": "Emergency Shelter Operations",
        "category": "Mass Care",
        "description": "Establishment and management of congregate or non-congregate shelters for displaced persons.",
        "aliases": ["Shelter", "Mass Shelter", "Emergency Shelter"],
    },
    {
        "name": "Evacuation Support",
        "category": "Mass Care",
        "description": "Coordination of evacuation routes, transportation, and assembly points for affected populations.",
        "aliases": ["Evacuation", "Evacuation Transportation"],
    },
    {
        "name": "Reunification Services",
        "category": "Mass Care",
        "description": "Systems and operations to reunite separated individuals and families after a disaster.",
        "aliases": ["Family Reunification", "Missing Persons"],
    },
    {
        "name": "Donations and Volunteer Management",
        "category": "Mass Care",
        "description": "Coordination of unsolicited donations, spontaneous volunteers, and NGO support.",
        "aliases": ["Volunteer Management", "Donations Management", "VOADs"],
    },
    {
        "name": "Access and Functional Needs Support",
        "category": "Mass Care",
        "description": "Services for individuals with disabilities, medical needs, or other access and functional needs.",
        "aliases": ["AFN", "Special Needs", "CMIST"],
    },

    # ------------------------------------------------------------------ #
    # Animal Services
    # ------------------------------------------------------------------ #
    {
        "name": "Large Animal Rescue",
        "category": "Animal Services",
        "description": "Rescue operations for horses, cattle, and other large animals in emergency situations.",
        "aliases": ["Livestock Rescue", "Equine Rescue"],
    },
    {
        "name": "Small Animal Sheltering",
        "category": "Animal Services",
        "description": "Emergency sheltering and care for household pets and small animals.",
        "aliases": ["Pet Shelter", "Animal Shelter"],
    },
    {
        "name": "Veterinary Care",
        "category": "Animal Services",
        "description": "Emergency veterinary triage, treatment, and care for animals during disaster response.",
        "aliases": ["Emergency Vet", "Animal Medical"],
    },
]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

def seed(db_path: Path | None = None, dry_run: bool = False) -> None:
    repo = ResourceTypeRepository(db_path)

    existing = {row["name"].lower() for row in repo.list_capabilities(include_inactive=True)}
    print(f"Existing capabilities in DB: {len(existing)}")

    skipped = 0
    inserted = 0
    failed = 0

    for entry in CAPABILITIES:
        name = entry["name"]
        if name.lower() in existing:
            skipped += 1
            continue

        cap = ResourceCapability(
            name=name,
            category=entry.get("category", ""),
            description=entry.get("description", ""),
            aliases=entry.get("aliases", []),
            is_active=True,
        )

        if dry_run:
            print(f"  DRY-RUN  [{cap.category:28s}]  {cap.name}")
            inserted += 1
            continue

        try:
            repo.save_capability(cap)
            inserted += 1
            existing.add(name.lower())
        except Exception as exc:
            print(f"  FAILED   {name}: {exc}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Inserted:         {inserted}")
    print(f"Skipped (exists): {skipped}")
    print(f"Failed:           {failed}")
    if dry_run:
        print("\n(dry-run — no changes written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed standard EM capabilities into master.db")
    parser.add_argument("--db", metavar="PATH", help="Path to SQLite DB (default: data/master.db)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be inserted without writing anything")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None

    print("Emergency Management Capability Seeder")
    print("=" * 60)
    seed(db_path=db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
