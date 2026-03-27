from __future__ import annotations

from . import incident_storage


def ensure_incident_dir() -> str:
    """Backward-compatible helper returning the incidents root directory."""
    incident_storage.ensure_layout_initialized()
    return str(incident_storage.incidents_root())
