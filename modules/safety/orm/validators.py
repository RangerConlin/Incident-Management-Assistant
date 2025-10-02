"""Pydantic schemas for CAP ORM REST payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

RiskLevel = Literal["L", "M", "H", "EH"]


class FormQuery(BaseModel):
    incident_id: int
    op_period: int = Field(ge=1)


class FormUpdate(BaseModel):
    incident_id: int
    op_period: int = Field(ge=1)
    activity: Optional[str] = None
    prepared_by_id: Optional[int] = None
    date_iso: Optional[str] = None

    @field_validator("date_iso")
    @classmethod
    def validate_iso(cls, value: Optional[str]) -> Optional[str]:
        if value:
            datetime.fromisoformat(value)
        return value


class HazardCreate(BaseModel):
    incident_id: int
    op_period: int = Field(ge=1)
    sub_activity: str
    hazard_outcome: str
    initial_risk: RiskLevel
    control_text: str
    residual_risk: RiskLevel
    implement_how: Optional[str] = None
    implement_who: Optional[str] = None

    @field_validator("sub_activity", "hazard_outcome", "control_text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field is required")
        return value.strip()


class HazardUpdate(BaseModel):
    sub_activity: str
    hazard_outcome: str
    initial_risk: RiskLevel
    control_text: str
    residual_risk: RiskLevel
    implement_how: Optional[str] = None
    implement_who: Optional[str] = None

    @field_validator("sub_activity", "hazard_outcome", "control_text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field is required")
        return value.strip()


class ApproveRequest(BaseModel):
    incident_id: int
    op_period: int = Field(ge=1)


class HazardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    form_id: int
    sub_activity: str
    hazard_outcome: str
    initial_risk: RiskLevel
    control_text: str
    residual_risk: RiskLevel
    implement_how: Optional[str]
    implement_who: Optional[str]


class FormRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    op_period: int
    activity: Optional[str]
    prepared_by_id: Optional[int]
    date_iso: Optional[str]
    highest_residual_risk: RiskLevel
    status: Literal["draft", "pending_mitigation", "approved"]
    approval_blocked: bool
