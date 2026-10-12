"""Incident attachment storage backed by MongoDB GridFS."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Optional
from urllib.parse import quote

import gridfs
from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

_GRIDFS_COLLECTION = "attachment_files"


class AttachmentsRepository(BaseRepository):
    collection_name = IncidentCollections.ATTACHMENTS
    soft_deletes = False


def _repo(incident_id: str) -> AttachmentsRepository:
    return AttachmentsRepository(get_incident_db(incident_id))


def _fs(incident_id: str) -> gridfs.GridFS:
    return gridfs.GridFS(get_incident_db(incident_id), collection=_GRIDFS_COLLECTION)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_int_id(repo: AttachmentsRepository) -> int:
    doc = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return int(doc["int_id"]) + 1 if doc else 1


def _attachment_id(incident_id: str, int_id: int) -> str:
    return f"{incident_id}-ATT-{int_id}"


def _clean_optional(value: Optional[str]) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _public_doc(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    gridfs_file_id = out.get("gridfs_file_id")
    if isinstance(gridfs_file_id, ObjectId):
        out["gridfs_file_id"] = str(gridfs_file_id)
    out["id"] = out.get("int_id")
    return out


def _find_attachment(repo: AttachmentsRepository, attachment_id: str) -> dict[str, Any] | None:
    query: dict[str, Any]
    try:
        query = {"int_id": int(attachment_id)}
    except (TypeError, ValueError):
        query = {"attachment_id": attachment_id}
    return repo.find_one(query)


@router.post("/incidents/{incident_id}/attachments", status_code=201)
async def upload_attachment(
    incident_id: str,
    file: UploadFile = File(...),
    owner_type: str = Form(...),
    owner_id: str = Form(...),
    category: str = Form("Other"),
    uploaded_by: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
) -> dict[str, Any]:
    """Upload one incident attachment and store its bytes in GridFS."""

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Attachment file is empty")

    repo = _repo(incident_id)
    int_id = _next_int_id(repo)
    attachment_id = _attachment_id(incident_id, int_id)
    filename = file.filename or "attachment"
    mime_type = file.content_type or "application/octet-stream"
    uploaded_at = _utcnow()
    checksum = hashlib.sha256(data).hexdigest()

    gridfs_file_id = _fs(incident_id).put(
        data,
        filename=filename,
        content_type=mime_type,
        metadata={
            "incident_id": incident_id,
            "attachment_id": attachment_id,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "uploaded_by": _clean_optional(uploaded_by),
            "uploaded_at": uploaded_at,
            "checksum_sha256": checksum,
        },
    )

    doc = repo.insert_one({
        "int_id": int_id,
        "attachment_id": attachment_id,
        "incident_id": incident_id,
        "owner_type": owner_type,
        "owner_id": str(owner_id),
        "category": category or "Other",
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": len(data),
        "checksum_sha256": checksum,
        "gridfs_file_id": gridfs_file_id,
        "uploaded_by": _clean_optional(uploaded_by),
        "uploaded_at": uploaded_at,
        "description": _clean_optional(description),
        "deleted": False,
    })
    return _public_doc(doc)


@router.get("/incidents/{incident_id}/attachments")
def list_attachments(
    incident_id: str,
    owner_type: Optional[str] = None,
    owner_id: Optional[str] = None,
    category: Optional[str] = None,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    repo = _repo(incident_id)
    query: dict[str, Any] = {"incident_id": incident_id}
    if owner_type:
        query["owner_type"] = owner_type
    if owner_id:
        query["owner_id"] = str(owner_id)
    if category:
        query["category"] = category
    if not include_deleted:
        query["deleted"] = {"$ne": True}
    docs = repo.find_many(query, sort=[("uploaded_at", -1), ("int_id", -1)])
    return [_public_doc(doc) for doc in docs]


@router.get("/incidents/{incident_id}/attachments/{attachment_id}")
def get_attachment(incident_id: str, attachment_id: str) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = _find_attachment(repo, attachment_id)
    if not doc or doc.get("incident_id") != incident_id or doc.get("deleted") is True:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return _public_doc(doc)


@router.get("/incidents/{incident_id}/attachments/{attachment_id}/download")
def download_attachment(incident_id: str, attachment_id: str) -> StreamingResponse:
    repo = _repo(incident_id)
    doc = _find_attachment(repo, attachment_id)
    if not doc or doc.get("incident_id") != incident_id or doc.get("deleted") is True:
        raise HTTPException(status_code=404, detail="Attachment not found")
    gridfs_file_id = doc.get("gridfs_file_id")
    if not gridfs_file_id:
        raise HTTPException(status_code=404, detail="Attachment file not found")
    try:
        stream = _fs(incident_id).get(gridfs_file_id)
        data = stream.read()
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Attachment file not found") from exc

    filename = str(doc.get("filename") or "attachment")
    quoted = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        "Content-Length": str(len(data)),
    }
    return StreamingResponse(
        BytesIO(data),
        media_type=str(doc.get("mime_type") or "application/octet-stream"),
        headers=headers,
    )


class _AttachmentUpdate(BaseModel):
    category: str


@router.patch("/incidents/{incident_id}/attachments/{attachment_id}")
def update_attachment(
    incident_id: str,
    attachment_id: str,
    body: _AttachmentUpdate,
) -> dict[str, Any]:
    repo = _repo(incident_id)
    doc = _find_attachment(repo, attachment_id)
    if not doc or doc.get("incident_id") != incident_id or doc.get("deleted") is True:
        raise HTTPException(status_code=404, detail="Attachment not found")
    repo.update_one(doc["_id"], {"category": body.category})
    doc["category"] = body.category
    return _public_doc(doc)


@router.delete("/incidents/{incident_id}/attachments/{attachment_id}")
def delete_attachment(
    incident_id: str,
    attachment_id: str,
    purge_file: bool = Query(False),
) -> dict[str, bool]:
    repo = _repo(incident_id)
    doc = _find_attachment(repo, attachment_id)
    if not doc or doc.get("incident_id") != incident_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    repo.update_one(doc["_id"], {"deleted": True, "deleted_at": _utcnow()})
    if purge_file and doc.get("gridfs_file_id"):
        try:
            _fs(incident_id).delete(doc["gridfs_file_id"])
        except Exception:
            pass
    return {"ok": True}
