"""Business logic for the reference library."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from .models import (
    AuditEntry,
    Collection,
    CollectionDocument,
    Document,
    ExternalLink,
    IncidentDocument,
)
from .models.schemas import (
    CollectionCreate,
    CollectionRead,
    DocumentCreate,
    DocumentRead,
    DocumentUpdate,
    ExternalLinkCreate,
    ExternalLinkRead,
    IncidentDocumentCreate,
    IncidentDocumentRead,
    SearchQuery,
    SearchResult,
    ToggleCacheRequest,
    ToggleCacheResponse,
)
from .repository import ROOT_DIR, with_master_session, with_incident_session
from .search_index import index_document, search_documents

FILES_ROOT = ROOT_DIR / "data" / "library" / "files"
CACHE_ROOT = ROOT_DIR / "data" / "incidents"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _extract_text(path: Path, limit: int = 4000) -> str:
    """Very small stub text extractor."""
    try:
        with path.open("rb") as f:
            data = f.read(limit)
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _log_audit(session: Session, event: dict) -> None:
    session.add(AuditEntry(event=json.dumps(event)))


# ---------------------------------------------------------------------------
# Document services
# ---------------------------------------------------------------------------


def list_documents() -> List[DocumentRead]:
    with with_master_session() as session:
        docs = session.query(Document).all()
        return [DocumentRead.from_orm(d) for d in docs]


def _store_file(upload: UploadFile, doc_id: int) -> Path:
    dest_dir = FILES_ROOT / str(doc_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / upload.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def create_document(upload: UploadFile, data: DocumentCreate) -> DocumentRead:
    with with_master_session() as session:
        doc = Document(
            title=data.title,
            filename=data.filename,
            mime_type=data.mime_type,
            size_bytes=data.size_bytes,
            checksum=data.checksum,
            tags_json=json.dumps(data.tags),
            agency=data.agency,
            category=data.category,
            access_level=data.access_level,
        )
        session.add(doc)
        session.flush()  # assign id
        path = _store_file(upload, doc.id)
        text = _extract_text(path)
        doc.size_bytes = path.stat().st_size
        doc.extracted_text = text
        index_document(session, doc.id, doc.title, text)
        _log_audit(session, {"action": "upload", "document_id": doc.id})
        return DocumentRead.from_orm(doc)


def get_document(doc_id: int) -> Optional[DocumentRead]:
    with with_master_session() as session:
        doc = session.get(Document, doc_id)
        if not doc:
            return None
        return DocumentRead.from_orm(doc)


def update_document(doc_id: int, data: DocumentUpdate) -> Optional[DocumentRead]:
    with with_master_session() as session:
        doc = session.get(Document, doc_id)
        if not doc:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "tags" and value is not None:
                setattr(doc, "tags_json", json.dumps(value))
            else:
                setattr(doc, field, value)
        doc.version += 1
        index_document(session, doc.id, doc.title, doc.extracted_text or "")
        _log_audit(session, {"action": "update", "document_id": doc.id})
        return DocumentRead.from_orm(doc)


def toggle_cache(doc_id: int, req: ToggleCacheRequest) -> ToggleCacheResponse:
    with with_master_session() as session:
        doc = session.get(Document, doc_id)
        if not doc:
            raise ValueError("Document not found")
        src = FILES_ROOT / str(doc.id) / doc.filename
        cache_dir = CACHE_ROOT / req.incident_id / "cache" / "library" / str(doc.id)
        cache_file = cache_dir / doc.filename
        if req.enable:
            cache_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, cache_file)
            doc.is_offline_cached = 1
        else:
            if cache_file.exists():
                cache_file.unlink()
            doc.is_offline_cached = 0
        _log_audit(
            session,
            {
                "action": "cache_toggle",
                "document_id": doc.id,
                "incident_id": req.incident_id,
                "enabled": req.enable,
            },
        )
    return ToggleCacheResponse(
        document_id=doc_id, incident_id=req.incident_id, enabled=req.enable
    )


def attach_to_incident(data: IncidentDocumentCreate) -> IncidentDocumentRead:
    with with_master_session() as session:
        entry = IncidentDocument(
            incident_id=data.incident_id,
            document_id=data.document_id,
            note=data.note,
        )
        session.add(entry)
        session.flush()
        _log_audit(
            session,
            {
                "action": "attach_incident",
                "document_id": data.document_id,
                "incident_id": data.incident_id,
            },
        )
        return IncidentDocumentRead.from_orm(entry)


# ---------------------------------------------------------------------------
# Collection services
# ---------------------------------------------------------------------------


def create_collection(data: CollectionCreate) -> CollectionRead:
    with with_master_session() as session:
        col = Collection(name=data.name, description=data.description)
        session.add(col)
        session.flush()
        _log_audit(session, {"action": "create_collection", "collection_id": col.id})
        return CollectionRead.from_orm(col)


def list_collections() -> List[CollectionRead]:
    with with_master_session() as session:
        cols = session.query(Collection).all()
        return [CollectionRead.from_orm(c) for c in cols]


def add_document_to_collection(collection_id: int, document_id: int) -> None:
    with with_master_session() as session:
        assoc = CollectionDocument(
            collection_id=collection_id, document_id=document_id
        )
        session.merge(assoc)
        _log_audit(
            session,
            {
                "action": "add_to_collection",
                "collection_id": collection_id,
                "document_id": document_id,
            },
        )


# ---------------------------------------------------------------------------
# External links
# ---------------------------------------------------------------------------


def create_external_link(data: ExternalLinkCreate) -> ExternalLinkRead:
    with with_master_session() as session:
        link = ExternalLink(
            title=data.title,
            url=data.url,
            description=data.description,
            tags_json=json.dumps(data.tags),
        )
        session.add(link)
        session.flush()
        _log_audit(session, {"action": "add_link", "link_id": link.id})
        return ExternalLinkRead.from_orm(link)


def list_external_links() -> List[ExternalLinkRead]:
    with with_master_session() as session:
        links = session.query(ExternalLink).all()
        return [ExternalLinkRead.from_orm(l) for l in links]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search(data: SearchQuery) -> List[SearchResult]:
    with with_master_session() as session:
        rows = search_documents(session, data.q, limit=data.limit)
        return [SearchResult(**r) for r in rows]
