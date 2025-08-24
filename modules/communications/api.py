"""FastAPI router for communications module."""

from fastapi import APIRouter, HTTPException
from .models.schemas import ChannelCreate, ChannelRead
from . import services

router = APIRouter()


@router.get("/channels", response_model=list[ChannelRead])
def list_channels() -> list[ChannelRead]:
    """Return all channels from the master library."""
    return services.list_channels()


@router.post("/channels", response_model=ChannelRead)
def create_channel(channel: ChannelCreate) -> ChannelRead:
    """Insert a new channel into the master library."""
    try:
        return services.add_channel(channel)
    except ValueError as exc:  # pragma: no cover - simple example
        raise HTTPException(status_code=400, detail=str(exc))
