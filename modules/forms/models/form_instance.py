from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FormInstance:
    family_id: int
    template_id: int
    template_version_id: int
    incident_id: str
    id: int | None = None
    operational_period_id: str | None = None
    linked_module: str | None = None
    linked_record_id: str | None = None
    title: str | None = None
    agency: str | None = None
    status: str = "draft"
    revision_number: int = 1
    created_by: str | None = None
    created_at: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None
    finalized_by: str | None = None
    finalized_at: str | None = None
    exported_pdf_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FormFieldValue:
    instance_id: int
    field_key: str
    value: Any = None
    id: int | None = None
    display_value: str | None = None
    source_type: str = "manual"
    source_binding: str | None = None
    source_module: str | None = None
    source_record_id: str | None = None
    is_locked: bool = False
    is_overridden: bool = False
    override_reason: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class FormInstanceRevision:
    instance_id: int
    revision_number: int
    snapshot: dict[str, Any]
    id: int | None = None
    change_summary: str | None = None
    created_by: str | None = None
    created_at: str | None = None
