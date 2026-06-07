from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FamilyCreate(BaseModel):
    code: str
    title: str
    description: str | None = None
    category: str | None = None
    default_agency: str | None = None


class TemplateCreate(BaseModel):
    family_id: int | None = None
    family_code: str | None = None
    agency: str
    system: str | None = None
    code: str
    title: str
    description: str | None = None
    fields: list[dict[str, Any]] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_by: str | None = None


class TemplateVersionCreate(BaseModel):
    fields: list[dict[str, Any]] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    version_label: str | None = None
    effective_date: str | None = None
    retired_date: str | None = None
    export_profiles: dict[str, Any] = Field(default_factory=dict)
    source_asset_path: str | None = None
    checksum: str | None = None
    change_summary: str | None = None
    created_by: str | None = None


class InstanceCreate(BaseModel):
    incident_id: str
    template_id: int | None = None
    template_version_id: int | None = None
    operational_period_id: str | None = None
    linked_module: str | None = None
    linked_record_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    binding_context: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None


class ValuesPatch(BaseModel):
    incident_id: str
    values: dict[str, Any]
    user_id: str | None = None


class RefreshRequest(BaseModel):
    incident_id: str
    context: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None


class InstanceAction(BaseModel):
    incident_id: str
    user_id: str | None = None
    reason: str | None = None


class ExportRequest(BaseModel):
    incident_id: str
    export_type: str = "pdf"
    output_path: str | None = None
    user_id: str | None = None


class UploadRequest(BaseModel):
    source_path: str
    family_id: int | None = None
    family_code: str | None = None
    agency: str
    system: str | None = None
    code: str
    title: str
    category: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidateRequest(BaseModel):
    fields: list[dict[str, Any]] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
