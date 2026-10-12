from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from .models import ExportRequest, ExportResult, PreparedExport
from .registry import ExportRegistry


def utcnow_seconds() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


class ExportService:
    """Central front door for form exports."""

    def __init__(
        self,
        registry: ExportRegistry,
        *,
        generator: Callable[..., object] | None = None,
        clock: Callable[[], str] = utcnow_seconds,
    ) -> None:
        self._registry = registry
        self._generator = generator
        self._clock = clock

    def export(self, request: ExportRequest) -> ExportResult:
        builder = self._registry.get(request.form_key)
        prepared = builder.build(request)
        self._generate(prepared)
        generated_at = str(prepared.metadata.get("generated_at") or self._clock())
        return ExportResult(
            form_key=request.form_key,
            form_id=prepared.form_id,
            output_path=prepared.output_path,
            generated_at=generated_at,
            metadata=dict(prepared.metadata),
        )

    def _generate(self, prepared: PreparedExport) -> None:
        if self._generator is not None:
            self._generator(
                prepared.form_id,
                prepared.output_path,
                incident_id=prepared.incident_id,
                form_set_id=prepared.form_set_id,
                extra_data=prepared.extra_data,
            )
            return
        from modules.forms_creator.engine import generate

        generate(
            prepared.form_id,
            prepared.output_path,
            incident_id=prepared.incident_id,
            form_set_id=prepared.form_set_id,
            extra_data=prepared.extra_data,
        )


def default_export_service() -> ExportService:
    from .builders import default_registry

    return ExportService(default_registry())
