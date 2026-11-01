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
        downloader: Callable[..., object] | None = None,
        clock: Callable[[], str] = utcnow_seconds,
    ) -> None:
        self._registry = registry
        self._downloader = downloader
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
        from .server import download_form

        downloader = self._downloader or download_form
        period_id = next(
            (prepared.metadata[key] for key in (
                "operational_period_id", "op_period_id", "op_period"
            ) if prepared.metadata.get(key) not in (None, "")),
            None,
        )
        if period_id is not None:
            if isinstance(period_id, bool):
                raise ValueError("Operational period ID must be numeric")
            try:
                period_id = int(period_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Operational period ID must be numeric") from exc
        target_type = str(prepared.metadata.get("target_type") or "").strip().lower()
        target_id = prepared.metadata.get("target_id")
        if period_id is None and target_type in {"operational_period", "op_period"}:
            try:
                period_id = int(target_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Operational period ID must be numeric") from exc
        source_id = None if target_type in {"operational_period", "op_period"} else target_id
        downloader(
            str(prepared.incident_id or ""),
            prepared.form_id,
            prepared.output_path,
            source_id=source_id,
            operational_period_id=period_id,
            prepared_by=str(prepared.metadata.get("prepared_by") or ""),
            form_set_id=prepared.form_set_id,
            prepared_by_position=str(prepared.metadata.get("prepared_by_position") or ""),
        )


def default_export_service() -> ExportService:
    from .builders import default_registry

    return ExportService(default_registry())
