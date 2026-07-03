"""File-system attachment service for Intel Items.

Attachments are stored on disk alongside a JSON manifest, mirroring the
pattern used by task attachments.  This keeps binary files out of MongoDB
while metadata remains lightweight.

Layout:
    <incident_root>/files/attachments/intel_items/<item_id>/
        attachments.json   — manifest
        <id>_<filename>    — copied file
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from utils import incident_context, incident_storage
except Exception:  # pragma: no cover
    incident_context = None  # type: ignore[assignment]
    incident_storage = None  # type: ignore[assignment]


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


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _attachments_dir(item_id: str, incident_id: Optional[str] = None) -> Path:
    """Return the intel item attachments directory, creating it if needed."""
    resolved_incident_id = incident_id
    if not resolved_incident_id:
        try:
            resolved_incident_id = (
                incident_context.get_active_incident_id() if incident_context else None
            )
        except Exception:
            pass
    resolved_incident_id = resolved_incident_id or "unknown"

    paths = incident_storage.resolve_incident_paths_by_identifier(resolved_incident_id)
    if paths is None:
        metadata = incident_storage.infer_incident_metadata(resolved_incident_id)
        paths = incident_storage.get_incident_paths(
            incident_number=metadata.get("incident_number") or resolved_incident_id,
            incident_name=metadata.get("name") or resolved_incident_id,
            incident_id=metadata.get("incident_id") or resolved_incident_id,
        )
        incident_storage.ensure_incident_structure(paths, metadata)
    base = paths.files_attachments / "intel_items" / str(item_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _manifest_path(item_id: str, incident_id: Optional[str] = None) -> Path:
    return _attachments_dir(item_id, incident_id) / "attachments.json"


def _load_manifest(item_id: str, incident_id: Optional[str] = None) -> Dict[str, Any]:
    p = _manifest_path(item_id, incident_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_id": 1, "attachments": []}


def _save_manifest(
    item_id: str, manifest: Dict[str, Any], incident_id: Optional[str] = None
) -> None:
    p = _manifest_path(item_id, incident_id)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def list_attachments(
    item_id: str, incident_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return the attachment list for an Intel Item."""
    return _load_manifest(item_id, incident_id).get("attachments", [])


def add_attachment(
    item_id: str,
    source_path: str,
    attachment_name: str = "",
    uploaded_by: str = "",
    notes: str = "",
    incident_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Copy a file into the item's attachment directory and record it in the manifest.

    Returns a dict with keys: ``added``, ``warning`` (optional), ``attachment``.
    """
    src = Path(source_path)
    if not src.exists():
        return {"added": False, "error": f"File not found: {source_path}"}

    manifest = _load_manifest(item_id, incident_id)
    att_id = manifest["next_id"]
    filename = src.name
    dest_filename = f"{att_id}_{filename}"
    dest_dir = _attachments_dir(item_id, incident_id)
    dest_path = dest_dir / dest_filename

    shutil.copy2(str(src), str(dest_path))

    size = dest_path.stat().st_size
    ext = src.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".pdf": "application/pdf",
        ".txt": "text/plain", ".csv": "text/csv",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".mp4": "video/mp4", ".mp3": "audio/mpeg",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    record: Dict[str, Any] = {
        "id": att_id,
        "filename": filename,
        "attachment_name": attachment_name or filename,
        "mime_type": mime_type,
        "size": size,
        "uploaded_at": _utcnow(),
        "uploaded_by": uploaded_by,
        "storage_path": str(dest_path),
        "notes": notes,
    }
    manifest["attachments"].append(record)
    manifest["next_id"] = att_id + 1
    _save_manifest(item_id, manifest, incident_id)

    result: Dict[str, Any] = {"added": True, "attachment": record}
    if size > ATTACHMENT_MAX_WARN_BYTES:
        result["warning"] = f"File is large ({size // (1024 * 1024)} MB)."
    return result


def get_attachment_path(
    item_id: str,
    attachment_id: int,
    incident_id: Optional[str] = None,
) -> Optional[str]:
    """Return the filesystem path for an attachment, or None if not found."""
    manifest = _load_manifest(item_id, incident_id)
    for att in manifest.get("attachments", []):
        if att.get("id") == attachment_id:
            p = att.get("storage_path", "")
            return p if p and Path(p).exists() else None
    return None


def remove_attachment(
    item_id: str,
    attachment_id: int,
    incident_id: Optional[str] = None,
) -> bool:
    """Remove an attachment record and delete its file.  Returns True on success."""
    manifest = _load_manifest(item_id, incident_id)
    remaining = []
    removed = False
    for att in manifest.get("attachments", []):
        if att.get("id") == attachment_id:
            removed = True
            p = att.get("storage_path", "")
            if p and Path(p).exists():
                try:
                    os.remove(p)
                except OSError:
                    pass
        else:
            remaining.append(att)
    if removed:
        manifest["attachments"] = remaining
        _save_manifest(item_id, manifest, incident_id)
    return removed
