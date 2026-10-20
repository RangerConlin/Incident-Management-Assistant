"""Resolve only explicitly registered, bundled form assets."""
from __future__ import annotations

import json
from pathlib import Path

from .models import FormDefinition, ResolvedTemplate

ASSETS = Path(__file__).parent / "assets"


class TemplateResolver:
    def __init__(self, root: Path = ASSETS) -> None:
        self.root = root.resolve()

    def _asset(self, filename: str) -> Path:
        path = (self.root / filename).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Form assets must stay within the configured bundle")
        if not path.is_file():
            raise FileNotFoundError("A registered form asset is unavailable")
        return path

    def resolve(self, definition: FormDefinition, form_set_id: str | None) -> ResolvedTemplate:
        spec = definition.template(form_set_id)
        pdf = self._asset(spec.pdf)
        mapping = None
        if spec.mapping is not None:
            mapping = json.loads(self._asset(spec.mapping).read_text(encoding="utf-8"))
            if not isinstance(mapping, dict) or not isinstance(mapping.get("fields"), list):
                raise ValueError("A form mapping must contain a fields list")
        return ResolvedTemplate(pdf, mapping)
