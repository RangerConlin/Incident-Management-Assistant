from __future__ import annotations

from typing import List
from sqlalchemy import text

from .repository import with_event_session


def search(event_id: str, query: str) -> List[dict]:
    with with_event_session(event_id) as session:
        result = session.execute(
            text("SELECT rowid, snippet(attachment_fts) FROM attachment_fts WHERE attachment_fts MATCH :q"),
            {"q": query},
        )
        return [{"id": row[0], "snippet": row[1]} for row in result]
