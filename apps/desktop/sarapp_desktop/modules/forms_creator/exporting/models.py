from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExportRequest:
    """Intent to export a form for an incident-scoped target."""

    form_key: str
    target_type: str = ""
    target_id: int | str | None = None
    incident_id: str | None = None
    form_set_id: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedExport:
    """Data package prepared by an export builder for the form engine."""

    form_id: str
    output_path: Path
    incident_id: str | None
    form_set_id: str | None = None
    extra_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportResult:
    """Result returned by the central export service after generation."""

    form_key: str
    form_id: str
    output_path: Path
    generated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
