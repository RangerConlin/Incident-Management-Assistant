"""Weather reading data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(slots=True)
class MetarReading:
    """Represents a METAR observation."""

    station: str
    issued: Optional[datetime] = None
    raw_text: str = ""
    decoded: Optional[dict] = None


@dataclass(slots=True)
class TafForecastLine:
    """Represents a single line of a decoded TAF forecast."""

    period: str
    summary: str


@dataclass(slots=True)
class TafReading:
    """Represents a TAF bulletin."""

    station: str
    issued: Optional[datetime] = None
    raw_text: str = ""
    decoded_lines: List[TafForecastLine] = field(default_factory=list)


@dataclass(slots=True)
class ForecastPeriod:
    """Represents a forecast period."""

    name: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    temperature: Optional[float] = None
    wind_speed: Optional[str] = None
    detailed_text: Optional[str] = None


__all__ = [
    "MetarReading",
    "TafForecastLine",
    "TafReading",
    "ForecastPeriod",
]
