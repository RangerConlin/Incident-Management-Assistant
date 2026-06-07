#!/usr/bin/env python3
"""
Seed Florida FFCA-SERP resource types from the Typed Resource Guidance Document PDF.

Reads data/florida_pdfs/fl_typed_resource_guidance.pdf and
data/florida_pdfs/fasar_usar_typing.pdf, parses resource type definitions,
and inserts new ResourceType records into master.db.

Idempotent: records whose name already exists are skipped.
Records that are essentially duplicate names of FEMA RTLT types already in the
DB are also skipped (handled by the name-collision check).

Usage:
    python scripts/seed_florida_resource_types.py
    python scripts/seed_florida_resource_types.py --db path/to/custom.db
    python scripts/seed_florida_resource_types.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pypdf

from modules.admin.resource_types.data.resource_type_repository import ResourceTypeRepository
from modules.admin.resource_types.models.resource_type_models import (
    FemaNimsMapping,
    ResourceType,
)

FL_PDF   = PROJECT_ROOT / "data" / "florida_pdfs" / "fl_typed_resource_guidance.pdf"
USAR_PDF = PROJECT_ROOT / "data" / "florida_pdfs" / "fasar_usar_typing.pdf"

SOURCE      = "AHJ Custom"
OWNER       = "Florida / FFCA-SERP"
CREATED_BY  = "fl_seed"
REFERENCE   = "https://www.ffca.org/assets/docs/SERP/FL-Typed%20Resource%20Guidence%20Document.pdf"
USAR_REF    = "https://www.ffca.org/assets/docs/FASAR%20Urban%20Search%20and%20Rescue%20Resource%20Typing%20document%202016.pdf"

# ---------------------------------------------------------------------------
# Pages to skip entirely (blank template / boilerplate pages)
# ---------------------------------------------------------------------------
_SKIP_PAGES = {138, 139, 140}          # Blank form templates

# ---------------------------------------------------------------------------
# Names to skip (near-exact duplicates of FEMA RTLT types already imported,
# or internal stubs that add no value as a resource type)
# ---------------------------------------------------------------------------
_SKIP_NAMES = {
    # Already in DB (exact or near-identical FEMA types)
    "ambulance task force",
    "fire boat",
    "fuel tender",
    "public safety dive team",
    "air search team (fixed-wing)",
    # Florida PDF has these but FEMA RTLT versions already loaded
    "hazmat response team",              # → "Hazardous Materials Response Team"
    "critical incident stress management team (cism)",  # → "Critical Incident Stress Management (CISM) Team"
    "cave search & rescue team",         # → "Cave Search and Rescue (SAR) Team"
    "swiftwater/flood s&r team",         # → "Swiftwater/Flood Search and Rescue Team"
    "mine and tunnel s&r team",          # → "Mine Search and Rescue (SAR) Team"
    "urban search & rescue task force",  # → "Urban Search and Rescue Task Force"
    "urban search & rescue incident support team",  # → "Urban Search and Rescue Incident Support Team"
    "collapse s&r team",                 # → "Structural Collapse Rescue Team"
    "airborne reconnaissance (fixed-wing)",  # → "Airborne Reconnaissance (Fixed Wing)"
    # Blank / internal forms
    "blank forms",
    "blank form w/ 4 type columns",
    "blank form w/ 7 type columns",
}

# ---------------------------------------------------------------------------
# Section header → FL discipline string
# ---------------------------------------------------------------------------
_SECTION_MAP = {
    "COMMAND / OVERHEAD":      "Command / Overhead",
    "EMS RESOURCE":            "Emergency Medical Services",
    "FIREFIGHTING RESOURCE":   "Fire / Hazardous Materials",
    "LAW ENFORCEMENT RESOURCE":"Law Enforcement",
    "PUBLIC INFORMATION RESOURCE": "Public Information",
    "SEARCH & RESCUE RESOURCE":"Search & Rescue",
}

# ---------------------------------------------------------------------------
# FL discipline / kind → our RESOURCE_CATEGORIES
# ---------------------------------------------------------------------------
def _map_category(discipline: str, kind: str, name: str) -> str:
    k = kind.lower().strip()
    d = discipline.lower()
    n = name.lower()
    words = set(re.split(r"[\s/(),\-]+", n))

    if "supply" in k or "product" in k or "foam bulk" in n:
        return "Supply"
    if k == "aircraft" or "helicopter" in n or "fixed-wing" in n or "rotary-wing" in n \
            or "air ambulance" in n:
        return "Aircraft"
    if k == "personnel" or "chief" in n or "officer" in n or "technician" in n \
            or "telecommunicator" in n or "specialist" in n or "investigator" in n \
            or "liaison" in n or "leader" in words:
        return "Personnel"
    # Team-like names regardless of kind field
    if any(t in n for t in ("strike team", "task force", "taskforce", " team", "tert")):
        return "Team"
    if k in ("team", "task force", "taskforce", "crew"):
        return "Team"
    if k == "facility":
        return "Facility"
    if k in ("vehicle", "equipment") or any(w in n for w in (
        "truck", "tender", "pump", "apparatus", "atv", "bus", "mechanic",
        "vehicle", "trailer",
    )):
        # Exact word "kit" or "cache" only (avoid "kitchen" false positive)
        if "kit" in words or "cache" in words:
            return "Equipment Kit / Cache"
        return "Equipment"
    # Rescue / unit nouns that are Equipment
    if any(w in n for w in ("unit", "rescue", "ambulance", "pump")):
        return "Equipment"
    # Fallbacks by discipline
    if "fire" in d or "hazmat" in d:
        return "Equipment"
    if "search" in d or "rescue" in d:
        return "Team"
    if "medical" in d or "ems" in d:
        return "Team"
    return "Team"


# ---------------------------------------------------------------------------
# Type level normalisation
# ---------------------------------------------------------------------------
_ROMAN = {"I": "Type I", "II": "Type II", "III": "Type III", "IV": "Type IV",
          "1": "Type I", "2": "Type II", "3": "Type III", "4": "Type IV"}


def _extract_type_levels(text: str) -> list[str]:
    raw = re.findall(r"\bType\s+([1-4]|I{1,3}V?|IV)\b", text, re.IGNORECASE)
    seen: dict[str, bool] = {}
    for r in raw:
        key = _ROMAN.get(r.upper(), f"Type {r}")
        seen[key] = True
    order = ["Type I", "Type II", "Type III", "Type IV"]
    return [t for t in order if t in seen]


# ---------------------------------------------------------------------------
# Title-case helper that preserves all-caps abbreviations
# ---------------------------------------------------------------------------
_ABBREVS = {"ATV", "EMS", "ALS", "BLS", "CISM", "EOC", "SEOC", "SERP",
            "TERT", "PIO", "AFFF", "AR-AFFF", "US&R", "TRT", "IMT",
            "ESF", "ARFF", "NQS", "USAR"}


def _title(s: str) -> str:
    """Convert an ALL-CAPS PDF string to Title Case, preserving abbreviations."""

    def _convert_word(w: str) -> str:
        # Strip surrounding punctuation for lookup, preserve it
        prefix = ""
        suffix = ""
        core = w
        while core and core[0] in "(/":
            prefix += core[0]; core = core[1:]
        while core and core[-1] in ")/.,":
            suffix = core[-1] + suffix; core = core[:-1]

        if not core:
            return w

        upper_core = core.upper()
        # Known abbreviations — keep as-is
        if upper_core in _ABBREVS:
            return prefix + upper_core + suffix

        # Hyphenated or slash-separated words: convert each part
        if "-" in core:
            parts = core.split("-")
            converted = "-".join(_convert_word(p) for p in parts)
            return prefix + converted + suffix
        if "/" in core:
            parts = core.split("/")
            converted = "/".join(_convert_word(p) for p in parts)
            return prefix + converted + suffix

        # All-caps word → Title Case
        if core.isupper() and len(core) > 1:
            return prefix + core.capitalize() + suffix

        return prefix + core + suffix

    return " ".join(_convert_word(w) for w in s.strip().split())


# ---------------------------------------------------------------------------
# PDF parser — extracts one dict per resource type page
# ---------------------------------------------------------------------------

def _clean_repeated(s: str) -> str:
    """Remove PDF-artifact name repetitions like 'FOO BAR FOO BAR FOO BAR'."""
    words = s.split()
    for n in range(1, len(words) // 2 + 1):
        chunk = words[:n]
        reps = len(words) // n
        if reps >= 2 and words == chunk * reps:
            return " ".join(chunk)
    return s


def _parse_fl_pdf() -> list[dict]:
    reader = pypdf.PdfReader(str(FL_PDF))
    records: list[dict] = []
    current_section = "Command / Overhead"

    for page_num, page in enumerate(reader.pages, 1):
        raw = page.extract_text() or ""
        text = raw.replace("\xa0", " ")

        # Update section tracker
        text_up = text.upper()
        for key, val in _SECTION_MAP.items():
            if key in text_up:
                current_section = val
                break

        # Skip pages without a resource table
        if "CATEGORY:" not in text and "Category:" not in text:
            continue
        if "KIND:" not in text and "Kind:" not in text:
            continue

        # Skip blank-form pages
        if page_num in _SKIP_PAGES:
            continue

        # Skip obvious placeholder pages (EXAMPLE with no real content)
        non_ws_lines = [l for l in text.splitlines() if l.strip()]
        example_idx = next((i for i, l in enumerate(non_ws_lines) if "EXAMPLE" in l.upper()), -1)
        if example_idx != -1:
            # Count content lines above the EXAMPLE marker
            content_before = [l for l in non_ws_lines[:example_idx]
                              if not any(k in l.upper() for k in
                                        ("CATEGORY", "KIND", "MINIMUM", "COMPONENT",
                                         "METRIC", "TYPE I", "TYPE II", "FFCA", "PAGE"))]
            if len(content_before) < 3:
                continue

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Extract name — first line that isn't a section header, label, or page footer
        name_raw = ""
        for line in lines[:8]:
            if any(k in line.upper() for k in
                   ("RESOURCE DEFINITIONS", "FFCA", "COMPANION DOCUMENT",
                    "PAGE", "CATEGORY:", "KIND:", "MINIMUM", "COMPONENT")):
                continue
            # Remove trailing TIER-I / Tier-I
            line_clean = re.sub(r'\s+Tier[- ](I|II|1|2)\s*$', '', line, flags=re.IGNORECASE).strip()
            # Resource: NAME pattern
            rm = re.match(r'Resource[:\s]+(.+)', line_clean, re.IGNORECASE)
            if rm:
                name_raw = rm.group(1).strip()
                break
            if len(line_clean) > 4 and line_clean == line_clean.upper():
                name_raw = line_clean
                break

        name_raw = _clean_repeated(name_raw)
        name_raw = re.sub(r'\s+Tier[- ](I|II|1|2)\s*$', '', name_raw, flags=re.IGNORECASE).strip()
        name = _title(name_raw)

        if not name or name.lower() in _SKIP_NAMES:
            continue

        # Kind & category
        kind = ""
        discipline = current_section
        for line in lines:
            km = re.search(r'(?:KIND|Kind)[:\s]+([A-Za-z ]+?)(?:\s{2,}|MINIMUM|$)', line)
            if km and not kind:
                raw_kind = km.group(1).strip()
                # Remove repeated artifact
                kind = _clean_repeated(raw_kind)
                if len(kind) > 20:
                    kind = kind[:20].strip()
            cm = re.search(r'(?:CATEGORY|Category)[:\s]+([A-Za-z /&()\-0-9]+?)(?:\s{2,}|KIND|$)', line)
            if cm:
                cat_val = cm.group(1).strip()
                if cat_val and len(cat_val) < 60:
                    discipline = cat_val

        # Tier
        tier_m = re.search(r'Tier[- ](I|II|1|2)\b', text, re.IGNORECASE)
        tier = ("Tier-I" if tier_m and tier_m.group(1).upper() in ("I", "1")
                else "Tier-II" if tier_m else "")

        # Type levels
        type_levels = _extract_type_levels(text)

        # Description: look for DESCRIPTION label or first multi-word sentence
        desc = ""
        desc_m = re.search(
            r'DESCRIPTION\s+(.{30,400}?)(?=MINIMUM CAPABILITIES|COMPONENT|TYPE I|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
        if desc_m:
            desc = re.sub(r'\s+', ' ', desc_m.group(1)).strip()[:400]

        category = _map_category(discipline, kind, name)

        records.append({
            "name": name,
            "discipline": discipline,
            "kind": kind,
            "tier": tier,
            "type_levels": type_levels,
            "category": category,
            "description": desc,
            "page": page_num,
        })

    return records


def _parse_usar_pdf() -> list[dict]:
    """Extract Florida US&R Task Force types (Type 1-4) from FASAR USAR PDF."""
    reader = pypdf.PdfReader(str(USAR_PDF))
    all_text = " ".join(
        (page.extract_text() or "").replace("\xa0", " ")
        for page in reader.pages
    )
    # Only one resource type: US&R Task Force, Types 1-4
    if "Urban Search and Rescue" not in all_text and "US&R Task Force" not in all_text:
        return []
    return [{
        "name": "Urban Search & Rescue Task Force (Florida)",
        "discipline": "Search & Rescue",
        "kind": "Task Force",
        "tier": "Tier-I",
        "type_levels": ["Type I", "Type II", "Type III", "Type IV"],
        "category": "Team",
        "description": (
            "Multi-disciplined task force conducting search, rescue, and recovery "
            "across technical rescue disciplines: structural collapse, rope rescue, "
            "vehicle extrication, confined space, trench, and water operations. "
            "Types I-II operate two 12-hour shifts; Types III-IV operate one 12-hour shift. "
            "All types self-sustaining for 72 hours and deployable up to 14 days. "
            "(Florida / FASAR Tier-I definition)"
        ),
        "page": 0,
    }]


# ---------------------------------------------------------------------------
# Build ResourceType from parsed record
# ---------------------------------------------------------------------------

def _build_resource_type(rec: dict) -> ResourceType:
    type_levels = rec.get("type_levels", [])
    name = rec["name"]

    mappings: list[FemaNimsMapping] = []
    if type_levels:
        for level in type_levels:
            mappings.append(FemaNimsMapping(
                resource_type_id=0,
                nims_name=name,
                discipline=rec["discipline"],
                type_code=rec.get("tier", ""),
                kind=rec["kind"],
                reference_url=USAR_REF if rec.get("page") == 0 else REFERENCE,
                typed_level=level,
            ))
    else:
        mappings.append(FemaNimsMapping(
            resource_type_id=0,
            nims_name=name,
            discipline=rec["discipline"],
            type_code=rec.get("tier", ""),
            kind=rec["kind"],
            reference_url=USAR_REF if rec.get("page") == 0 else REFERENCE,
            typed_level="",
        ))

    return ResourceType(
        name=name,
        planning_display_name=name,
        category=rec["category"],
        source=SOURCE,
        owner_agency=OWNER,
        description=rec.get("description", ""),
        is_active=True,
        fema_mappings=mappings,
        created_by=CREATED_BY,
        updated_by=CREATED_BY,
    )


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------

def seed(db_path: Path | None = None, dry_run: bool = False) -> None:
    for pdf_path in (FL_PDF, USAR_PDF):
        if not pdf_path.exists():
            print(f"ERROR: PDF not found: {pdf_path}")
            print("Run: python scripts/seed_florida_resource_types.py --fetch  (or download manually)")
            sys.exit(1)

    print("Parsing PDFs ...", flush=True)
    records = _parse_fl_pdf() + _parse_usar_pdf()
    print(f"  Parsed {len(records)} candidate resource types")

    repo = ResourceTypeRepository(db_path)
    existing = {row["name"].lower() for row in repo.list_resource_types(active_filter="All")}
    print(f"  Existing records in DB: {len(existing)}")
    print()

    inserted = skipped_dup = skipped_name = failed = 0

    for rec in records:
        name = rec["name"]

        if name.lower() in _SKIP_NAMES:
            skipped_name += 1
            continue
        if name.lower() in existing:
            skipped_dup += 1
            continue

        rt = _build_resource_type(rec)

        if dry_run:
            levels = ", ".join(rec.get("type_levels") or ["(untyped)"])
            print(f"  DRY-RUN  [{rt.category:24s}]  {rt.name}  [{levels}]")
            inserted += 1
            continue

        try:
            repo.save_resource_type(rt)
            inserted += 1
            existing.add(name.lower())
        except Exception as exc:
            print(f"  FAILED   {name}: {exc}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Inserted:              {inserted}")
    print(f"Skipped (name match):  {skipped_dup}")
    print(f"Skipped (exclusion):   {skipped_name}")
    print(f"Failed:                {failed}")
    if dry_run:
        print("\n(dry-run -- no changes written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Florida FFCA-SERP resource types")
    parser.add_argument("--db", metavar="PATH", help="Path to SQLite DB (default: data/master.db)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be inserted without writing")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None

    print("Florida FFCA-SERP Resource Type Seeder")
    print("=" * 60)
    seed(db_path=db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
