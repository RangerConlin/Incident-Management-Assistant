"""Stub lightning provider.

Provides a contract-compatible placeholder that returns no strikes. The module is
wired so that a real provider can be implemented without modifying the UI layers.
"""

from __future__ import annotations

import logging
from typing import List

from .base import LightningProvider
from ..models.lightning import LightningStrike

LOGGER = logging.getLogger(__name__)


class LightningStub(LightningProvider):
    """Placeholder lightning provider that returns no data."""

    def fetch_recent_strikes(
        self, latitude: float, longitude: float, radius_nm: float
    ) -> List[LightningStrike]:
        LOGGER.debug(
            "Lightning stub invoked for lat=%s lon=%s radius=%s", latitude, longitude, radius_nm
        )
        return []


__all__ = ["LightningStub"]
