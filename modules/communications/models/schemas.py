"""Pydantic models for communications API."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ChannelBase(BaseModel):
    name: str
    rx_freq: float
    tx_freq: float
    mode: str
    tone: str | None = None
    nac: str | None = None
    band: str | None = None
    call_sign: str | None = None
    usage: str | None = None
    encrypted: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChannelCreate(ChannelBase):
    pass


class ChannelRead(ChannelBase):
    id: int


class ChannelAssignment(BaseModel):
    incident_id: str
    team: str
    channel_id: int

    model_config = ConfigDict(from_attributes=True)


class MessageLogEntry(BaseModel):
    incident_id: str
    timestamp: datetime
    sender: str
    recipient: str
    method: str
    message: str

    model_config = ConfigDict(from_attributes=True)
