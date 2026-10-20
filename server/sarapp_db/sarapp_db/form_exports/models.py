"""Headless contracts shared by export builders, mappings, and renderers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class ExportError(Exception):
    """A safe export error that the API can present to the caller."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ExportRequest:
    incident_id: str
    form_id: str
    source_id: str | None = None
    operational_period_id: int | None = None
    prepared_by: str = ""
    form_set_id: str | None = None
    prepared_by_position: str = ""


@dataclass
class ExportSnapshot:
    form_id: str
    incident: dict[str, Any]
    period: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    prepared_by: str = ""
    form_set_id: str = "fema"
    prepared_by_position: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


@dataclass(frozen=True)
class TemplateSpec:
    form_set_id: str
    pdf: str
    mapping: str | None = None


@dataclass(frozen=True)
class ResolvedTemplate:
    pdf: Path
    mapping: dict[str, Any] | None


@dataclass(frozen=True)
class FormDefinition:
    form_id: str
    label: str
    source: str
    templates: tuple[TemplateSpec, ...]
    default_set: str
    builder: Callable[[ExportRequest, FormDefinition], ExportSnapshot]
    mapper: Callable[[ExportSnapshot, ResolvedTemplate], list[dict[str, Any]]]
    source_required: bool = False
    period_required: bool = False
    allow_source: bool = True
    minimum_font_size: float = 8.0

    def template(self, form_set_id: str | None) -> TemplateSpec:
        selected = form_set_id or self.default_set
        for template in self.templates:
            if template.form_set_id == selected:
                return template
        raise ExportError(422, "Unsupported form set for this export")

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "form_id": self.form_id, "label": self.label, "source": self.source,
            "set": self.default_set,
            "sets": [template.form_set_id for template in self.templates],
            "source_required": self.source_required, "period_required": self.period_required,
            "allow_source": self.allow_source,
        }


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    filename: str
    form_id: str
    form_set_id: str
    generated_at: str
    media_type: str = "application/pdf"
