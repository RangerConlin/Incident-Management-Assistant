"""Stub lightning provider.

Provides a contract-compatible placeholder that generates simulated strikes
to facilitate testing and UI rendering.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import List

from .base import LightningProvider
from ..models.lightning import LightningStrike

LOGGER = logging.getLogger(__name__)


class LightningStub(LightningProvider):
    """Placeholder lightning provider that returns simulated lightning strikes."""

    def fetch_recent_strikes(
        self, latitude: float, longitude: float, radius_nm: float
    ) -> List[LightningStrike]:
        LOGGER.info(
            "Lightning stub generating simulated strikes for lat=%s lon=%s radius=%s",
            latitude,
            longitude,
            radius_nm,
        )
        strikes: List[LightningStrike] = []
        # Generate 2 to 4 random strikes
        num_strikes = random.randint(2, 4)
        for _ in range(num_strikes):
            # 1 degree of latitude is roughly 60 nm
            lat_offset = random.uniform(-radius_nm / 60.0, radius_nm / 60.0)
            # Adjust longitude offset based on latitude
            lon_offset = random.uniform(-radius_nm / 60.0, radius_nm / 60.0)
            
            strikes.append(
                LightningStrike(
                    timestamp=datetime.now(timezone.utc),
                    latitude=latitude + lat_offset,
                    longitude=longitude + lon_offset,
                    amplitude=random.uniform(-80.0, 80.0),
                )
            )
        return strikes


__all__ = ["LightningStub"]
