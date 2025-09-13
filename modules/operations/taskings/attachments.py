from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from utils import incident_context
except Exception:  # pragma: no cover - defensive
    incident_context = None  # type: ignore[assignment]


ATTACHMENT_MAX_WARN_BYTES = 10 * 1024 * 1024  # 10 MB: warn user but allow


def _now_utc_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _attachments_dir(task_id: int) -> Path:
    """Return the task attachments directory, creating it if needed.

    Structure: data/incidents/<incident_id>/tasks/<task_id>/attachments
    Falls back to data/incidents/unknown if no active incident is set.
    """
    try:
        incident_id = incident_context.get_active_incident_id() if incident_context else None
    except Exception:
        incident_id = None
    incident_id = incident_id or "unknown"
    base = Path("data") / "incidents" / str(incident_id) / "tasks" / str(int(task_id)) / "attachments"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _manifest_path(task_id: int) -> Path:
    return _attachments_dir(task_id) / "attachments.json"


def _load_manifest(task_id: int) -> Dict[str, Any]:
    p = _manifest_path(task_id)
    if not p.exists():
        return {"next_id": 1, "attachments": []}
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}") or {"next_id": 1, "attachments": []}
    except Exception:
        return {"next_id": 1, "attachments": []}


def _save_manifest(task_id: int, data: Dict[str, Any]) -> None:
    p = _manifest_path(task_id)
    # Ensure safe minimal structure
    payload = {"next_id": int(data.get("next_id", 1)), "attachments": list(data.get("attachments", []))}
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _infer_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mapping = {
        ".jpg": "Image",
        ".jpeg": "Image",
        ".png": "Image",
        ".gif": "Image",
        ".pdf": "PDF",
        ".txt": "Text",
        ".doc": "Word",
        ".docx": "Word",
        ".xls": "Excel",
        ".xlsx": "Excel",
        ".json": "JSON",
        ".csv": "CSV",
    }
    return mapping.get(ext, (ext[1:].upper() if ext else "File"))


def list_attachments(task_id: int) -> List[Dict[str, Any]]:
    """Return a flat list of attachment rows with latest version summary.

    Row keys: id, filename, type, uploaded_by, timestamp, size_bytes, versions (count)
    """
    m = _load_manifest(int(task_id))
    out: List[Dict[str, Any]] = []
    for a in m.get("attachments", []):
        try:
            versions = list(a.get("versions", []))
            v = versions[-1] if versions else {}
            row = {
                "id": int(a.get("id")),
                "filename": a.get("filename") or v.get("filename") or "",
                "type": a.get("type") or _infer_type(a.get("filename") or v.get("filename") or ""),
                "uploaded_by": v.get("uploaded_by") or a.get("uploaded_by") or "",
                "timestamp": v.get("timestamp") or a.get("timestamp") or "",
                "size_bytes": int(v.get("size_bytes") or 0),
                "versions": len(versions),
            }
            # bubble through associated team metadata if present
            if a.get("associated_team"):
                row["associated_team"] = a.get("associated_team")
            out.append(row)
        except Exception:
            continue
    return out


def _copy_with_version(task_id: int, src: Path, aid: int, base_filename: str, version: int) -> Tuple[Path, int]:
    dst_dir = _attachments_dir(task_id) / f"att{aid:04d}"
    dst_dir.mkdir(parents=True, exist_ok=True)
    # versioned file name: v{n}_{original}
    dst_name = f"v{version}_{base_filename}"
    dst = dst_dir / dst_name
    data = src.read_bytes()
    dst.write_bytes(data)
    return dst, len(data)


def upload_attachment(task_id: int, source_path: str, uploaded_by: Optional[str | int] = None, associated_team: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Copy a file into the attachments store, creating a new attachment or new version.

    Returns: { added_id, warning?: str, attachments: [...] }
    """
    src = Path(str(source_path))
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"File not found: {source_path}")
    size = src.stat().st_size
    warning = None
    if size >= ATTACHMENT_MAX_WARN_BYTES:
        warning = f"Large file ({size//(1024*1024)} MB). Upload may be slow."

    m = _load_manifest(int(task_id))
    attachments = list(m.get("attachments", []))
    base_name = src.name
    # Check if an attachment with same base filename exists; if so, add a version
    existing = None
    for a in attachments:
        if (a.get("filename") or "").lower() == base_name.lower():
            existing = a
            break

    ts = _now_utc_iso()
    by = str(uploaded_by) if uploaded_by is not None else ""
    if existing is None:
        aid = int(m.get("next_id", 1))
        ver = 1
        dst, nbytes = _copy_with_version(int(task_id), src, aid, base_name, ver)
        row = {
            "id": aid,
            "filename": base_name,
            "type": _infer_type(base_name),
            "versions": [
                {"version": ver, "path": str(dst), "timestamp": ts, "size_bytes": int(nbytes), "uploaded_by": by, "filename": base_name}
            ],
        }
        if associated_team:
            row["associated_team"] = dict(associated_team)
        attachments.append(row)
        m["next_id"] = int(aid + 1)
        added_id = aid
    else:
        aid = int(existing.get("id"))
        versions = list(existing.get("versions", []))
        ver = (int(versions[-1].get("version", 0)) if versions else 0) + 1
        dst, nbytes = _copy_with_version(int(task_id), src, aid, base_name, ver)
        versions.append({"version": ver, "path": str(dst), "timestamp": ts, "size_bytes": int(nbytes), "uploaded_by": by, "filename": base_name})
        existing["versions"] = versions
        # keep filename/type consistent
        existing["filename"] = base_name
        existing["type"] = existing.get("type") or _infer_type(base_name)
        added_id = aid

    m["attachments"] = attachments
    _save_manifest(int(task_id), m)
    return {"added_id": added_id, "warning": warning, "attachments": list_attachments(int(task_id))}


def get_attachment_file(task_id: int, attachment_id: int, version: Optional[int] = None) -> Optional[str]:
    """Return the absolute path to an attachment file; latest version by default."""
    m = _load_manifest(int(task_id))
    for a in m.get("attachments", []):
        if int(a.get("id")) == int(attachment_id):
            versions = list(a.get("versions", []))
            if not versions:
                return None
            if version is None:
                v = versions[-1]
            else:
                v = next((x for x in versions if int(x.get("version", 0)) == int(version)), versions[-1])
            return str(v.get("path")) if v else None
    return None


def annotate_attachment(task_id: int, attachment_id: int, note: str, user: Optional[str | int] = None) -> bool:
    """Append a textual annotation to the attachment's manifest."""
    m = _load_manifest(int(task_id))
    changed = False
    for a in m.get("attachments", []):
        if int(a.get("id")) == int(attachment_id):
            ann = list(a.get("annotations", []))
            ann.append({"timestamp": _now_utc_iso(), "note": str(note or ""), "by": str(user) if user is not None else ""})
            a["annotations"] = ann
            changed = True
            break
    if changed:
        _save_manifest(int(task_id), m)
    return changed


def attach_files(task_id: int, file_paths: List[str], uploaded_by: Optional[str | int] = None, associated_team: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Attach existing files (already on disk), returning the new manifest list.

    Convenience for attaching exported forms.
    """
    warning: Optional[str] = None
    last_id: Optional[int] = None
    added_ids: List[int] = []
    for p in (file_paths or []):
        try:
            res = upload_attachment(int(task_id), str(p), uploaded_by, associated_team)
            if res.get("warning"):
                warning = res.get("warning")
            last_id = res.get("added_id")
            try:
                if res.get("added_id") is not None:
                    added_ids.append(int(res.get("added_id")))
            except Exception:
                pass
        except Exception:
            continue
    return {"added_id": last_id, "added_ids": added_ids, "warning": warning, "attachments": list_attachments(int(task_id))}


def delete_attachment(task_id: int, attachment_id: int) -> bool:
    """Delete an attachment, including its files and manifest entry."""
    m = _load_manifest(int(task_id))
    changed = False
    new_list = []
    for a in m.get("attachments", []):
        if int(a.get("id")) == int(attachment_id):
            # remove files on disk
            try:
                versions = list(a.get("versions", []))
                for v in versions:
                    p = v.get("path")
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                # remove the dir
                att_dir = _attachments_dir(int(task_id)) / f"att{int(attachment_id):04d}"
                try:
                    # remove directory if empty
                    if att_dir.exists():
                        for _ in att_dir.iterdir():
                            break
                        else:
                            att_dir.rmdir()
                except Exception:
                    pass
            except Exception:
                pass
            changed = True
            continue
        new_list.append(a)
    if changed:
        m["attachments"] = new_list
        _save_manifest(int(task_id), m)
    return changed


def set_attachment_team(task_id: int, attachment_id: int, team: Dict[str, Any]) -> bool:
    """Associate an attachment with a team object (stored in manifest)."""
    m = _load_manifest(int(task_id))
    for a in m.get("attachments", []):
        if int(a.get("id")) == int(attachment_id):
            a["associated_team"] = dict(team or {})
            _save_manifest(int(task_id), m)
            return True
    return False


__all__ = [
    "list_attachments",
    "upload_attachment",
    "get_attachment_file",
    "annotate_attachment",
    "attach_files",
    "delete_attachment",
    "set_attachment_team",
]
