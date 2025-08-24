"""Business logic for communications module."""

from typing import Iterable
from sqlmodel import Session, select

from .repository import get_master_engine
from .models.schemas import ChannelCreate, ChannelRead
from .models.comms_models import Channel


def list_channels() -> list[ChannelRead]:
    engine = get_master_engine()
    with Session(engine) as session:
        channels = session.exec(select(Channel)).all()
        return [ChannelRead.model_validate(channel) for channel in channels]


def add_channel(data: ChannelCreate) -> ChannelRead:
    engine = get_master_engine()
    channel = Channel.model_validate(data)
    with Session(engine) as session:
        session.add(channel)
        session.commit()
        session.refresh(channel)
    return ChannelRead.model_validate(channel)


def import_channels(channels: Iterable[ChannelCreate]) -> int:
    """Bulk-import channels into the master library."""
    engine = get_master_engine()
    count = 0
    with Session(engine) as session:
        for ch in channels:
            session.add(Channel.model_validate(ch))
            count += 1
        session.commit()
    return count
