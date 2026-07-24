"""Runway crosswind computation.

METAR/TAF only report wind direction and speed, not runway heading, so
crosswind can't be derived from weather data alone. Runway headings come
from `runway_api.py` (a live NOAA AWC lookup performed once, at
station-creation time, and cached on the WeatherLocation) — this module
takes that cached `runway_ends` list directly and never fetches anything
itself. If a station has no runway data (lookup failed, no key/network, or
the airport wasn't found), callers simply omit the crosswind readout rather
than guessing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from ..models.location import RunwayEnd


@dataclass(slots=True)
class CrosswindResult:
    runway: RunwayEnd
    crosswind_kt: float
    headwind_kt: float


def compute_crosswind(wind_dir_deg: float, wind_speed_kt: float, runway_heading_deg: float) -> tuple[float, float]:
    """Return (crosswind_kt, headwind_kt) for one runway heading.

    Positive headwind = wind blowing down the runway toward the aircraft
    (favorable); negative = tailwind. Crosswind is always reported as a
    magnitude (direction of the crosswind component isn't meaningful without
    a chosen runway end to reference).
    """
    angle_rad = math.radians(wind_dir_deg - runway_heading_deg)
    crosswind = abs(wind_speed_kt * math.sin(angle_rad))
    headwind = wind_speed_kt * math.cos(angle_rad)
    return crosswind, headwind


def best_runway_crosswind(
    runway_ends: List[RunwayEnd], wind_dir_deg: Optional[float], wind_speed_kt: Optional[float]
) -> Optional[CrosswindResult]:
    """Return the lowest-crosswind runway for this station's current wind, or None.

    Returns None (never a guess) when the station has no cached runway data,
    or when wind direction/speed aren't available yet.
    """
    if wind_dir_deg is None or wind_speed_kt is None or not runway_ends:
        return None
    best: Optional[CrosswindResult] = None
    for runway in runway_ends:
        crosswind, headwind = compute_crosswind(wind_dir_deg, wind_speed_kt, runway.heading_true_deg)
        if best is None or crosswind < best.crosswind_kt:
            best = CrosswindResult(runway=runway, crosswind_kt=crosswind, headwind_kt=headwind)
    return best


def all_runway_crosswinds(
    runway_ends: List[RunwayEnd], wind_dir_deg: Optional[float], wind_speed_kt: Optional[float]
) -> List[CrosswindResult]:
    """Return crosswind/headwind for every published runway, sorted best-first."""
    if wind_dir_deg is None or wind_speed_kt is None or not runway_ends:
        return []
    results = []
    for runway in runway_ends:
        crosswind, headwind = compute_crosswind(wind_dir_deg, wind_speed_kt, runway.heading_true_deg)
        results.append(CrosswindResult(runway=runway, crosswind_kt=crosswind, headwind_kt=headwind))
    results.sort(key=lambda r: r.crosswind_kt)
    return results


__all__ = ["CrosswindResult", "compute_crosswind", "best_runway_crosswind", "all_runway_crosswinds"]
