from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.profile_manager import profile_manager


@dataclass(frozen=True)
class BindingOption:
    """A single binding entry exposed to authoring tools."""

    key: str
    source: str
    description: str
    synonyms: List[str]
    patterns: List[str]
    origin_profile: Optional[str]
    is_defined_in_active: bool
    extra: Dict[str, Any]

    @property
    def display_label(self) -> str:
        source = (self.source or "").strip() or "?"
        label = f"{source} · {self.key}"
        desc = (self.description or "").strip()
        if desc:
            label = f"{label} — {desc}"
        return label

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = dict(self.extra)
        if self.source:
            payload["source"] = self.source
        else:
            payload.pop("source", None)
        if self.description:
            payload["desc"] = self.description
        else:
            payload.pop("desc", None)
        if self.synonyms:
            payload["synonyms"] = list(self.synonyms)
        else:
            payload.pop("synonyms", None)
        if self.patterns:
            payload["patterns"] = list(self.patterns)
        else:
            payload.pop("patterns", None)
        return payload


@dataclass(frozen=True)
class BindingLibraryResult:
    options: List[BindingOption]
    active_profile_id: Optional[str]
    catalog_path: Optional[Path]


def _profile_chain(profile_id: str) -> List[Tuple[str, Dict[str, Any], Path]]:
    profiles = {meta.id: meta for meta in profile_manager.list_profiles()}
    chain: List[Tuple[str, Dict[str, Any], Path]] = []
    seen: set[str] = set()

    def _walk(pid: str) -> None:
        meta = profiles.get(pid)
        if meta is None:
            return
        inherits = meta.manifest.get("inherits", [])
        if isinstance(inherits, list):
            for parent in inherits:
                if isinstance(parent, str):
                    _walk(parent)
        if meta.id not in seen:
            seen.add(meta.id)
            catalog_name = meta.manifest.get("catalog", "catalog.json")
            chain.append((meta.id, meta.manifest, meta.path / catalog_name))

    _walk(profile_id)
    return chain


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _parse_option(
    key: str,
    meta: Dict[str, Any],
    origin_profile: Optional[str],
    active_profile: Optional[str],
) -> BindingOption:
    source = str(meta.get("source") or "constants")
    desc = str(meta.get("desc") or meta.get("description") or "")
    raw_synonyms = meta.get("synonyms", [])
    synonyms = [str(s).strip() for s in raw_synonyms if isinstance(s, str) and s.strip()]
    raw_patterns = meta.get("patterns", [])
    patterns = [str(p).strip() for p in raw_patterns if isinstance(p, str) and p.strip()]
    known_keys = {"source", "desc", "description", "synonyms", "patterns"}
    extra = {k: v for k, v in meta.items() if k not in known_keys}
    return BindingOption(
        key=key,
        source=source,
        description=desc,
        synonyms=synonyms,
        patterns=patterns,
        origin_profile=origin_profile,
        is_defined_in_active=origin_profile == active_profile,
        extra=extra,
    )


def load_binding_library(profile_id: Optional[str] = None) -> BindingLibraryResult:
    """Return binding entries from the active (or specified) profile catalog."""

    try:
        if profile_id:
            catalog = profile_manager.get_catalog_for_profile(profile_id)
            active_profile = profile_id
        else:
            catalog = profile_manager.get_catalog()
            active_profile = profile_manager.get_active_profile_id()
    except Exception:
        catalog = {}
        active_profile = profile_id or profile_manager.get_active_profile_id()

    active_catalog_path: Optional[Path] = None

    if active_profile:
        for pid, _, path in _profile_chain(active_profile):
            data = _load_json(path)
            if pid == active_profile:
                active_catalog_path = path
            keys_section = data.get("keys") if isinstance(data, dict) else {}
            if isinstance(keys_section, dict):
                origin_map = catalog.setdefault("__origin__", {})
                if isinstance(origin_map, dict):
                    for raw_key in keys_section:
                        if isinstance(raw_key, str):
                            origin_map[raw_key] = pid

    keys_section = catalog.get("keys") if isinstance(catalog, dict) else {}
    if not isinstance(keys_section, dict):
        return BindingLibraryResult([], active_profile, active_catalog_path)

    origin_map: Dict[str, str] = catalog.get("__origin__", {}) if isinstance(catalog, dict) else {}

    options: List[BindingOption] = []
    for raw_key, raw_meta in keys_section.items():
        if not isinstance(raw_key, str):
            continue
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        origin_profile = origin_map.get(raw_key)
        option = _parse_option(raw_key, meta, origin_profile, active_profile)
        options.append(option)

    options.sort(key=lambda opt: opt.key.lower())
    return BindingLibraryResult(options=options, active_profile_id=active_profile, catalog_path=active_catalog_path)


def save_binding_option(
    option: BindingOption,
    profile_id: Optional[str] = None,
    original_key: Optional[str] = None,
) -> None:
    target_profile = profile_id or profile_manager.get_active_profile_id()
    if not target_profile:
        raise RuntimeError("No active profile selected")

    chain = _profile_chain(target_profile)
    active_entry = next((entry for entry in chain if entry[0] == target_profile), None)
    if not active_entry:
        raise RuntimeError(f"Profile {target_profile} not found")

    _, _, catalog_path = active_entry
    data = _load_json(catalog_path)
    if "version" not in data:
        data["version"] = 1
    keys_section = data.setdefault("keys", {})
    if not isinstance(keys_section, dict):
        keys_section = {}
        data["keys"] = keys_section

    if original_key and original_key != option.key:
        keys_section.pop(original_key, None)

    keys_section[option.key] = option.to_payload()
    _write_json(catalog_path, data)


def delete_binding_option(key: str, profile_id: Optional[str] = None) -> bool:
    target_profile = profile_id or profile_manager.get_active_profile_id()
    if not target_profile:
        raise RuntimeError("No active profile selected")

    chain = _profile_chain(target_profile)
    active_entry = next((entry for entry in chain if entry[0] == target_profile), None)
    if not active_entry:
        raise RuntimeError(f"Profile {target_profile} not found")

    _, _, catalog_path = active_entry
    data = _load_json(catalog_path)
    keys_section = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys_section, dict) or key not in keys_section:
        return False

    keys_section.pop(key, None)
    _write_json(catalog_path, data)
    return True


__all__ = [
    "BindingOption",
    "BindingLibraryResult",
    "load_binding_library",
    "save_binding_option",
    "delete_binding_option",
]
