"""Minimal profile manager used for deterministic template lookup.

Only a very small subset of the functionality from the real application is
implemented here – just enough for unit tests.  Profiles are stored on disk in
``profiles/<profile_id>`` and templates are located under the ``templates``
subdirectory.  The :meth:`resolve_by_uid` helper parses the template UID and
returns the parsed JSON document.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json


class ProfileManager:
    def __init__(self, profiles_dir: str | Path, active_profile_id: str):
        self.profiles_dir = Path(profiles_dir)
        self.active_profile_id = active_profile_id

    # ---------------------------------------------------------------- assets
    def assets_path(self, relative: str, profile_id: str | None = None) -> Path:
        """Resolve ``relative`` against the profile directory."""

        pid = profile_id or self.active_profile_id
        return (self.profiles_dir / pid / relative).resolve()

    # -------------------------------------------------------------- templates
    def resolve_by_uid(self, template_uid: str) -> Dict[str, Any]:
        """Return the template JSON for ``template_uid``.

        The UID is expected to have the format ``"<profile>:<form>@<version>"``.
        A :class:`ValueError` is raised if the UID does not belong to the active
        profile or if the template cannot be located.
        """

        try:
            profile_id, rest = template_uid.split(":", 1)
            form_id, version = rest.split("@", 1)
        except ValueError as exc:  # pragma: no cover - defensive programming
            raise ValueError(f"Invalid template UID: {template_uid}") from exc

        if profile_id != self.active_profile_id:
            raise ValueError("template UID profile does not match active profile")

        templates_dir = self.profiles_dir / profile_id / "templates"
        for path in templates_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # pragma: no cover - invalid JSON
                continue
            if data.get("template_uid") == template_uid:
                return data
        raise FileNotFoundError(f"Template not found for UID: {template_uid}")


__all__ = ["ProfileManager"]

