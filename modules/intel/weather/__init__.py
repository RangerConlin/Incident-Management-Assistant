"""Weather module package initialization.

This package provides the Weather Safety tooling for the Incident Management Assistant.
The module exposes UI components under :mod:`modules.intel.weather.windows` and helper
services under :mod:`modules.intel.weather.services`.
"""

from __future__ import annotations

from .services.api_link import WeatherApiManager

__all__ = ["WeatherApiManager"]
