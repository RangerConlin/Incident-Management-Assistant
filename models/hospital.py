"""Domain model for hospital records stored in ``data/master.db``.

The schema for the ``hospitals`` table has evolved over time. Some
deployments only include a minimal contact record (name, phone, address),
while newer databases add detailed trauma and aviation metadata.  The
``Hospital`` dataclass represents the superset of fields observed in the
project so the service layer can gracefully adapt to whichever columns are
available at runtime.

Fields that are not present in a database schema are simply ignored by the
service layer.  This keeps the model forward-compatible without forcing new
columns onto existing installations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Hospital:
    """In-memory representation of a hospital catalog entry."""

    id: Optional[int] = None
    name: str = ""
    code: str = ""
    type: str = ""
    phone: str = ""
    phone_er: str = ""
    phone_switchboard: str = ""
    fax: str = ""
    email: str = ""
    contact: str = ""
    contact_name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    travel_time_min: Optional[int] = None
    helipad: Optional[bool] = None
    trauma_level: str = ""
    burn_center: Optional[bool] = None
    pediatric_capability: Optional[bool] = None
    bed_available: Optional[int] = None
    diversion_status: str = ""
    ambulance_radio_channel: str = ""
    notes: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_active: Optional[bool] = None


__all__ = ["Hospital"]

