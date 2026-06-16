"""Schema for personnel documents (sarapp_master.personnel)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from sarapp_db.schemas.common import TimestampedDocument


class PersonnelDocument(TimestampedDocument):
    """A responder or staff member in the agency master roster."""

    personnel_id: str  # Stable agency-assigned identifier; indexed
    first_name: str
    last_name: str
    display_name: Optional[str] = None
    organization: Optional[str] = None
    agency: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    radio_id: Optional[str] = None
    status: str = "available"  # available | deployed | unavailable | inactive
    certification_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
