"""Schema for personnel documents (sarapp_master.personnel)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from sarapp_db.schemas.common import TimestampedDocument


class PersonnelCertification(BaseModel):
    """Embedded certification record stored directly on a personnel document."""

    id: Optional[int] = None
    cert_type_id: Optional[int] = None
    code: str = ""
    name: str = ""
    category: str = ""
    issuing_org: str = ""
    parent_id: Optional[int] = None
    tags: List[str] = Field(default_factory=list)

    # 0=None, 1=Trainee, 2=Qualified, 3=Evaluator
    level: int = 0

    issue_date: str = ""
    expiration: str = ""
    expiration_date: str = ""
    docs: str = ""
    attachment_url: str = ""

    verification_status: str = ""
    verified_by: str = ""
    verified_at: str = ""
    source: str = "manual"
    notes: str = ""
    updated_at: str = ""


class PersonnelDocument(TimestampedDocument):
    """A responder or staff member in the agency master roster."""

    personnel_id: str  # Stable agency-assigned identifier; indexed
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

    # Certification data is intentionally embedded here instead of stored as a
    # separate relationship collection. The catalog remains a lookup source for
    # cert definitions; the person's current qualification record lives with the
    # person.
    certifications: List[PersonnelCertification] = Field(default_factory=list)

    # Deprecated legacy field retained for older records/imports.
    certification_ids: List[str] = Field(default_factory=list)

    notes: Optional[str] = None
