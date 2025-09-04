"""Full text search helpers."""

from __future__ import annotations

from typing import Iterable, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.reference_models import Document


FTS_CREATE = text(
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS library_fts USING fts5(
        doc_id UNINDEXED,
        content
    )
    """
)


def ensure_fts(session: Session) -> None:
    session.execute(FTS_CREATE)


def update_fts(session: Session, doc: Document) -> None:
    ensure_fts(session)
    session.execute(
        text("INSERT INTO library_fts(rowid, doc_id, content) VALUES (:rowid, :doc_id, :content)"),
        {
            "rowid": doc.id,
            "doc_id": doc.id,
            "content": " ".join(
                filter(
                    None,
                    [
                        doc.title,
                        doc.category,
                        doc.subcategory,
                        doc.tags,
                        doc.agency,
                        doc.jurisdiction,
                        doc.description,
                    ],
                )
            ),
        },
    )


def search_documents(session: Session, query: str, filters: Optional[dict] = None):
    ensure_fts(session)
    base_sql = "SELECT doc_id FROM library_fts WHERE library_fts MATCH :q"
    params = {"q": query}
    rows = session.execute(text(base_sql), params).fetchall()
    ids = [r[0] for r in rows]
    q = session.query(Document).filter(Document.id.in_(ids))
    if filters:
        if cat := filters.get("category"):
            q = q.filter(Document.category == cat)
        if tags := filters.get("tags"):
            for tag in tags:
                q = q.filter(Document.tags.contains(tag))
    return q.all()
