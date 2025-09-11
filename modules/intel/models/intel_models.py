"""SQLModel table definitions for incident intelligence data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Clue(SQLModel, table=True):
    """Intel clue recorded during an incident."""

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str
    score: int = 0
    at_time: datetime
    location_text: str
    geom: str | None = None
    entered_by: str
    team_text: str | None = None
    description: str | None = None
    attachments_json: str | None = None
    linked_subject_id: int | None = Field(default=None, foreign_key="subject.id")
    linked_task_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Subject(SQLModel, table=True):
    """Subject profile information."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    sex: str | None = None
    dob: str | None = None
    race: str | None = None
    photo: str | None = None  # path to photo
    lkp_time: datetime | None = None
    lkp_place: str | None = None


class EnvSnapshot(SQLModel, table=True):
    """Environmental intel for an operational period."""

    id: Optional[int] = Field(default=None, primary_key=True)
    op_period: int
    weather_json: str | None = None
    hazards_json: str | None = None
    terrain_json: str | None = None
    notes: str | None = None


class IntelReport(SQLModel, table=True):
    """Intel report composed from clues and subjects."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    body_md: str
    linked_subject_id: int | None = Field(default=None, foreign_key="subject.id")
    linked_task_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FormEntry(SQLModel, table=True):
    """Generic storage for completed forms.

    The project supports numerous official SAR and CAP forms.  Rather than
    creating a dedicated table for each form during early development this
    table stores the serialised representation and a simple name identifier.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    form_name: str
    data_json: str
