"""Shared field definitions for SARApp MongoDB document schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid4())


class TimestampedDocument(BaseModel):
    """
    Mixin providing standard timestamp and soft-delete fields.

    All SARApp MongoDB documents should include these fields so the
    repository layer can handle updated_at and soft_delete uniformly.
    """

    id: str = Field(default_factory=new_id, alias="_id")
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    deleted: bool = False

    model_config = {"populate_by_name": True}
