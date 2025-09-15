"""Registry for template JSON files.

The registry is responsible for loading all templates for a given profile and
providing quick lookup by ``template_uid``.  Templates follow the v2 JSON
schema outlined in the design documents.  The implementation here intentionally
performs only a light-weight validation suitable for unit tests; the full
application performs more exhaustive checks and logging.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any
import json
import copy


ALLOWED_BINDING_SOURCES = {"constants", "mission", "personnel", "env", "computed", None}


@dataclass
class TemplateMeta:
    template_uid: str
    title: str
    category: str | None
    form_id: str
    form_version: str
    profile_id: str


class FormRegistry:
    """Load and index template JSON files for a profile."""

    def __init__(self, profiles_dir: str | Path, profile_id: str):
        self._profiles_dir = Path(profiles_dir)
        self.profile_id = profile_id
        self._dir = self._profiles_dir / profile_id / "templates"
        self._index: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ utils
    def _validate_template(self, data: Dict[str, Any], path: Path) -> None:
        if data.get("template_version") != 2:
            raise ValueError(f"{path} is not a v2 template")

        required = ["profile_id", "form_id", "form_version", "template_uid", "renderer"]
        for key in required:
            if key not in data:
                raise ValueError(f"{path} missing required field {key}")

        profile_id = data["profile_id"]
        form_id = data["form_id"]
        version = data["form_version"]
        expected_uid = f"{profile_id}:{form_id}@{version}"
        if data["template_uid"] != expected_uid:
            raise ValueError(f"{path} has mismatched template_uid")

        if data.get("renderer", "pdf") == "pdf":
            src = data.get("pdf_source")
            if not src:
                raise ValueError(f"{path} missing pdf_source")
            if not data.get("pdf_fingerprint"):
                raise ValueError(f"{path} missing pdf_fingerprint")
            pdf_path = (self._profiles_dir / profile_id / src).resolve()
            if not pdf_path.exists():
                raise ValueError(f"Base PDF not found: {pdf_path}")

        for field in data.get("fields", []):
            binding = field.get("binding") or {}
            src = binding.get("source")
            if src not in ALLOWED_BINDING_SOURCES:
                raise ValueError(f"Invalid binding source {src} in {path}")

    # ------------------------------------------------------------------- api
    def load(self) -> None:
        """Load template JSON files from the profile directory."""

        self._index.clear()
        if not self._dir.exists():
            return

        for tpl_path in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(tpl_path.read_text(encoding="utf-8"))
                self._validate_template(data, tpl_path)
            except Exception:
                # Invalid templates are skipped entirely; in the real
                # application they would be logged for diagnostics.
                continue

            # Remember the profile directory to help locating assets later.
            data.setdefault("_profile_dir", str(self._profiles_dir / self.profile_id))
            self._index[data["template_uid"]] = data

    def get(self, template_uid: str) -> Dict[str, Any]:
        """Return a deep copy of the template for ``template_uid``."""

        if template_uid not in self._index:
            raise KeyError(f"Unknown template: {template_uid}")
        return copy.deepcopy(self._index[template_uid])

    def list(self) -> List[TemplateMeta]:
        """Return metadata for all loaded templates.

        The list is useful for populating template pickers.  Only a subset of
        information is returned so callers do not need to parse the full JSON
        document.
        """

        items: List[TemplateMeta] = []
        for uid, data in self._index.items():
            items.append(
                TemplateMeta(
                    template_uid=uid,
                    title=data.get("title", ""),
                    category=data.get("category"),
                    form_id=data.get("form_id", ""),
                    form_version=data.get("form_version", ""),
                    profile_id=data.get("profile_id", ""),
                )
            )
        return items


__all__ = ["FormRegistry", "TemplateMeta"]

