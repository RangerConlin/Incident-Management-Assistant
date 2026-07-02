"""Schema for team documents (sarapp_master.teams)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from sarapp_db.schemas.common import TimestampedDocument


class TeamDocument(TimestampedDocument):
    """A response team in the master roster."""

    team_id: str  # Stable identifier; indexed
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
