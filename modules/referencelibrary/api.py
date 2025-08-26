"""FastAPI router for the reference library."""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

from modules.referencelibrary import services
from modules.referencelibrary.models.schemas import (
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

router = APIRouter()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.get("/documents", response_model=List[DocumentRead])
async def list_documents(q: Optional[str] = None) -> List[DocumentRead]:
    if q:
        return services.search(SearchQuery(q=q))
    return services.list_documents()


@router.post("/documents", response_model=DocumentRead)
async def upload_document(
    file: UploadFile = File(...), meta: str = Form(...)
) -> DocumentRead:
    data = DocumentCreate(**json.loads(meta))
    data.filename = file.filename
    data.mime_type = file.content_type or data.mime_type
    data.size_bytes = 0
    return services.create_document(file, data)


@router.get("/documents/{doc_id}", response_model=DocumentRead)
async def get_document(doc_id: int) -> DocumentRead:
    doc = services.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/documents/{doc_id}", response_model=DocumentRead)
async def update_document(doc_id: int, payload: DocumentUpdate) -> DocumentRead:
    doc = services.update_document(doc_id, payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/documents/{doc_id}/cache", response_model=ToggleCacheResponse)
async def toggle_cache(doc_id: int, payload: ToggleCacheRequest) -> ToggleCacheResponse:
    return services.toggle_cache(doc_id, payload)


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


@router.post("/collections", response_model=CollectionRead)
async def create_collection(payload: CollectionCreate) -> CollectionRead:
    return services.create_collection(payload)


@router.get("/collections", response_model=List[CollectionRead])
async def get_collections() -> List[CollectionRead]:
    return services.list_collections()


@router.post("/collections/{collection_id}/documents")
async def add_to_collection(collection_id: int, document_id: int = Body(..., embed=True)) -> None:
    services.add_document_to_collection(collection_id, document_id)


# ---------------------------------------------------------------------------
# External links
# ---------------------------------------------------------------------------


@router.post("/links", response_model=ExternalLinkRead)
async def create_link(payload: ExternalLinkCreate) -> ExternalLinkRead:
    return services.create_external_link(payload)


@router.get("/links", response_model=List[ExternalLinkRead])
async def list_links() -> List[ExternalLinkRead]:
    return services.list_external_links()


# ---------------------------------------------------------------------------
# Incident attachments
# ---------------------------------------------------------------------------


@router.post("/incident/attach", response_model=IncidentDocumentRead)
async def attach_to_incident(payload: IncidentDocumentCreate) -> IncidentDocumentRead:
    return services.attach_to_incident(payload)
