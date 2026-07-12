"""Schema for team documents (sarapp_incident_<id>.teams)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from sarapp_db.schemas.common import TimestampedDocument


class TeamDocument(TimestampedDocument):
    """A response team assigned within an incident."""

    int_id: int  # Stable identifier; indexed (see team-id/int_id consolidation notes)
    name: str
    team_type: Optional[str] = None  # Ground | K9 | Dive | Technical | etc.
    status: str = "available"  # available | deployed | unavailable | inactive
    ci_status: str = "Available"  # Available | Checked In | Pending | Enroute | etc.
    member_person_records: List[int] = Field(default_factory=list)
    leader_person_record: Optional[int] = None
    agency: Optional[str] = None
    radio_channel: Optional[str] = None
    vehicle_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    # Team-location tracking (GIS module Phase 1) — last-known position only,
    # no breadcrumb trail. Written by data/db/sarapp_db/api/routers/mobile_location.py,
    # gated by a leader-preference check; see tracking_plan.md in ICS-Mobile-App.
    current_location_lat: Optional[float] = None
    current_location_lon: Optional[float] = None
    current_location_updated_at: Optional[str] = None
    current_location_person_record: Optional[int] = None
