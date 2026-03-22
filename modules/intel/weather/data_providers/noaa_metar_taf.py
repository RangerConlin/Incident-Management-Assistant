"""NOAA aviation weather adapters.

The classes defined here implement the provider interfaces for METAR and TAF data.
Real network interaction should be performed using the requests library or
``httpx`` in worker threads. The current implementation provides a non-blocking
skeleton that returns empty data structures when offline.
"""

from __future__ import annotations

import logging
from typing import Iterable, List

from .base import MetarProvider, TafProvider
from ..models.readings import MetarReading, TafReading

LOGGER = logging.getLogger(__name__)


class NoaaMetarProvider(MetarProvider):
    """Fetches METAR observations from the NOAA ADDS service."""

    def fetch_metar(self, icao_codes: Iterable[str]) -> List[MetarReading]:
        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            LOGGER.debug("No ICAO codes supplied for METAR fetch.")
            return []
        LOGGER.info("METAR fetch requested for %s", ", ".join(codes))
        # NOTE: Real implementation must perform HTTP requests and parsing.
        return []


class NoaaTafProvider(TafProvider):
    """Fetches TAF bulletins from the NOAA ADDS service."""

    def fetch_taf(self, icao_codes: Iterable[str]) -> List[TafReading]:
        codes = list({code.strip().upper() for code in icao_codes if code})
        if not codes:
            LOGGER.debug("No ICAO codes supplied for TAF fetch.")
            return []
        LOGGER.info("TAF fetch requested for %s", ", ".join(codes))
        # NOTE: Real implementation must perform HTTP requests and parsing.
        return []


__all__ = ["NoaaMetarProvider", "NoaaTafProvider"]
