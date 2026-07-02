"""Schema for personnel documents (sarapp_master.personnel)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from sarapp_db.schemas.common import TimestampedDocument


class PersonnelCertification(BaseModel):
    """Embedded certification record stored directly on a personnel document.

    Keep this intentionally small. Catalog display data and medic-checkoff flags
    live on the certification catalog entry.
    """

    cert_type_id: int
    level: int = 0  # 0=None, 1=Trainee, 2=Qualified, 3=Evaluator


class PersonnelDocument(TimestampedDocument):
    """A responder or staff member in the agency master roster."""

    person_record: int  # Auto-assigned internal integer key; unique index; never shown to users
    person_id: str = ""  # User-entered visible ID (badge number, employee number, etc.)
    first_name: str = ""
    last_name: str = ""
    display_name: Optional[str] = None
    organization: Optional[str] = None
    agency: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    radio_id: Optional[str] = None
    status: str = "available"  # available | deployed | unavailable | inactive

    # Person-owned certifications. Each entry stores only the catalog type and
    # the person's current level. All other cert details come from the catalog.
    certifications: List[PersonnelCertification] = Field(default_factory=list)

    notes: Optional[str] = None
