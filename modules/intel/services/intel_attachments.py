"""Attachment service for Intel Items, backed by the canonical GridFS attachments API.

See ``data/db/sarapp_db/api/routers/attachments.py`` and
``Design Documents/Instructions/mongodb_schema_decisions.md``.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.api_client import APIError, api_client

try:
    from utils import incident_context
except Exception:  # pragma: no cover
    incident_context = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ATTACHMENT_MAX_WARN_BYTES = 10 * 1024 * 1024  # 10 MB — warn but allow

ATTACHMENT_TYPE_CATEGORIES = [
    "Photo",
    "Map",
    "Form",
    "Document",
    "Scanned Note",
    "Screenshot",
    "Audio/Video",
    "Other",
]

_OWNER_TYPE = "intel_item"


def _resolve_incident_id(incident_id: Optional[str] = None) -> str:
    resolved = incident_id
    if not resolved:
        try:
            resolved = incident_context.get_active_incident_id() if incident_context else None
        except Exception:
            resolved = None
    if not resolved:
        raise RuntimeError("No active incident")
    return str(resolved)


def list_attachments(item_id: str, incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return the attachment list for an Intel Item."""
    try:
        inc = _resolve_incident_id(incident_id)
        docs = api_client.get(
            f"/api/incidents/{inc}/attachments",
            params={"owner_type": _OWNER_TYPE, "owner_id": str(item_id)},
        )
    except (APIError, RuntimeError) as exc:
        logger.warning("Failed to list attachments for intel item %s: %s", item_id, exc)
        return []
    out: List[Dict[str, Any]] = []
    for d in docs or []:
        out.append(
            {
                "id": d.get("id"),
                "filename": d.get("filename") or "",
                "mime_type": d.get("mime_type") or "",
                "size": int(d.get("size_bytes") or 0),
                "uploaded_at": d.get("uploaded_at") or "",
                "uploaded_by": d.get("uploaded_by") or "",
                "notes": d.get("description") or "",
            }
        )
    return out


def add_attachment(
    item_id: str,
    source_path: str,
    uploaded_by: str = "",
    notes: str = "",
    incident_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload a file as an Intel Item attachment.

    Returns a dict with keys: ``added``, ``warning`` (optional), ``attachment``.
    """
    src = Path(source_path)
    if not src.exists():
        return {"added": False, "error": f"File not found: {source_path}"}

    size = src.stat().st_size
    try:
        inc = _resolve_incident_id(incident_id)
        doc = api_client.post_file(
            f"/api/incidents/{inc}/attachments",
            file_path=str(src),
            data={
                "owner_type": _OWNER_TYPE,
                "owner_id": str(item_id),
                "category": "Other",
                "uploaded_by": uploaded_by or None,
                "description": notes or None,
            },
        )
    except (APIError, RuntimeError) as exc:
        return {"added": False, "error": str(exc)}

    record = {
        "id": doc.get("id"),
        "filename": doc.get("filename") or src.name,
        "mime_type": doc.get("mime_type") or "",
        "size": int(doc.get("size_bytes") or size),
        "uploaded_at": doc.get("uploaded_at") or "",
        "uploaded_by": doc.get("uploaded_by") or uploaded_by,
        "notes": doc.get("description") or notes,
    }
    result: Dict[str, Any] = {"added": True, "attachment": record}
    if size > ATTACHMENT_MAX_WARN_BYTES:
        result["warning"] = f"File is large ({size // (1024 * 1024)} MB)."
    return result


def get_attachment_path(
    item_id: str,
    attachment_id: int,
    incident_id: Optional[str] = None,
) -> Optional[str]:
    """Download the attachment and return a local temp file path to open."""
    try:
        inc = _resolve_incident_id(incident_id)
        doc = api_client.get(f"/api/incidents/{inc}/attachments/{int(attachment_id)}")
        data = api_client.get_bytes(f"/api/incidents/{inc}/attachments/{int(attachment_id)}/download")
    except (APIError, RuntimeError) as exc:
        logger.warning("Failed to download attachment %s: %s", attachment_id, exc)
        return None

    filename = str((doc or {}).get("filename") or f"attachment_{attachment_id}")
    tmp_dir = Path(tempfile.gettempdir()) / "ima_attachments" / inc / f"intel_item_{item_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dst = tmp_dir / filename
    dst.write_bytes(data)
    return str(dst)


def remove_attachment(
    item_id: str,
    attachment_id: int,
    incident_id: Optional[str] = None,
) -> bool:
    """Soft-delete an attachment and purge its stored bytes. Returns True on success."""
    try:
        inc = _resolve_incident_id(incident_id)
        api_client.delete(
            f"/api/incidents/{inc}/attachments/{int(attachment_id)}",
            params={"purge_file": True},
        )
        return True
    except (APIError, RuntimeError) as exc:
        logger.warning("Failed to remove attachment %s: %s", attachment_id, exc)
        return False


__all__ = [
    "ATTACHMENT_TYPE_CATEGORIES",
    "list_attachments",
    "add_attachment",
    "get_attachment_path",
    "remove_attachment",
]
