"""Dataclass definitions for incident intelligence data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Clue:
    type: str
    score: int
    at_time: datetime
    location_text: str
    entered_by: str
    id: Optional[int] = None
    geom: Optional[str] = None
    team_text: Optional[str] = None
    description: Optional[str] = None
    attachments_json: Optional[str] = None
    linked_subject_id: Optional[int] = None
    linked_task_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Subject:
    name: str
    id: Optional[int] = None
    sex: Optional[str] = None
    dob: Optional[str] = None
    race: Optional[str] = None
    photo: Optional[str] = None
    lkp_time: Optional[datetime] = None
    lkp_place: Optional[str] = None


@dataclass
class EnvSnapshot:
    op_period: int
    id: Optional[int] = None
    weather_json: Optional[str] = None
    hazards_json: Optional[str] = None
    terrain_json: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class IntelReport:
    title: str
    body_md: str
    id: Optional[int] = None
    linked_subject_id: Optional[int] = None
    linked_task_id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class FormEntry:
    form_name: str
    data_json: str
    id: Optional[int] = None
