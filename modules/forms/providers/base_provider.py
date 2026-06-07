from __future__ import annotations

from typing import Any

from modules.forms.models import BindingResult


class BindingProvider:
    namespace = "base"

    def resolve(self, path: str, context: dict[str, Any] | None = None) -> BindingResult:
        return BindingResult(key=f"{self.namespace}.{path}", source_module=self.namespace, error="provider not wired")

    def describe(self) -> list[dict[str, Any]]:
        return []


class StaticContextProvider(BindingProvider):
    def __init__(self, namespace: str, keys: list[str]) -> None:
        self.namespace = namespace
        self._keys = keys

    def resolve(self, path: str, context: dict[str, Any] | None = None) -> BindingResult:
        context = context or {}
        value = self._lookup(context.get(self.namespace, {}), path.split("."))
        if value is None:
            return BindingResult(key=f"{self.namespace}.{path}", source_module=self.namespace, error="value unavailable")
        return BindingResult(key=f"{self.namespace}.{path}", value=value, display_value=str(value), source_module=self.namespace, confidence=1.0)

    def describe(self) -> list[dict[str, Any]]:
        return [{"key": f"{self.namespace}.{k}", "provider": self.namespace} for k in self._keys]

    def _lookup(self, data: Any, parts: list[str]) -> Any:
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                return None
        return current
