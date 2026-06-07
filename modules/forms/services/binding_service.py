from __future__ import annotations

from typing import Any

from modules.forms.models import BindingResult
from modules.forms.providers import (
    BindingProvider, CommunicationsProvider, FinanceProvider, IncidentProvider, IntelProvider,
    LiaisonProvider, LogisticsProvider, MedicalProvider, OperationsProvider, PersonnelProvider, PlanningProvider,
)


class BindingService:
    def __init__(self, providers: list[BindingProvider] | None = None) -> None:
        self.providers: dict[str, BindingProvider] = {}
        for provider in providers or [IncidentProvider(), PersonnelProvider(), PlanningProvider(), OperationsProvider(), LogisticsProvider(), CommunicationsProvider(), MedicalProvider(), IntelProvider(), LiaisonProvider(), FinanceProvider()]:
            self.register_provider(provider)

    def register_provider(self, provider: BindingProvider) -> None:
        self.providers[provider.namespace] = provider

    def resolve(self, binding_key: str, context: dict[str, Any] | None = None) -> BindingResult:
        namespace, _, path = binding_key.partition(".")
        if not namespace or not path:
            return BindingResult(key=binding_key, error="binding key must include provider and path")
        provider = self.providers.get(namespace)
        if not provider:
            return BindingResult(key=binding_key, source_module=namespace, error="provider unavailable")
        try:
            return provider.resolve(path, context or {})
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return BindingResult(key=binding_key, source_module=namespace, error=str(exc))

    def describe_available_bindings(self) -> list[dict[str, Any]]:
        bindings: list[dict[str, Any]] = []
        for provider in sorted(self.providers.values(), key=lambda p: p.namespace):
            bindings.extend(provider.describe())
        return bindings

    def refresh_unlocked_fields(self, fields: list[dict[str, Any]], current_values: dict[str, dict[str, Any]], context: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        updates: dict[str, dict[str, Any]] = {}
        for field in fields:
            key = field.get("key")
            binding_key = field.get("binding_key")
            existing = current_values.get(key or "", {})
            if not key or not binding_key or existing.get("is_locked") or existing.get("is_overridden"):
                continue
            result = self.resolve(binding_key, context)
            if result.error:
                continue
            updates[key] = {
                "value": result.value,
                "display_value": result.display_value,
                "source_type": result.source_type,
                "source_binding": result.key,
                "source_module": result.source_module,
                "source_record_id": result.source_record_id,
            }
        return updates
