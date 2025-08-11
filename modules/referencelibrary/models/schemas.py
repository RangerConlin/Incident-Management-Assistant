"""Pydantic schemas for the reference library API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentBase(BaseModel):
    title: str
    agency: Optional[str] = None
    category: Optional[str] = None
    access_level: Optional[str] = None
    tags: List[str] = []


class DocumentCreate(DocumentBase):
    filename: str
    mime_type: str
    size_bytes: int
    checksum: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    agency: Optional[str] = None
    category: Optional[str] = None
    access_level: Optional[str] = None
    tags: Optional[List[str]] = None


class DocumentRead(DocumentBase):
    id: int
    filename: str
    mime_type: str
    size_bytes: int
    version: int
    created_at: datetime
    updated_at: datetime
    is_offline_cached: bool

    class Config:
        orm_mode = True


# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionRead(CollectionCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------------------------
# External link schemas
# ---------------------------------------------------------------------------


class ExternalLinkCreate(BaseModel):
    title: str
    url: str
    description: Optional[str] = None
    tags: List[str] = []


class ExternalLinkRead(ExternalLinkCreate):
    id: int
    added_by: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------------------------
# Mission documents and cache toggles
# ---------------------------------------------------------------------------


class MissionDocumentCreate(BaseModel):
    mission_id: str
    document_id: int
    note: Optional[str] = None


class MissionDocumentRead(MissionDocumentCreate):
    id: int
    added_by: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class ToggleCacheRequest(BaseModel):
    mission_id: str
    enable: bool = True


class ToggleCacheResponse(BaseModel):
    document_id: int
    mission_id: str
    enabled: bool


# ---------------------------------------------------------------------------
# Search schemas
# ---------------------------------------------------------------------------


class SearchQuery(BaseModel):
    q: str
    limit: int = 50


class SearchResult(BaseModel):
    id: int
    title: str
    snippet: Optional[str] = None

