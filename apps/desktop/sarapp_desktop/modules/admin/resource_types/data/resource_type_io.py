"""CSV bulk import/export for the Resource Type Library.

Capabilities and resource types can each be round-tripped through a flat CSV
file that is easy to edit in a spreadsheet.  List fields (aliases, capability
names) use semicolons as separators inside a single cell, matching the
convention already used by the capability aliases column in the database.

Components and FEMA/NIMS mappings are intentionally omitted from the CSV
format — they are too relational for a flat table.  Use the editor dialog to
manage those fields on individual records.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..models.resource_type_models import (
    RESOURCE_CATEGORIES,
    RESOURCE_SOURCES,
    ResourceCapability,
    ResourceType,
)
from .resource_type_repository import ApiResourceTypeRepository

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

CAPABILITY_CSV_FIELDS = [
    "name",
    "category",
    "description",
    "aliases",
    "is_active",
    "notes",
]

RESOURCE_TYPE_CSV_FIELDS = [
    "name",
    "resource_name",
    "category",
    "source",
    "owner_agency",
    "description",
    "default_unit",
    "typical_quantity",
    "typical_team_size",
    "is_kit_cache",
    "is_consumable",
    "is_active",
    "notes",
    "aliases",
    "capabilities",
]

# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def export_capabilities_csv(
    repository: ApiResourceTypeRepository, file_path: str | Path
) -> int:
    """Write all capabilities (including inactive) to *file_path*.

    Returns the number of rows written.
    """
    rows = repository.list_capabilities(include_inactive=True)
    with open(file_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CAPABILITY_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "name": row.get("name", ""),
                    "category": row.get("category", ""),
                    "description": row.get("description", ""),
                    "aliases": row.get("aliases", ""),
                    "is_active": "1" if row.get("is_active") else "0",
                    "notes": row.get("notes", ""),
                }
            )
    return len(rows)


def import_capabilities_csv(
    repository: ApiResourceTypeRepository, file_path: str | Path
) -> dict[str, Any]:
    """Read capabilities from *file_path* and upsert them into the database.

    Matching is case-insensitive on ``name``.  Existing records are updated;
    new names are inserted.  Returns a result dict::

        {"inserted": int, "updated": int, "errors": list[str]}
    """
    inserted = updated = 0
    errors: list[str] = []

    with open(file_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for line_num, row in enumerate(reader, start=2):
            name = row.get("name", "").strip()
            if not name:
                errors.append(f"Row {line_num}: name is required — skipped.")
                continue
            try:
                existing = repository.get_capability_by_name(name)
                aliases = [a.strip() for a in row.get("aliases", "").split(";") if a.strip()]
                is_active = _parse_bool(row.get("is_active", "1"), default=True)
                cap = ResourceCapability(
                    id=int(existing["id"]) if existing else None,
                    name=name,
                    category=row.get("category", "").strip(),
                    description=row.get("description", "").strip(),
                    aliases=aliases,
                    is_active=is_active,
                    notes=row.get("notes", "").strip(),
                )
                repository.save_capability(cap)
                if existing:
                    updated += 1
                else:
                    inserted += 1
            except Exception as exc:
                errors.append(f"Row {line_num} ({name!r}): {exc}")

    return {"inserted": inserted, "updated": updated, "errors": errors}


# ---------------------------------------------------------------------------
# Resource types
# ---------------------------------------------------------------------------


def export_resource_types_csv(
    repository: ApiResourceTypeRepository, file_path: str | Path
) -> int:
    """Write all resource types (including inactive) to *file_path*.

    Aliases are written as a semicolon-separated string.  Capabilities are
    written as a semicolon-separated string of capability names.  Components
    and FEMA/NIMS mappings are not included in the CSV export.

    Returns the number of rows written.
    """
    rows = repository.list_resource_types(active_filter="All")
    with open(file_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESOURCE_TYPE_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            rt = repository.get_resource_type(int(row["id"]))
            aliases_str = "; ".join(rt.aliases) if rt else ""
            capabilities_str = row.get("capabilities", "") or ""
            writer.writerow(
                {
                    "name": row.get("name", ""),
                    "resource_name": row.get("resource_name") or row.get("name", ""),
                    "category": row.get("category", ""),
                    "source": row.get("source", ""),
                    "owner_agency": row.get("owner_agency", ""),
                    "description": row.get("description", ""),
                    "default_unit": row.get("default_unit", ""),
                    "typical_quantity": row.get("typical_quantity", ""),
                    "typical_team_size": row.get("typical_team_size") or "",
                    "is_kit_cache": "1" if row.get("is_kit_cache") else "0",
                    "is_consumable": "1" if row.get("is_consumable") else "0",
                    "is_active": "1" if row.get("is_active") else "0",
                    "notes": row.get("notes", ""),
                    "aliases": aliases_str,
                    "capabilities": capabilities_str,
                }
            )
    return len(rows)


def import_resource_types_csv(
    repository: ApiResourceTypeRepository, file_path: str | Path
) -> dict[str, Any]:
    """Read resource types from *file_path* and upsert them into the database.

    Matching is case-insensitive on ``name``.  Existing records are updated;
    new names are inserted.  Capability names in the ``capabilities`` column
    are resolved to IDs; unrecognised names are skipped and logged as warnings.
    Components and FEMA/NIMS mappings are not affected.

    Returns::

        {"inserted": int, "updated": int, "errors": list[str]}
    """
    inserted = updated = 0
    errors: list[str] = []

    with open(file_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for line_num, row in enumerate(reader, start=2):
            name = row.get("name", "").strip()
            if not name:
                errors.append(f"Row {line_num}: name is required — skipped.")
                continue
            try:
                category = row.get("category", "Other").strip() or "Other"
                if category not in RESOURCE_CATEGORIES:
                    errors.append(
                        f"Row {line_num} ({name!r}): unknown category {category!r} — defaulting to 'Other'."
                    )
                    category = "Other"

                source = row.get("source", "AHJ Custom").strip() or "AHJ Custom"
                if source not in RESOURCE_SOURCES:
                    errors.append(
                        f"Row {line_num} ({name!r}): unknown source {source!r} — defaulting to 'AHJ Custom'."
                    )
                    source = "AHJ Custom"

                aliases = [a.strip() for a in row.get("aliases", "").split(";") if a.strip()]

                capability_ids: list[int] = []
                cap_str = row.get("capabilities", "").strip()
                if cap_str:
                    for cap_name in [c.strip() for c in cap_str.split(";") if c.strip()]:
                        cap = repository.get_capability_by_name(cap_name)
                        if cap:
                            capability_ids.append(int(cap["id"]))
                        else:
                            errors.append(
                                f"Row {line_num} ({name!r}): capability {cap_name!r} not found — skipped."
                            )

                try:
                    typical_quantity = float(row.get("typical_quantity", "1") or "1")
                except ValueError:
                    typical_quantity = 1.0

                team_size_raw = (row.get("typical_team_size") or "").strip()
                try:
                    typical_team_size: int | None = int(team_size_raw) if team_size_raw else None
                except ValueError:
                    typical_team_size = None

                existing = repository.get_resource_type_by_name(name)
                rt = ResourceType(
                    id=existing.id if existing else None,
                    name=name,
                    resource_name=row.get("resource_name", "").strip(),
                    category=category,
                    source=source,
                    owner_agency=row.get("owner_agency", "").strip(),
                    description=row.get("description", "").strip(),
                    default_unit=row.get("default_unit", "each").strip() or "each",
                    typical_quantity=typical_quantity,
                    typical_team_size=typical_team_size,
                    is_kit_cache=_parse_bool(row.get("is_kit_cache", "0"), default=False),
                    is_consumable=_parse_bool(row.get("is_consumable", "0"), default=False),
                    is_active=_parse_bool(row.get("is_active", "1"), default=True),
                    notes=row.get("notes", "").strip(),
                    aliases=aliases,
                    capability_ids=capability_ids,
                    fema_mappings=existing.fema_mappings if existing else [],
                )
                repository.save_resource_type(rt)
                if existing:
                    updated += 1
                else:
                    inserted += 1
            except Exception as exc:
                errors.append(f"Row {line_num} ({name!r}): {exc}")

    return {"inserted": inserted, "updated": updated, "errors": errors}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_bool(value: str, *, default: bool) -> bool:
    """Interpret common truthy/falsy strings from spreadsheet exports."""
    v = value.strip().lower()
    if v in ("1", "true", "yes", "y"):
        return True
    if v in ("0", "false", "no", "n"):
        return False
    return default
