"""Weather location/station and snapshot data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .advisory import Advisory
from .readings import ForecastPeriod, MetarReading, TafReading


@dataclass(slots=True)
class RunwayEnd:
    """One runway end, as returned by the live runway-data API at station-creation time."""

    designator: str
    heading_true_deg: float
    length_ft: Optional[float] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "RunwayEnd":
        return cls(
            designator=str(data.get("designator") or ""),
            heading_true_deg=float(data.get("heading_true_deg") or 0.0),
            length_ft=data.get("length_ft"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "designator": self.designator,
            "heading_true_deg": self.heading_true_deg,
            "length_ft": self.length_ft,
        }


@dataclass(slots=True)
class WeatherLocation:
    """A station/location tracked by the weather module for one incident."""

    location_id: str
    label: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    icao_codes: List[str] = field(default_factory=list)
    is_default: bool = False
    source: str = "manual"  # "manual" | "initial_response" | "facility"
    source_ref_id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    # Fetched once from the live runway-data API when the station is created
    # (see services/runway_api.py) and cached here — never re-queried per
    # crosswind computation. Empty if the API had no data, no key was
    # configured, or the lookup failed; the Aviation tab omits the crosswind
    # readout in that case rather than guessing.
    runway_ends: List["RunwayEnd"] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "WeatherLocation":
        return cls(
            location_id=str(data.get("location_id") or ""),
            label=str(data.get("label") or ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            icao_codes=list(data.get("icao_codes") or []),
            is_default=bool(data.get("is_default") or False),
            source=str(data.get("source") or "manual"),
            source_ref_id=data.get("source_ref_id"),
            created_at=data.get("created_at"),
            created_by=data.get("created_by"),
            runway_ends=[RunwayEnd.from_api(r) for r in (data.get("runway_ends") or []) if isinstance(r, dict)],
        )


@dataclass(slots=True)
class WeatherSnapshot:
    """Everything currently known for one location: current + forecast + aviation."""

    location_id: str
    metar: Optional[MetarReading] = None
    taf: Optional[TafReading] = None
    forecast: List[ForecastPeriod] = field(default_factory=list)
    advisories: List[Advisory] = field(default_factory=list)
    hwo_text: Optional[str] = None
    updated_at: Optional[str] = None


__all__ = ["RunwayEnd", "WeatherLocation", "WeatherSnapshot"]
