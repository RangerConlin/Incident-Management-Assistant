from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typing import Any, Optional
from pydantic import Field


class HastyTaskCreate(BaseModel):
    area: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    create_task: bool = True
    request_logistics: bool = False


class HastyTaskRead(BaseModel):
    id: int
    area: str
    priority: Optional[str] = None
    notes: Optional[str] = None
    operations_task_id: Optional[int] = None
    logistics_request_id: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReflexActionCreate(BaseModel):
    trigger: str
    action: Optional[str] = None
    notify: bool = True


class ReflexActionRead(BaseModel):
    id: int
    trigger: str
    action: Optional[str] = None
    communications_alert_id: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InitialOverviewRead(BaseModel):
    incident_id: str
    incident_mode: str = "Missing Person"
    behavior_category: str = ""
    source_info: dict[str, Any] = Field(default_factory=dict)
    subject_info: dict[str, Any] = Field(default_factory=dict)
    aircraft_info: dict[str, Any] = Field(default_factory=dict)
    timeline_info: dict[str, Any] = Field(default_factory=dict)
    primary_anchor: dict[str, Any] = Field(default_factory=dict)
    related_locations: list[dict[str, Any]] = Field(default_factory=list)
    clues_environment: dict[str, Any] = Field(default_factory=dict)
    operations_summary: dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InitialOverviewUpdate(BaseModel):
    incident_mode: str = "Missing Person"
    behavior_category: str = ""
    source_info: dict[str, Any] = Field(default_factory=dict)
    subject_info: dict[str, Any] = Field(default_factory=dict)
    aircraft_info: dict[str, Any] = Field(default_factory=dict)
    timeline_info: dict[str, Any] = Field(default_factory=dict)
    primary_anchor: dict[str, Any] = Field(default_factory=dict)
    related_locations: list[dict[str, Any]] = Field(default_factory=list)
    clues_environment: dict[str, Any] = Field(default_factory=dict)
    operations_summary: dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""
