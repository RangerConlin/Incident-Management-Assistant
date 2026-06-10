"""Station metadata models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Station:
    """Represents an aviation or point forecast station."""

    icao: str
    name: str
    latitude: float
    longitude: float
    elevation_ft: Optional[float] = None
    country: Optional[str] = None
    region: Optional[str] = None


__all__ = ["Station"]
