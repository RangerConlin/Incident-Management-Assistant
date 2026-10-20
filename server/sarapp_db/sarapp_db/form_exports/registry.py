"""Explicit registrations for wired forms; no dynamic imports from request data."""
from __future__ import annotations

import re

from .models import ExportError, FormDefinition


class ExportRegistry:
    def __init__(self) -> None:
        self._forms: dict[str, FormDefinition] = {}

    def register(self, definition: FormDefinition) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", definition.form_id):
            raise ValueError("Invalid canonical form ID")
        if definition.form_id in self._forms:
            raise ValueError(f"Duplicate export registration: {definition.form_id}")
        sets = [template.form_set_id for template in definition.templates]
        if not sets or len(set(sets)) != len(sets) or definition.default_set not in sets:
            raise ValueError("An export must declare unique form sets and a valid default")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]*", value) for value in sets):
            raise ValueError("Invalid canonical form set ID")
        if not callable(definition.builder) or not callable(definition.mapper):
            raise ValueError("An export must have both a builder and a mapper")
        if not 6.0 <= definition.minimum_font_size <= 10.0:
            raise ValueError("Export font minimum must be between 6 and 10 points")
        self._forms[definition.form_id] = definition

    def get(self, form_id: str) -> FormDefinition:
        try:
            return self._forms[form_id]
        except KeyError as exc:
            raise ExportError(404, "Unsupported form export") from exc

    def definitions(self) -> tuple[FormDefinition, ...]:
        return tuple(self._forms.values())

    def catalog(self) -> list[dict]:
        return [definition.catalog_entry() for definition in self.definitions()]
