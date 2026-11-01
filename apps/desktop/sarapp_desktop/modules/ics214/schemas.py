"""Client models for the canonical ICS-214 activity stream."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Associations(BaseModel):
    person_ids: list[int] = Field(default_factory=list)
    team_ids: list[int] = Field(default_factory=list)
    task_ids: list[int] = Field(default_factory=list)
    org_unit_ids: list[int] = Field(default_factory=list)
    facility_ids: list[int] = Field(default_factory=list)
    resource_ids: list[int] = Field(default_factory=list)
    external_agency_ids: list[int] = Field(default_factory=list)


class SourceRecord(BaseModel):
    collection: str
    record_id: str


class EntryCreate(Associations):
    text: str
    occurred_at: datetime | None = None
    critical_flag: bool = False
    incident_wide: bool = False
    source: str = "manual"
    created_by: str | None = None
    source_record: SourceRecord | None = None
    expand_team_members: bool = False
    idempotency_hash: str | None = None

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class EntryFilter(Associations):
    operational_period_id: int | None = None
    incident_wide: bool | None = None
    unassigned: bool = False
    include_voided: bool = False
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    sources: list[str] = Field(default_factory=list)
    critical_only: bool = False


class VoidRequest(BaseModel):
    voided_by: str
    reason: str


class CorrectionCreate(EntryCreate):
    voided_by: str
    void_reason: str


class LogDefinitionCreate(BaseModel):
    name: str
    filters: EntryFilter
    unit_name: str = ""
    prepared_by_position: str = ""


class LogDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[EntryFilter] = None
    unit_name: Optional[str] = None
    prepared_by_position: Optional[str] = None


class ExportRequest(BaseModel):
    filters: EntryFilter = Field(default_factory=EntryFilter)
    unit_name: str = "Incident"
    include_auto: bool = True
    include_attachments: bool = False
