"""Field validation helpers for intel data."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..models import Clue, Subject, EnvSnapshot, IntelReport


class ValidationError(Exception):
    """Raised when validation fails."""


REQUIRED_CLUE_FIELDS: Iterable[str] = [
    "type",
    "score",
    "at_time",
    "location_text",
    "entered_by",
]


def validate_clue(clue: Clue) -> None:
    """Validate that ``clue`` has all required fields."""
    for field in REQUIRED_CLUE_FIELDS:
        if getattr(clue, field) in (None, ""):
            raise ValidationError(f"Clue field '{field}' is required")
    if not isinstance(clue.at_time, datetime):
        raise ValidationError("'at_time' must be a datetime instance")


def validate_subject(subject: Subject) -> None:
    """Validate minimal requirements for a subject profile."""
    if not (subject.name and subject.name.strip()):
        raise ValidationError("Subject field 'name' is required")


def validate_env_snapshot(s: EnvSnapshot) -> None:
    """Validate environmental snapshot requirements."""
    if s.op_period is None:
        raise ValidationError("Environment field 'op_period' is required")
    try:
        val = int(s.op_period)
    except Exception:
        raise ValidationError("'op_period' must be an integer")
    if val <= 0:
        raise ValidationError("'op_period' must be a positive integer")


def validate_report(r: IntelReport) -> None:
    """Validate intel report minimal fields."""
    if not (r.title and r.title.strip()):
        raise ValidationError("Report field 'title' is required")
