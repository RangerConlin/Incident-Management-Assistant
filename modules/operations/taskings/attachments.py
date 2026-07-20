from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.api_client import APIError, api_client

try:
    from utils import incident_context
except Exception:  # pragma: no cover - defensive
    incident_context = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ATTACHMENT_MAX_WARN_BYTES = 10 * 1024 * 1024  # 10 MB: warn user but allow
ATTACHMENT_TYPE_CATEGORIES = [
    "Map",
    "Log",
    "Safety",
    "Assignment",
    "Debrief",
    "Photo",
    "Audio/Video",
    "Form",
    "Medical",
    "Communications",
    "Other",
]

_OWNER_TYPE = "task"


def _incident_id() -> str:
    incident_id = incident_context.get_active_incident_id() if incident_context else None
    if not incident_id:
        raise RuntimeError("No active incident")
    return str(incident_id)


def _infer_type(filename: str) -> str:
    import os

    ext = os.path.splitext(filename)[1].lower()
    name = os.path.basename(filename).lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".heic"}:
        return "Photo"
    if ext in {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".mkv"}:
        return "Audio/Video"
    if ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx"}:
        if any(term in name for term in ("ics", "form", "214", "204", "109", "104")):
            return "Form"
        if "debrief" in name or "brief" in name:
            return "Debrief"
        if "map" in name:
            return "Map"
        if "safety" in name:
            return "Safety"
        if "medical" in name:
            return "Medical"
        if "comm" in name or "radio" in name or "channel" in name or "205" in name:
            return "Communications"
        if "assign" in name or "task" in name:
            return "Assignment"
        return "Form"
    if ext in {".txt", ".log", ".json", ".csv"}:
        if "radio" in name or "comm" in name or "channel" in name:
            return "Communications"
        return "Log"
    return "Other"


def list_attachments(task_id: int) -> List[Dict[str, Any]]:
    """Return a flat list of attachment rows for a task.

    Row keys: id, filename, type, uploaded_by, timestamp, size_bytes, versions
    """
    try:
        incident_id = _incident_id()
        docs = api_client.get(
            f"/api/incidents/{incident_id}/attachments",
            params={"owner_type": _OWNER_TYPE, "owner_id": str(int(task_id))},
        )
    except (APIError, RuntimeError) as exc:
        logger.warning("Failed to list attachments for task %s: %s", task_id, exc)
        return []
    out: List[Dict[str, Any]] = []
    for d in docs or []:
        out.append(
            {
                "id": d.get("id"),
                "filename": d.get("filename") or "",
                "type": d.get("category") or _infer_type(d.get("filename") or ""),
                "uploaded_by": d.get("uploaded_by") or "",
                "timestamp": d.get("uploaded_at") or "",
                "size_bytes": int(d.get("size_bytes") or 0),
                "versions": 1,
            }
        )
    return out


def upload_attachment(
    task_id: int, source_path: str, uploaded_by: Optional[str | int] = None
) -> Dict[str, Any]:
    """Upload a file as a task attachment.

    Returns: { added_id, warning?: str, attachments: [...] }
    """
    src = Path(str(source_path))
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"File not found: {source_path}")
    size = src.stat().st_size
    warning = None
    if size >= ATTACHMENT_MAX_WARN_BYTES:
        warning = f"Large file ({size // (1024 * 1024)} MB). Upload may be slow."

    incident_id = _incident_id()
    doc = api_client.post_file(
        f"/api/incidents/{incident_id}/attachments",
        file_path=str(src),
        data={
            "owner_type": _OWNER_TYPE,
            "owner_id": str(int(task_id)),
            "category": _infer_type(src.name),
            "uploaded_by": str(uploaded_by) if uploaded_by is not None else None,
        },
    )
    return {
        "added_id": doc.get("id"),
        "warning": warning,
        "attachments": list_attachments(int(task_id)),
    }


def get_attachment_file(task_id: int, attachment_id: int, version: Optional[int] = None) -> Optional[str]:
    """Download the attachment and return a local temp file path to open.

    ``version`` is unused: the API stores a single current file per attachment.
    """
    incident_id = _incident_id()
    try:
        doc = api_client.get(f"/api/incidents/{incident_id}/attachments/{int(attachment_id)}")
        data = api_client.get_bytes(
            f"/api/incidents/{incident_id}/attachments/{int(attachment_id)}/download"
        )
    except APIError as exc:
        logger.warning("Failed to download attachment %s: %s", attachment_id, exc)
        return None

    filename = str((doc or {}).get("filename") or f"attachment_{attachment_id}")
    tmp_dir = Path(tempfile.gettempdir()) / "ima_attachments" / incident_id / f"task_{int(task_id)}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dst = tmp_dir / filename
    dst.write_bytes(data)
    return str(dst)


def attach_files(
    task_id: int, file_paths: List[str], uploaded_by: Optional[str | int] = None
) -> Dict[str, Any]:
    """Attach existing files (already on disk), returning the new attachment list.

    Convenience for attaching exported forms.
    """
    warning: Optional[str] = None
    last_id: Optional[int] = None
    added_ids: List[int] = []
    for p in file_paths or []:
        try:
            res = upload_attachment(int(task_id), str(p), uploaded_by)
            if res.get("warning"):
                warning = res.get("warning")
            last_id = res.get("added_id")
            if res.get("added_id") is not None:
                added_ids.append(int(res.get("added_id")))
        except Exception:
            continue
    return {
        "added_id": last_id,
        "added_ids": added_ids,
        "warning": warning,
        "attachments": list_attachments(int(task_id)),
    }


def delete_attachment(task_id: int, attachment_id: int) -> bool:
    """Soft-delete an attachment and purge its stored bytes."""
    incident_id = _incident_id()
    try:
        api_client.delete(
            f"/api/incidents/{incident_id}/attachments/{int(attachment_id)}",
            params={"purge_file": True},
        )
        return True
    except APIError as exc:
        logger.warning("Failed to delete attachment %s: %s", attachment_id, exc)
        return False


def set_attachment_type(task_id: int, attachment_id: int, attachment_type: str) -> bool:
    """Update the attachment's operational category."""
    normalized = str(attachment_type or "").strip()
    if not normalized:
        return False
    incident_id = _incident_id()
    try:
        api_client.patch(
            f"/api/incidents/{incident_id}/attachments/{int(attachment_id)}",
            json={"category": normalized},
        )
        return True
    except APIError as exc:
        logger.warning("Failed to update attachment %s type: %s", attachment_id, exc)
        return False


__all__ = [
    "ATTACHMENT_TYPE_CATEGORIES",
    "list_attachments",
    "upload_attachment",
    "get_attachment_file",
    "attach_files",
    "delete_attachment",
    "set_attachment_type",
]
