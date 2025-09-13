from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import json

from .pdf_mapgen import extract_acroform_fields


@dataclass
class ValidationReport:
    coverage_pct: float
    unmapped_fields: List[str]
    warnings: List[str]


class TemplateRegistry:
    """Load/save registry.json and provide helpers for activation and validation.

    Registry structure (example):
    {
      "ics_205": {
        "2025.09": {
          "pdf": "data/templates/ics/ICS_205_v2025.09.pdf",
          "mapping": "data/templates/ics/ICS_205_v2025.09.map.yaml",
          "schema": null,
          "domain": "ics",
          "group": "default"
        },
        "aliases": {"latest": "2025.09"},
        "active": "2025.09",
        "groups": {
          "default": ["2025.09"],
          "agency_jackson": ["2025.09", "2025.08-customA"]
        }
      },
      "__active_by_form__": {"ics_205": "2025.09"},
      "__active_group__": "default"
    }
    """

    def __init__(self, path: Path):
        self.path = path
        self.data: Dict = {}
        self.load()

    # ----------------------- core io -----------------------
    def load(self):
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"__active_by_form__": {}, "__active_group__": "default"}
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ----------------------- registration ------------------
    def register(
        self,
        *,
        form_id: str,
        version: str,
        pdf_path: Path,
        mapping_path: Path,
        schema_path: Optional[Path],
        domain: str,
        group: Optional[str],
    ):
        block = self.data.setdefault(form_id, {})
        block[version] = {
            "pdf": str(pdf_path).replace("\\", "/"),
            "mapping": str(mapping_path).replace("\\", "/"),
            "schema": str(schema_path).replace("\\", "/") if schema_path else None,
            "domain": domain,
            "group": group or "default",
        }
        groups = block.setdefault("groups", {})
        gname = group or "default"
        versions = groups.setdefault(gname, [])
        if version not in versions:
            versions.append(version)
        aliases = block.setdefault("aliases", {})
        aliases.setdefault("latest", version)
        self.save()

    # ----------------------- activation --------------------
    def set_active(self, form_id: str, version: str):
        if form_id not in self.data or version not in self.data[form_id]:
            raise ValueError(f"Unknown form/version: {form_id}:{version}")
        self.data[form_id]["active"] = version
        self.data.setdefault("__active_by_form__", {})[form_id] = version
        self.save()

    def active(self, form_id: str) -> Optional[str]:
        blk = self.data.get(form_id)
        if not blk:
            return None
        return blk.get("active") or blk.get("aliases", {}).get("latest")

    # ----------------------- group control -----------------
    def set_active_group(self, group: str):
        self.data["__active_group__"] = group
        self.save()

    def active_group(self) -> str:
        return self.data.get("__active_group__", "default")

    # ----------------------- validation --------------------
    def validate_entry(self, form_id: str, version: str) -> ValidationReport:
        blk = self.data.get(form_id, {})
        entry = blk.get(version)
        if not entry:
            return ValidationReport(
                coverage_pct=0.0,
                unmapped_fields=["<missing entry>"],
                warnings=["No entry in registry"],
            )

        pdf_p = Path(entry["pdf"])
        map_p = Path(entry["mapping"])
        if not (pdf_p.exists() and map_p.exists()):
            return ValidationReport(
                coverage_pct=0.0,
                unmapped_fields=["<missing files>"],
                warnings=["PDF or mapping file missing"],
            )

        import yaml

        mapping = yaml.safe_load(map_p.read_text(encoding="utf-8")) or {}
        fields_map: Dict = mapping.get("fields", {})

        pdf_fields = extract_acroform_fields(pdf_p)
        pdf_names = [f.name for f in pdf_fields]

        mapped = [k for k in fields_map.keys() if k in pdf_names]
        unmapped = [k for k in pdf_names if k not in fields_map]
        cov = (len(mapped) / max(1, len(pdf_names))) * 100.0

        warns: List[str] = []
        if unmapped:
            warns.append("Some PDF fields are not mapped")

        return ValidationReport(
            coverage_pct=cov,
            unmapped_fields=unmapped,
            warnings=warns,
        )

    # ----------------------- diffs -------------------------
    def diff_fields(self, old_pdf: Path, new_pdf: Path) -> Dict[str, List[str]]:
        old = {f.name for f in extract_acroform_fields(old_pdf)}
        new = {f.name for f in extract_acroform_fields(new_pdf)}
        return {
            "added": sorted(list(new - old)),
            "removed": sorted(list(old - new)),
            "common": sorted(list(old & new)),
        }

