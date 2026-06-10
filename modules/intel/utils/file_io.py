"""Helpers for storing and retrieving intel attachments."""

from __future__ import annotations

from pathlib import Path

from utils import incident_storage
import shutil
import uuid


def save_attachment(incident_id: str, source: Path) -> Path:
    """Copy ``source`` into the incident's attachment directory.

    The file is stored under ``<data_root>/incidents/<incident_id>/files/attachments/intel``
    using a UUID file name to avoid collisions.  The new file path is
    returned to the caller.
    """

    paths = incident_storage.resolve_incident_paths_by_identifier(str(incident_id))
    if paths is None:
        meta = incident_storage.infer_incident_metadata(str(incident_id))
        paths = incident_storage.get_incident_paths(incident_number=meta.get("incident_number") or incident_id, incident_name=meta.get("name") or incident_id, incident_id=meta.get("incident_id") or incident_id)
        incident_storage.ensure_incident_structure(paths, meta)
    dest_dir = paths.files_attachments / "intel"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{uuid.uuid4()}{source.suffix}"
    shutil.copy2(source, dest_path)
    return dest_path
