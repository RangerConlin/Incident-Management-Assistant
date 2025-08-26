"""SQLModel table definitions for communications."""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Channel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    rx_freq: float
    tx_freq: float
    mode: str  # analog or digital
    tone: str | None = None
    nac: str | None = None
    band: str | None = None
    call_sign: str | None = None
    usage: str | None = None
    encrypted: bool = False


class ChannelAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str
    team: str
    channel_id: int


class MessageLogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str
    timestamp: datetime
    sender: str
    recipient: str
    method: str
    message: str
