"""Weather advisory data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(slots=True)
class Advisory:
    """Represents a single weather advisory or warning."""

    event: str
    severity: Optional[str]
    start: Optional[datetime]
    end: Optional[datetime]
    headline: Optional[str]
    description: Optional[str]
    certainty: Optional[str] = None
    urgency: Optional[str] = None
    affected_areas: Optional[List[str]] = None


__all__ = ["Advisory"]
