"""Datamodel definitions for the CAP ORM module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

RiskLevel = str


@dataclass(slots=True)
class ORMForm:
    id: int
    incident_id: int
    op_period: int
    activity: Optional[str]
    prepared_by_id: Optional[int]
    date_iso: Optional[str]
    highest_residual_risk: RiskLevel
    status: str
    approval_blocked: bool


@dataclass(slots=True)
class ORMHazard:
    id: int
    form_id: int
    sub_activity: str
    hazard_outcome: str
    initial_risk: RiskLevel
    control_text: str
    residual_risk: RiskLevel
    implement_how: Optional[str]
    implement_who: Optional[str]
