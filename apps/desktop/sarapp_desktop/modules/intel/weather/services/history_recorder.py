"""Appends each successful poll's reading to the weather_history collection.

NWS provides no historical-observation endpoint, so this is the only source
of data for the History trend chart — samples accumulate from whenever a
location starts being polled, with no retroactive backfill.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from . import weather_repository_client as client

LOGGER = logging.getLogger(__name__)

_CANONICAL_FIELDS = (
    "temperature_f",
    "wind_speed_kt",
    "wind_gust_kt",
    "wind_direction_deg",
    "visibility_sm",
    "ceiling_ft",
    "relative_humidity_pct",
    "barometric_pressure_hpa",
)


def record(incident_id: str, location_id: str, normalized_reading: Dict[str, Any]) -> None:
    """Record one history sample for a location from an already-normalized reading.

    `normalized_reading` must already use canonical units (see
    weather_manager._normalize_metar_reading) — this module does no unit
    conversion itself, it just shapes and forwards the sample.
    """
    if not normalized_reading:
        return
    sample = {field: normalized_reading.get(field) for field in _CANONICAL_FIELDS}
    sample["location_id"] = location_id
    sample["source"] = "metar"
    try:
        client.record_history(incident_id, sample)
    except Exception:
        LOGGER.exception("Failed to record weather history sample for location %s", location_id)


__all__ = ["record"]
