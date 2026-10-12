"""Helpers for locating PDF form mappings."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def find_mapping_for_pdf(pdf_path: str, mappings_dir: str = "modules/forms/mappings") -> str | None:
    """Return the first mapping configuration that matches ``pdf_path``."""
    pdf = Path(pdf_path)
    candidates = [
        pdf.with_suffix(".mapping.json"),
        Path(mappings_dir) / f"{pdf.stem}.json",
        Path(mappings_dir) / f"{pdf.stem}.mapping.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def list_available_forms(mappings_dir: str = "modules/forms/mappings") -> list[dict[str, Any]]:
    """Return all forms that have a discoverable mapping configuration."""
    base = Path(mappings_dir)
    if not base.exists():
        return []

    forms: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()

    for mapping_path in sorted(base.glob("*.json")):
        stem = mapping_path.name
        if stem.endswith(".mapping.json"):
            pdf_stem = stem[: -len(".mapping.json")]
        else:
            pdf_stem = mapping_path.stem
        pdf_candidate = base / f"{pdf_stem}.pdf"
        entry = {
            "name": pdf_stem.replace("_", " ").upper(),
            "pdf_path": str(pdf_candidate) if pdf_candidate.exists() else None,
            "mapping_path": str(mapping_path),
        }
        key = (entry["name"], entry["mapping_path"])
        if key in seen:
            continue
        seen.add(key)
        forms.append(entry)

    return forms
