from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MessageType(str, Enum):
    PressRelease = "PressRelease"
    Advisory = "Advisory"
    SituationUpdate = "SituationUpdate"


class Audience(str, Enum):
    Public = "Public"
    Agency = "Agency"
    Internal = "Internal"


class Status(str, Enum):
    Draft = "Draft"
    InReview = "InReview"
    Approved = "Approved"
    Published = "Published"
    Archived = "Archived"


@dataclass
class Message:
    id: Optional[int]
    incident_id: str
    title: str
    body: str
    type: MessageType
    audience: Audience
    status: Status
    tags: Optional[str] = None
    revision: int = 1
    created_by: int = 0
    approved_by: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    published_at: Optional[str] = None
