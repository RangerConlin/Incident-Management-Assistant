"""The common server entry point: validate, build, resolve, bind, render, download."""
from __future__ import annotations

import re

from .models import (
    ExportError, ExportRequest, ExportResult, ExportSnapshot, FormDefinition, ResolvedTemplate,
)
from .registry import ExportRegistry
from .templates import TemplateResolver


class FormExportService:
    def __init__(
        self, registry: ExportRegistry, resolver: TemplateResolver | None = None,
    ) -> None:
        self.registry = registry
        self.resolver = resolver or TemplateResolver()

    def render_snapshot(self, snapshot: ExportSnapshot) -> bytes:
        definition = self.registry.get(snapshot.form_id)
        template = self.resolver.resolve(definition, snapshot.form_set_id)
        return self._render(snapshot, definition, template)

    @staticmethod
    def _render(
        snapshot: ExportSnapshot, definition: FormDefinition, template: ResolvedTemplate,
    ) -> bytes:
        sheets = definition.mapper(snapshot, template)
        if not sheets:
            raise ValueError("An export mapper must return at least one sheet")
        from .pdf import render_pdf

        return render_pdf(
            snapshot, template=template.pdf, sheets=sheets, label=definition.label,
            minimum_font_size=definition.minimum_font_size,
        )

    def export(self, request: ExportRequest) -> ExportResult:
        definition = self.registry.get(request.form_id)
        selected = definition.template(request.form_set_id).form_set_id
        if not request.incident_id:
            raise ExportError(422, "An incident is required")
        period = request.operational_period_id
        if period is not None and (isinstance(period, bool) or not isinstance(period, int) or period <= 0):
            raise ExportError(422, "Operational period ID must be a positive integer")
        if definition.period_required and period is None:
            raise ExportError(422, "Select an operational period for this form")
        if definition.source_required and not request.source_id:
            raise ExportError(422, "Select a saved source record to export this form")
        if not definition.allow_source and request.source_id is not None:
            raise ExportError(422, "This form exports incident data rather than a source record")
        template = self.resolver.resolve(definition, selected)
        snapshot = definition.builder(request, definition)
        if snapshot.form_id != request.form_id or snapshot.form_set_id != selected:
            raise ValueError("An export builder returned the wrong form or publishing set")
        content = self._render(snapshot, definition, template)
        suffix = re.sub(r"[^A-Za-z0-9_-]", "_", request.source_id or request.incident_id)[:80]
        return ExportResult(
            content, f"{request.form_id}_{suffix}.pdf", request.form_id,
            selected, snapshot.generated_at,
        )


def default_service() -> FormExportService:
    from .builtins import default_registry

    return FormExportService(default_registry())
