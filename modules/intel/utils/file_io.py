"""Helpers for storing and retrieving intel attachments."""

from __future__ import annotations

from pathlib import Path
import shutil
import uuid


def save_attachment(incident_id: str, source: Path) -> Path:
    """Copy ``source`` into the incident's attachment directory.

    The file is stored under ``data/incidents/<incident_id>/intel_attachments``
    using a UUID file name to avoid collisions.  The new file path is
    returned to the caller.
    """

    dest_dir = Path("data") / "incidents" / str(incident_id) / "intel_attachments"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{uuid.uuid4()}{source.suffix}"
    shutil.copy2(source, dest_path)
    return dest_path
