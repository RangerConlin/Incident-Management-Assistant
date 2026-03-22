"""Lightning data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class LightningStrike:
    """Represents a detected lightning strike."""

    timestamp: datetime
    latitude: float
    longitude: float
    amplitude: Optional[float] = None


__all__ = ["LightningStrike"]
