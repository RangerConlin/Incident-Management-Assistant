"""Public API for the Reference Library module — backed by MongoDB API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from utils.api_client import api_client
from ..services import storage, ingest


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
) -> dict[str, Any]:
    """Add a reference document to the library."""
    file_path = Path(file_path)
    dest_path, file_hash = storage.store_file(file_path)
    meta = ingest.extract_metadata(dest_path)
    return api_client.post(
        "/api/master/reference-library/documents",
        json={
            "title": title,
            "category": category,
            "tags": tags or [],
            "agency": agency,
            "jurisdiction": jurisdiction,
            "description": description,
            "file_path": str(dest_path),
            "file_hash": file_hash,
            "file_ext": meta.extension,
            "file_size": meta.size,
            "created_by": created_by,
        },
    )


def search_references(query: str, filters: Optional[dict] = None) -> list[dict[str, Any]]:
    """Search reference documents."""
    params: dict = {"search": query}
    if filters:
        if cat := filters.get("category"):
            params["category"] = cat
    try:
        return api_client.get("/api/master/reference-library/documents", params=params) or []
    except Exception:
        return []


def get_reference_by_id(doc_id: int) -> Optional[dict[str, Any]]:
    try:
        return api_client.get(f"/api/master/reference-library/documents/{doc_id}")
    except Exception:
        return None


def link_reference_to_collection(document_id: int, collection_id: int) -> None:
    api_client.post(f"/api/master/reference-library/collections/{collection_id}/documents/{document_id}")


def list_collections() -> list[dict[str, Any]]:
    try:
        return api_client.get("/api/master/reference-library/collections") or []
    except Exception:
        return []
