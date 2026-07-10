"""Datamodel definitions for the Safety Risk Manager hazard register."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class SpeAssessment:
    severity: int
    probability: int
    exposure: int
    score: int
    band: str
    action: str


@dataclass(slots=True)
class HazardLinks:
    work_assignment_ids: list[int] = field(default_factory=list)
    task_ids: list[int] = field(default_factory=list)
    team_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Hazard:
    id: int
    incident_id: str
    title: str
    description: Optional[str]
    category: Optional[str]
    hazard_type_id: Optional[str]
    hazard_type_text: Optional[str]
    source: Optional[str]
    op_period_ids: list[int]
    location_text: Optional[str]
    links: HazardLinks
    control_measure: Optional[str]
    mitigation_text: Optional[str]
    ppe_text: Optional[str]
    safety_message: Optional[str]
    notes: Optional[str]
    spe_initial: Optional[SpeAssessment]
    spe_residual: Optional[SpeAssessment]
    created_at: Optional[str]
    updated_at: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
