from __future__ import annotations

from .builder import ExportBuilder


def normalize_form_key(form_key: str) -> str:
    return str(form_key or "").strip().lower()


class ExportRegistry:
    """Registry mapping export form keys to data builders."""

    def __init__(self) -> None:
        self._builders: dict[str, ExportBuilder] = {}

    def register(self, form_key: str, builder: ExportBuilder) -> None:
        key = normalize_form_key(form_key)
        if not key:
            raise ValueError("form_key is required")
        self._builders[key] = builder

    def get(self, form_key: str) -> ExportBuilder:
        key = normalize_form_key(form_key)
        try:
            return self._builders[key]
        except KeyError as exc:
            raise KeyError(f"No export builder is registered for '{form_key}'.") from exc

    def keys(self) -> list[str]:
        return sorted(self._builders)
