from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .form_binding import FormBindingDefinition
from .form_field import FormFieldDefinition, FormValidationRule


@dataclass(slots=True)
class FormTemplateVersion:
    template_id: int
    version_number: int
    layout: dict[str, Any]
    fields: list[FormFieldDefinition]
    id: int | None = None
    version_label: str | None = None
    effective_date: str | None = None
    retired_date: str | None = None
    bindings: list[FormBindingDefinition] = field(default_factory=list)
    validation_rules: list[FormValidationRule] = field(default_factory=list)
    export_profiles: dict[str, Any] = field(default_factory=dict)
    source_asset_path: str | None = None
    checksum: str | None = None
    change_summary: str | None = None
    created_by: str | None = None
    created_at: str | None = None
    is_current: bool = False


@dataclass(slots=True)
class FormTemplate:
    family_id: int
    agency: str
    code: str
    title: str
    id: int | None = None
    system: str | None = None
    description: str | None = None
    status: str = "active"
    current_version_id: int | None = None
    compatibility: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    current_version: FormTemplateVersion | None = None
