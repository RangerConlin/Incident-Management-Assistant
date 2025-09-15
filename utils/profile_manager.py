from __future__ import annotations
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from .settingsmanager import SettingsManager


@dataclass
class ProfileMeta:
    """Metadata about a profile discovered on disk."""

    id: str
    name: str
    path: Path
    manifest: Dict[str, Any]


@dataclass
class Issue:
    level: str
    code: str
    message: str
    path: str


class ComputedRegistry(dict):
    """Simple mapping of computed binding names to callables."""


class ProfileManager:
    """Singleton responsible for loading and managing profiles."""

    _instance: "ProfileManager" | None = None

    def __new__(cls) -> "ProfileManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._profiles: Dict[str, ProfileMeta] = {}
            cls._instance._active_id: Optional[str] = None
            cls._instance._root_dir: Path = Path("profiles")
            cls._instance._settings = SettingsManager()
        return cls._instance

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _deep_merge(self, base: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for k, v in new.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def _profile_chain(self, profile_id: str) -> List[ProfileMeta]:
        meta = self._profiles[profile_id]
        chain: List[ProfileMeta] = []
        for parent_id in meta.manifest.get("inherits", []):
            chain.extend(self._profile_chain(parent_id))
        chain.append(meta)
        # remove duplicates preserving order
        unique: List[ProfileMeta] = []
        seen = set()
        for m in chain:
            if m.id not in seen:
                unique.append(m)
                seen.add(m.id)
        return unique

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_all_profiles(self, root_dir: str | Path) -> None:
        """Scan root_dir for profiles and load their manifests."""
        self._root_dir = Path(root_dir)
        self._profiles.clear()
        for manifest_file in self._root_dir.glob("*/manifest.json"):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                pid = manifest.get("id")
                if not pid:
                    continue
                meta = ProfileMeta(
                    id=pid,
                    name=manifest.get("name", pid),
                    path=manifest_file.parent,
                    manifest=manifest,
                )
                self._profiles[pid] = meta
            except Exception:
                continue

        active = self._settings.get("active_profile_id")
        if active in self._profiles:
            self._active_id = active
        elif self._profiles:
            # pick first profile as default
            self._active_id = next(iter(self._profiles))
            self._settings.set("active_profile_id", self._active_id)

    def list_profiles(self) -> List[ProfileMeta]:
        return list(self._profiles.values())

    def get_active_profile_id(self) -> Optional[str]:
        return self._active_id

    # ------------------------------------------------------------------
    # Linter
    # ------------------------------------------------------------------
    def lint_profile(self, profile_id: str) -> List[Issue]:
        issues: List[Issue] = []
        if profile_id not in self._profiles:
            issues.append(Issue("ERROR", "UNKNOWN_PROFILE", f"Profile {profile_id} not found", ""))
            return issues
        chain = self._profile_chain(profile_id)
        meta = chain[-1]
        manifest = meta.manifest
        required_fields = [
            "id",
            "name",
            "templates_dir",
            "catalog",
            "computed_module",
        ]
        for field in required_fields:
            if field not in manifest:
                issues.append(
                    Issue(
                        "ERROR",
                        "MANIFEST_MISSING",
                        f"Missing field '{field}' in manifest",
                        str(meta.path / "manifest.json"),
                    )
                )

        # load merged catalog and computed
        catalog = self.get_catalog_for_profile(profile_id)
        computed = self.get_computed_for_profile(profile_id)

        # iterate templates and validate
        seen_keys: Dict[str, str] = {}
        for m in chain:
            tdir = m.path / m.manifest.get("templates_dir", "templates")
            for tpl in tdir.glob("*_template.json"):
                try:
                    with open(tpl, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    issues.append(Issue("ERROR", "TEMPLATE_PARSE", str(e), str(tpl)))
                    continue
                if data.get("template_version") != 2:
                    issues.append(
                        Issue(
                            "ERROR",
                            "TEMPLATE_VERSION",
                            f"{tpl.name} is not Template v2",
                            str(tpl),
                        )
                    )
                for field in data.get("fields", []):
                    key = field.get("key")
                    if key:
                        if key in seen_keys and seen_keys[key] != tpl.name:
                            issues.append(
                                Issue(
                                    "ERROR",
                                    "DUPLICATE_KEY",
                                    f"Field key '{key}' duplicated in {seen_keys[key]} and {tpl.name}",
                                    str(tpl),
                                )
                            )
                        else:
                            seen_keys[key] = tpl.name
                    binding = field.get("binding", {})
                    bkey = binding.get("key")
                    if bkey:
                        if bkey not in catalog.get("keys", {}):
                            if bkey not in computed:
                                issues.append(
                                    Issue(
                                        "ERROR",
                                        "UNKNOWN_BINDING",
                                        f"Binding key '{bkey}' not found in catalog or computed",
                                        str(tpl),
                                    )
                                )
        return issues

    # ------------------------------------------------------------------
    def set_active_profile(self, profile_id: str) -> None:
        issues = self.lint_profile(profile_id)
        if any(i.level == "ERROR" for i in issues):
            raise ValueError(f"Profile {profile_id} failed validation: {[i.message for i in issues]}")
        self._active_id = profile_id
        self._settings.set("active_profile_id", profile_id)

    # ------------------------------------------------------------------
    # Resolving Data
    # ------------------------------------------------------------------
    def resolve_template(self, form_id: str) -> Dict[str, Any]:
        if not self._active_id:
            raise RuntimeError("No active profile")
        chain = self._profile_chain(self._active_id)
        merged: Dict[str, Any] = {}
        found = False
        for m in chain:
            tdir = m.path / m.manifest.get("templates_dir", "templates")
            f = tdir / f"{form_id}_template.json"
            if f.exists():
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                merged = self._deep_merge(merged, data)
                found = True
        if not found:
            raise FileNotFoundError(f"Template {form_id} not found in profile {self._active_id}")
        return merged

    def get_catalog_for_profile(self, profile_id: str) -> Dict[str, Any]:
        chain = self._profile_chain(profile_id)
        catalog: Dict[str, Any] = {}
        for m in chain:
            cpath = m.path / m.manifest.get("catalog", "catalog.json")
            if cpath.exists():
                with open(cpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                catalog = self._deep_merge(catalog, data)
        return catalog

    def get_catalog(self) -> Dict[str, Any]:
        if not self._active_id:
            return {}
        return self.get_catalog_for_profile(self._active_id)

    def get_computed_for_profile(self, profile_id: str) -> ComputedRegistry:
        chain = self._profile_chain(profile_id)
        registry: ComputedRegistry = ComputedRegistry()
        for m in chain:
            module_path = m.path / m.manifest.get("computed_module", "computed.py")
            if module_path.exists():
                mod_name = f"computed_{m.id}"
                spec = importlib.util.spec_from_file_location(mod_name, module_path)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                loader = spec.loader
                assert loader is not None
                loader.exec_module(module)  # type: ignore
                functions: Dict[str, Callable] = {}
                if hasattr(module, "computed_map") and isinstance(module.computed_map, dict):
                    functions = module.computed_map
                else:
                    for name in dir(module):
                        if name.startswith("_"):
                            continue
                        obj = getattr(module, name)
                        if callable(obj):
                            functions[name] = obj
                registry.update(functions)
        return registry

    def get_computed(self) -> ComputedRegistry:
        if not self._active_id:
            return ComputedRegistry()
        return self.get_computed_for_profile(self._active_id)

    def assets_path(self, name: str) -> Path:
        if not self._active_id:
            raise RuntimeError("No active profile")
        chain = self._profile_chain(self._active_id)
        for m in reversed(chain):
            assets = m.manifest.get("assets", {})
            if name in assets:
                p = m.path / assets[name]
                if p.exists():
                    return p
        raise KeyError(name)

    def hot_reload(self) -> None:
        """Re-load active profile data from disk."""
        # simply reload all manifests and keep the same active id
        active = self._active_id
        self.load_all_profiles(self._root_dir)
        if active:
            self._active_id = active if active in self._profiles else None


# convenience default instance
profile_manager = ProfileManager()
