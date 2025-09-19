from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.profile_manager import profile_manager


@dataclass(frozen=True)
class BindingOption:
    """A single binding entry exposed to authoring tools."""

    key: str
    source: str
    description: str

    @property
    def display_label(self) -> str:
        source = (self.source or "").strip() or "?"
        label = f"{source} · {self.key}"
        desc = (self.description or "").strip()
        if desc:
            label = f"{label} — {desc}"
        return label


def _iter_catalog_keys(catalog: Dict[str, object]) -> List[BindingOption]:
    keys = catalog.get("keys") if isinstance(catalog, dict) else None
    if not isinstance(keys, dict):
        return []
    options: List[BindingOption] = []
    for raw_key, raw_meta in keys.items():
        if not isinstance(raw_key, str):
            continue
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        source = str(meta.get("source") or "constants")
        desc = str(meta.get("desc") or meta.get("description") or "")
        options.append(BindingOption(key=raw_key, source=source, description=desc))
    return options


def load_binding_library(profile_id: Optional[str] = None) -> List[BindingOption]:
    """Return binding entries from the active (or specified) profile catalog."""

    try:
        if profile_id:
            catalog = profile_manager.get_catalog_for_profile(profile_id)
        else:
            catalog = profile_manager.get_catalog()
    except Exception:
        catalog = {}

    options = list(_iter_catalog_keys(catalog))
    deduped: Dict[str, BindingOption] = {}
    for option in options:
        deduped.setdefault(option.key, option)
    return sorted(deduped.values(), key=lambda opt: opt.key.lower())


__all__ = ["BindingOption", "load_binding_library"]
