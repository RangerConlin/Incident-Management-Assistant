"""Schema for the incident profile document (sarapp_incident_<id>.incident_profile)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from sarapp_db.schemas.common import TimestampedDocument


class IncidentProfileDocument(TimestampedDocument):
    """Top-level incident profile. One document per incident database."""

    incident_id: str
    name: str
    incident_number: Optional[str] = None
    incident_type: Optional[str] = None
    location_description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    incident_commander: Optional[str] = None
    agency: Optional[str] = None
    state: Optional[str] = None
    status: str = "active"  # active | closed | archived
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
