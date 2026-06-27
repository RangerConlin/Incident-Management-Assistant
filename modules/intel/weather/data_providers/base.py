"""Abstract data provider interfaces for the weather module.

These interfaces define the contracts used by :class:`WeatherApiManager` for fetching
weather data. Concrete implementations live in sibling modules and should perform
network I/O off the main thread.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol

from ..models.advisory import Advisory
from ..models.readings import ForecastPeriod, MetarReading, TafReading
from ..models.lightning import LightningStrike

import httpx

_shared_client: httpx.Client | None = None


def get_shared_client() -> httpx.Client:
    """Return a shared httpx.Client instance to reuse connections."""
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.Client(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _shared_client


@dataclass(slots=True)
class ProviderResult:
    """Container describing the outcome of a provider fetch."""

    success: bool
    error: Optional[str] = None


class MetarProvider(ABC):
    """Interface for classes capable of retrieving METAR data."""

    @abstractmethod
    def fetch_metar(self, icao_codes: Iterable[str]) -> List[MetarReading]:
        """Fetch METAR data for the provided ICAO codes."""


class TafProvider(ABC):
    """Interface for retrieving TAF bulletins."""

    @abstractmethod
    def fetch_taf(self, icao_codes: Iterable[str]) -> List[TafReading]:
        """Fetch TAF bulletins for the provided ICAO codes."""


class ForecastProvider(ABC):
    """Interface for multi-day forecast data."""

    @abstractmethod
    def fetch_forecast(self, latitude: float, longitude: float) -> List[ForecastPeriod]:
        """Retrieve a forecast for the provided coordinates."""


class AdvisoryProvider(ABC):
    """Interface for National Weather Service alert products."""

    @abstractmethod
    def fetch_advisories(self, latitude: float, longitude: float) -> List[Advisory]:
        """Return a list of active advisories impacting the given point."""


class LightningProvider(Protocol):
    """Protocol describing a lightning data feed."""

    def fetch_recent_strikes(
        self, latitude: float, longitude: float, radius_nm: float
    ) -> List[LightningStrike]:
        """Return strikes within the radius in the last polling interval."""


__all__ = [
    "ProviderResult",
    "MetarProvider",
    "TafProvider",
    "ForecastProvider",
    "AdvisoryProvider",
    "LightningProvider",
    "get_shared_client",
]
