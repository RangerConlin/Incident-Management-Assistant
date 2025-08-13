from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .message import Audience, MessageType, Status


class MessageBase(BaseModel):
    title: str
    body: str
    type: MessageType
    audience: Audience
    tags: Optional[str] = None


class MessageCreate(MessageBase):
    created_by: int


class MessageUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    type: Optional[MessageType] = None
    audience: Optional[Audience] = None
    tags: Optional[str] = None


class MessageRead(MessageBase):
    id: int
    mission_id: str
    status: Status
    revision: int
    created_by: int
    approved_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class MessageHistory(BaseModel):
    id: int
    title: str
    type: MessageType
    audience: Audience
    published_at: datetime
    revision: int
    approved_by: Optional[int] = None


class MessageList(BaseModel):
    items: List[MessageRead]
    total: int = Field(default=0)
