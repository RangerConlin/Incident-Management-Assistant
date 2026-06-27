"""Recursively make a Mongo document safe to hand to a JSON encoder.

Collections that predate BaseRepository (or that were never migrated at
all) can contain BSON types a plain JSON encoder — or FastAPI/Pydantic's —
doesn't know how to serialize: `ObjectId` (Mongo's auto-generated `_id` for
any document that was never given an explicit one) and raw `datetime`
values (for code that stored a Python datetime directly instead of an ISO
string). Both the cache snapshot endpoint and the WebSocket broadcast path
need documents to survive `json.dumps`/Pydantic serialization regardless of
which collection or how old the data is, so this walks the whole structure
rather than special-casing just `_id`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from bson import ObjectId


def json_safe(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


__all__ = ["json_safe"]
