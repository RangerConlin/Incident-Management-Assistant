"""Registry for form sets and the master form catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_FORMS_ROOT = Path(__file__).resolve().parents[2] / "forms"


@dataclass
class FormSetMeta:
    id: str
    display_name: str
    version: str
    fallback: str | None
    path: Path


@dataclass
class FormCatalogEntry:
    id: str
    number: str
    title: str
    category: str
    row_groups: list[dict] = field(default_factory=list)


@dataclass
class FormCoverage:
    """Coverage of a single form across all known form sets."""
    form_id: str
    implementations: dict[str, dict[str, Any]] = field(default_factory=dict)
    # implementations[set_id] = {"version": ..., "has_pdf": bool, "has_mapping": bool,
    #                             "unmapped_count": int, "fallback_set": str|None}


class FormSetRegistry:
    """Scans forms/sets/ and provides form set and catalog queries."""

    def __init__(self, forms_root: Path | str | None = None) -> None:
        self._root = Path(forms_root) if forms_root else _FORMS_ROOT
        self._sets: dict[str, FormSetMeta] = {}
        self._catalog: list[FormCatalogEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_sets(self) -> list[FormSetMeta]:
        return list(self._sets.values())

    def get_set(self, set_id: str) -> FormSetMeta | None:
        return self._sets.get(set_id)

    def list_catalog(self) -> list[FormCatalogEntry]:
        return list(self._catalog)

    def get_form_definition(self, form_id: str) -> FormCatalogEntry | None:
        for entry in self._catalog:
            if entry.id == form_id:
                return entry
        return None

    def update_form_definition(self, form_id: str, number: str, title: str, category: str) -> bool:
        """Update an existing form's metadata in catalog.json. Returns True if found."""
        for entry in self._catalog:
            if entry.id == form_id:
                entry.number = number
                entry.title = title
                entry.category = category
                self._save_catalog()
                return True
        return False

    def remove_form_definition(self, form_id: str) -> bool:
        """Remove a form from catalog.json. Returns True if removed."""
        before = len(self._catalog)
        self._catalog = [e for e in self._catalog if e.id != form_id]
        if len(self._catalog) < before:
            self._save_catalog()
            return True
        return False

    def update_set(self, set_id: str, display_name: str, version: str, fallback: str | None) -> bool:
        """Update a form set's manifest.json. Returns True if found."""
        meta = self._sets.get(set_id)
        if not meta:
            return False
        manifest = {
            "id": set_id,
            "display_name": display_name,
            "version": version,
            "fallback": fallback,
        }
        (meta.path / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        meta.display_name = display_name
        meta.version = version
        meta.fallback = fallback
        return True

    def remove_set(self, set_id: str) -> bool:
        """Delete a form set directory and its manifest. Returns True if removed."""
        import shutil
        meta = self._sets.pop(set_id, None)
        if not meta:
            return False
        shutil.rmtree(meta.path, ignore_errors=True)
        return True

    def remove_version(self, form_id: str, set_id: str) -> bool:
        """Delete template.pdf and mapping.json for a form within a set."""
        meta = self._sets.get(set_id)
        if not meta:
            return False
        form_dir = meta.path / form_id
        if not form_dir.exists():
            return False
        import shutil
        shutil.rmtree(form_dir, ignore_errors=True)
        return True

    def add_form_definition(self, form_id: str, number: str, title: str, category: str,
                            row_groups: list[dict] | None = None) -> FormCatalogEntry:
        """Add a new form to catalog.json and return the entry."""
        entry = FormCatalogEntry(id=form_id, number=number, title=title, category=category,
                                 row_groups=row_groups or [])
        self._catalog.append(entry)
        self._save_catalog()
        return entry

    def update_form_row_groups(self, form_id: str, row_groups: list[dict]) -> bool:
        """Replace the row_groups list for a form and save catalog.json."""
        for entry in self._catalog:
            if entry.id == form_id:
                entry.row_groups = row_groups
                self._save_catalog()
                return True
        return False

    def coverage(self, form_id: str) -> FormCoverage:
        """Return implementation status for a form across all known sets."""
        cov = FormCoverage(form_id=form_id)
        for set_meta in self._sets.values():
            form_dir = set_meta.path / form_id
            has_pdf = (form_dir / "template.pdf").exists()
            has_mapping = (form_dir / "mapping.json").exists()
            unmapped = 0
            if has_mapping:
                unmapped = self._count_unmapped(form_dir / "mapping.json")
            if has_pdf or has_mapping:
                cov.implementations[set_meta.id] = {
                    "version": set_meta.version,
                    "has_pdf": has_pdf,
                    "has_mapping": has_mapping,
                    "unmapped_count": unmapped,
                    "fallback_set": None,
                }
            else:
                # Find which set this falls back to
                fb = self._resolve_fallback(set_meta, form_id)
                cov.implementations[set_meta.id] = {
                    "version": None,
                    "has_pdf": False,
                    "has_mapping": False,
                    "unmapped_count": 0,
                    "fallback_set": fb,
                }
        return cov

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._load_sets()
        self._load_catalog()

    def _load_sets(self) -> None:
        sets_dir = self._root / "sets"
        if not sets_dir.exists():
            return
        for manifest_path in sorted(sets_dir.glob("*/manifest.json")):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                meta = FormSetMeta(
                    id=data["id"],
                    display_name=data.get("display_name", data["id"]),
                    version=data.get("version", ""),
                    fallback=data.get("fallback"),
                    path=manifest_path.parent,
                )
                self._sets[meta.id] = meta
            except Exception:
                pass

    def _load_catalog(self) -> None:
        catalog_path = self._root / "catalog.json"
        if not catalog_path.exists():
            return
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            for item in data.get("forms", []):
                self._catalog.append(FormCatalogEntry(
                    id=item["id"],
                    number=item.get("number", item["id"]),
                    title=item.get("title", ""),
                    category=item.get("category", ""),
                    row_groups=item.get("row_groups", []),
                ))
        except Exception:
            pass

    def _save_catalog(self) -> None:
        catalog_path = self._root / "catalog.json"
        rows = []
        for e in self._catalog:
            entry: dict = {"id": e.id, "number": e.number, "title": e.title, "category": e.category}
            if e.row_groups:
                entry["row_groups"] = e.row_groups
            rows.append(entry)
        data = {"forms": rows}
        catalog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _resolve_fallback(self, set_meta: FormSetMeta, form_id: str) -> str | None:
        """Walk the fallback chain and return the first set_id that has the form."""
        visited: set[str] = {set_meta.id}
        current_id = set_meta.fallback
        while current_id:
            if current_id in visited:
                break
            visited.add(current_id)
            fb_meta = self._sets.get(current_id)
            if fb_meta is None:
                break
            form_dir = fb_meta.path / form_id
            if (form_dir / "template.pdf").exists() or (form_dir / "mapping.json").exists():
                return current_id
            current_id = fb_meta.fallback
        return None

    @staticmethod
    def _count_unmapped(mapping_path: Path) -> int:
        import re
        try:
            data = json.loads(mapping_path.read_text(encoding="utf-8"))

            # Build set of regex patterns for fields covered by array col_patterns
            rg_patterns: list[re.Pattern] = []
            for rg in data.get("row_groups", []):
                for pattern in rg.get("col_patterns", {}).values():
                    if pattern:
                        regex = re.escape(pattern).replace(r"\{n\}", r"\d+") + "$"
                        rg_patterns.append(re.compile(regex, re.IGNORECASE))

            count = 0
            for field_entry in data.get("fields", []):
                source = field_entry.get("source")
                if source is None or source == "" or source == {"literal": ""}:
                    name = field_entry.get("pdf_field") or field_entry.get("name") or ""
                    if not any(p.match(name) for p in rg_patterns):
                        count += 1
            return count
        except Exception:
            return 0
