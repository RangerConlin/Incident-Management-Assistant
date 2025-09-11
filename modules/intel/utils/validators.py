"""Field validation helpers for intel data."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..models import Clue


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
