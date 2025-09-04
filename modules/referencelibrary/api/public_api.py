"""Public API for the Reference Library module."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from ..models.reference_models import (
    Base,
    Document,
    Collection,
    get_engine,
    get_session,
)
from ..services import storage, ingest, search


def add_reference(
    file_path: str | Path,
    *,
    title: str,
    category: str,
    tags: Optional[list[str]] = None,
    agency: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Document:
    """Add a reference document to the library."""
    file_path = Path(file_path)
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        dest_path, file_hash = storage.store_file(file_path)
        meta = ingest.extract_metadata(dest_path)
        doc = Document(
            title=title,
            category=category,
            tags=tags or [],
            agency=agency,
            jurisdiction=jurisdiction,
            description=description,
            file_path=str(dest_path),
            file_hash=file_hash,
            file_ext=meta.extension,
            file_size=meta.size,
            created_by=created_by,
        )
        session.add(doc)
        session.commit()
        search.update_fts(session, doc)
        return doc


def search_references(query: str, filters: Optional[dict] = None) -> list[Document]:
    """Search reference documents using full text search."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        return search.search_documents(session, query, filters)


def get_reference_by_id(doc_id: int) -> Optional[Document]:
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        return session.get(Document, doc_id)


def link_reference_to_collection(document_id: int, collection_id: int) -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        doc = session.get(Document, document_id)
        coll = session.get(Collection, collection_id)
        if not doc or not coll:
            raise ValueError("Invalid document or collection ID")
        coll.documents.append(doc)
        session.commit()


def list_collections() -> list[Collection]:
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        return session.query(Collection).all()
