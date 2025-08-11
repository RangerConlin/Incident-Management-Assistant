"""FTS5 utilities for the reference library."""

from __future__ import annotations

from typing import List

from sqlalchemy import Text, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def ensure_fts(engine: Engine) -> None:
    """Ensure the FTS5 table exists."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                USING fts5(id UNINDEXED, title, text)
                """
            )
        )


def index_document(session: Session, doc_id: int, title: str, content: str) -> None:
    """Insert or replace a document's text into the FTS table."""
    session.execute(
        text(
            """
            INSERT INTO documents_fts(rowid, id, title, text)
            VALUES (:rowid, :id, :title, :text)
            ON CONFLICT(rowid) DO UPDATE SET title=:title, text=:text
            """
        ),
        {"rowid": doc_id, "id": doc_id, "title": title, "text": content},
    )


def search_documents(session: Session, query: str, limit: int = 50) -> List[dict]:
    """Run a keyword search against the FTS index."""
    result = session.execute(
        text(
            """
            SELECT id, title, snippet(documents_fts, 2, '<b>', '</b>', '...', 10) AS snippet,
                   rank
            FROM documents_fts, fts5_rank(documents_fts) AS rank
            WHERE documents_fts MATCH :q
            ORDER BY rank
            LIMIT :limit
            """
        ),
        {"q": query, "limit": limit},
    )
    return [dict(r._mapping) for r in result]
