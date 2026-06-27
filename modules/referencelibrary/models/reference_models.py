"""Data models for the Reference Library.

Persistence is API-backed (`modules/referencelibrary/api/public_api.py` calls
`utils.api_client` against `data/db/sarapp_db/api/routers/reference_library.py`,
MongoDB-backed). The SQLAlchemy ORM models and FTS5 search helpers that used
to live here were removed during migration — they had zero callers anywhere
in the app; `public_api.search_references` hits the Mongo-backed `search`
query param on the documents endpoint instead.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Metadata:
    size: int
    extension: str
