from __future__ import annotations

"""Legacy registry-based template resolver (deprecated).

Kept for developer tools and older flows using data/templates/registry.json.
Prefer profile-driven templates with FormRegistry in new code.
"""

import warnings as _warnings
_warnings.warn(
    "modules.forms.templating is deprecated; prefer FormRegistry (profile-driven)",
    DeprecationWarning,
    stacklevel=2,
)

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

import yaml

REGISTRY_PATH = Path("data/templates/registry.json")


@dataclass
class TemplateInfo:
    pdf_path: Optional[Path]
    mapping_path: Path
    schema_path: Path


def load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_template(form_id: str, version: str) -> TemplateInfo:
    registry = load_registry()
    form_entry = registry.get(form_id)
    if not form_entry:
        raise KeyError(f"Unknown form: {form_id}")
    info = form_entry.get(version)
    if isinstance(info, str):  # alias e.g. "latest"
        info = form_entry.get(info)
    if not info:
        raise KeyError(f"Unknown version: {form_id}:{version}")
    pdf = Path(info["pdf"]) if "pdf" in info else None
    mapping = Path(info["mapping"])
    schema = Path(info["schema"])
    return TemplateInfo(pdf, mapping, schema)


def load_mapping(mapping_path: Path) -> Dict[str, Any]:
    with mapping_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
