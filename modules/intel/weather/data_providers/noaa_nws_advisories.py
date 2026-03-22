"""NOAA NWS advisories data provider."""

from __future__ import annotations

import logging
from typing import List

from .base import AdvisoryProvider
from ..models.advisory import Advisory

LOGGER = logging.getLogger(__name__)


class NoaaNwsAdvisoryProvider(AdvisoryProvider):
    """Fetches weather advisories for a location from the NWS API."""

    def fetch_advisories(self, latitude: float, longitude: float) -> List[Advisory]:
        LOGGER.info(
            "Advisory fetch requested for lat=%s lon=%s", latitude, longitude
        )
        # NOTE: Real implementation pending API integration.
        return []


__all__ = ["NoaaNwsAdvisoryProvider"]
