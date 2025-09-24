from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional
import json


CATALOG_PATH = Path("data/forms/catalog.json")


@dataclass
class TemplateEntry:
    version: str
    pdf: str  # relative path
    mapping: Optional[str] = None  # relative path (YAML)
    schema: Optional[str] = None   # relative path (JSON schema)
    profiles: List[str] = field(default_factory=list)


@dataclass
class FormEntry:
    id: str
    title: str
    category: str  # e.g., "ICS"
    profiles: List[str]
    templates: List[TemplateEntry]


DEFAULT_FORMS: List[FormEntry] = [
    FormEntry("ICS_201", "Incident Briefing", "ICS", [], []),
    FormEntry("ICS_202", "Incident Objectives", "ICS", [], []),
    FormEntry("ICS_203", "Organization Assignment List", "ICS", [], []),
    FormEntry("ICS_204", "Assignment List", "ICS", [], []),
    FormEntry("ICS_205", "Communications Plan", "ICS", [], []),
    FormEntry("ICS_206", "Medical Plan", "ICS", [], []),
    FormEntry("ICS_208", "Safety Message/Plan", "ICS", [], []),
    FormEntry("ICS_209", "Incident Status Summary", "ICS", [], []),
    FormEntry("ICS_211", "Check-In List", "ICS", [], []),
    FormEntry("ICS_213", "General Message", "ICS", [], []),
    FormEntry("ICS_213RR", "Resource Request", "ICS", [], []),
    FormEntry("ICS_214", "Activity Log", "ICS", [], []),
    FormEntry("ICS_215", "Operational Planning Worksheet", "ICS", [], []),
    FormEntry("ICS_215A", "Incident Action Plan Safety Analysis", "ICS", [], []),
    FormEntry("ICS_216", "Radio Requirements Worksheet", "ICS", [], []),
    FormEntry("ICS_217", "Communications Resource Availability", "ICS", [], []),
    FormEntry("ICS_218", "Support Vehicle/Equipment Inventory", "ICS", [], []),
    FormEntry("CAPF_109", "CAP Flight Plan", "CAP", [], []),
    FormEntry("SAR_104", "Search Assignment Form", "SAR", [], []),
]


class FormCatalog:
    def __init__(self, path: Path = CATALOG_PATH) -> None:
        self.path = path
        self.data: Dict[str, any] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        if not self.data:
            self.data = {
                "forms": [asdict(f) for f in DEFAULT_FORMS],
                "custom_forms": [],
            }
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ---------------------------- forms ----------------------------
    def list_forms(self) -> List[FormEntry]:
        forms = []
        for raw in self.data.get("forms", []) + self.data.get("custom_forms", []):
            tpls = [TemplateEntry(**t) for t in raw.get("templates", [])]
            forms.append(FormEntry(id=raw["id"], title=raw.get("title", raw["id"]), category=raw.get("category", "ICS"), profiles=list(raw.get("profiles", [])), templates=tpls))
        return forms

    def upsert_form(self, entry: FormEntry, custom: bool = False) -> None:
        key = "custom_forms" if custom else "forms"
        arr = self.data.setdefault(key, [])
        # replace by id if exists
        for i, raw in enumerate(arr):
            if raw.get("id") == entry.id:
                arr[i] = asdict(entry)
                self.save()
                return
        arr.append(asdict(entry))
        self.save()

    def delete_form(self, form_id: str) -> None:
        for key in ("forms", "custom_forms"):
            arr = self.data.get(key, [])
            arr = [x for x in arr if x.get("id") != form_id]
            self.data[key] = arr
        self.save()

    def set_profiles(self, form_id: str, profiles: List[str]) -> None:
        for key in ("forms", "custom_forms"):
            for raw in self.data.get(key, []):
                if raw.get("id") == form_id:
                    raw["profiles"] = list(profiles)
        self.save()

    # ---------------------------- templates ------------------------
    def add_template(self, form_id: str, tpl: TemplateEntry, custom: bool | None = None) -> None:
        def _add(where: str) -> bool:
            for raw in self.data.get(where, []):
                if raw.get("id") == form_id:
                    templ = raw.setdefault("templates", [])
                    # dedupe by version
                    for i, t in enumerate(templ):
                        if t.get("version") == tpl.version:
                            existing = TemplateEntry(**t)
                            merged_profiles = set(existing.profiles or []) | {
                                p.strip() for p in tpl.profiles if p.strip()
                            }
                            pdf = tpl.pdf or existing.pdf
                            mapping = tpl.mapping if tpl.mapping is not None else existing.mapping
                            schema = tpl.schema if tpl.schema is not None else existing.schema
                            updated = TemplateEntry(
                                version=tpl.version,
                                pdf=pdf,
                                mapping=mapping,
                                schema=schema,
                                profiles=sorted(merged_profiles),
                            )
                            templ[i] = asdict(updated)
                            self.save()
                            return True
                    normalized_profiles = sorted({p.strip() for p in tpl.profiles if p.strip()})
                    new_entry = TemplateEntry(
                        version=tpl.version,
                        pdf=tpl.pdf,
                        mapping=tpl.mapping,
                        schema=tpl.schema,
                        profiles=normalized_profiles,
                    )
                    templ.append(asdict(new_entry))
                    self.save()
                    return True
            return False

        if custom is True and _add("custom_forms"):
            return
        if custom is False and _add("forms"):
            return
        if not _add("forms"):
            _add("custom_forms")


__all__ = [
    "FormCatalog",
    "FormEntry",
    "TemplateEntry",
    "CATALOG_PATH",
]

