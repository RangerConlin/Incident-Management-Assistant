"""Resolve a form_id + active form set to a (template_pdf, mapping_json) pair."""

from __future__ import annotations

from pathlib import Path

from .form_set_registry import FormSetRegistry


class FormNotAvailableError(Exception):
    """Raised when no template or mapping can be found for the requested form."""


class FormResolver:
    """Given a form_id and an active form set, returns file paths via fallback chain."""

    def __init__(self, registry: FormSetRegistry | None = None, forms_root: Path | str | None = None) -> None:
        self._registry = registry or FormSetRegistry(forms_root)

    def resolve(
        self,
        form_id: str,
        form_set_id: str | None = None,
    ) -> tuple[Path, Path]:
        """Return (template_pdf_path, mapping_json_path) for the given form.

        Walks the fallback chain of the active set until a complete implementation
        (both template.pdf and mapping.json) is found.  Falls back to the global
        default set if form_set_id is not provided or not found.

        Raises FormNotAvailableError if no implementation exists anywhere in the chain.
        """
        active_id = form_set_id or self._default_set_id()
        visited: set[str] = set()
        current_id: str | None = active_id

        while current_id and current_id not in visited:
            visited.add(current_id)
            set_meta = self._registry.get_set(current_id)
            if set_meta is None:
                break
            form_dir = set_meta.path / form_id
            template = form_dir / "template.pdf"
            mapping = form_dir / "mapping.json"
            if template.exists() and mapping.exists():
                return template, mapping
            current_id = set_meta.fallback

        # Last resort: try the configured default if not already tried
        default_id = self._default_set_id()
        if default_id not in visited:
            set_meta = self._registry.get_set(default_id)
            if set_meta:
                form_dir = set_meta.path / form_id
                template = form_dir / "template.pdf"
                mapping = form_dir / "mapping.json"
                if template.exists() and mapping.exists():
                    return template, mapping

        raise FormNotAvailableError(
            f"No template+mapping found for form '{form_id}' "
            f"in set '{active_id}' or its fallback chain."
        )

    def resolve_mapping_only(self, form_id: str, form_set_id: str | None = None) -> Path:
        """Return mapping_json_path only — used by the mapper tool and engine preview."""
        active_id = form_set_id or self._default_set_id()
        visited: set[str] = set()
        current_id: str | None = active_id

        while current_id and current_id not in visited:
            visited.add(current_id)
            set_meta = self._registry.get_set(current_id)
            if set_meta is None:
                break
            mapping = set_meta.path / form_id / "mapping.json"
            if mapping.exists():
                return mapping
            current_id = set_meta.fallback

        raise FormNotAvailableError(
            f"No mapping found for form '{form_id}' in set '{active_id}' or its fallback chain."
        )

    def _default_set_id(self) -> str:
        import json
        from pathlib import Path as _Path
        config = _Path(__file__).resolve().parents[2] / "forms" / "config.json"
        try:
            return json.loads(config.read_text(encoding="utf-8")).get("default_form_set", "fema")
        except Exception:
            return "fema"
