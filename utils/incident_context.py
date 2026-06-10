"""Incident context utilities."""
from __future__ import annotations

from pathlib import Path

from . import incident_storage

_active_incident_id: str | None = None


def set_active_incident(incident_id: str | None) -> None:
    """Set the identifier for the active incident."""
    global _active_incident_id
    _active_incident_id = None if incident_id is None else str(incident_id)


def get_active_incident_id() -> str | None:
    """Return the currently configured incident identifier or ``None``."""
    return _active_incident_id


def get_active_incident_paths() -> incident_storage.IncidentPaths:
    if not _active_incident_id:
        raise RuntimeError("Active incident has not been set")

    incident_storage.ensure_layout_initialized()
    resolved = incident_storage.resolve_incident_paths_by_identifier(_active_incident_id)
    if resolved is None:
        # Transitional compatibility: create a scaffolded folder using identifier-only
        metadata = incident_storage.infer_incident_metadata(_active_incident_id)
        resolved = incident_storage.get_incident_paths(
            incident_number=metadata.get("incident_number") or _active_incident_id,
            incident_name=metadata.get("name") or _active_incident_id,
            incident_id=metadata.get("incident_id") or _active_incident_id,
        )
        incident_storage.ensure_incident_structure(resolved, metadata)
    return resolved


def get_active_incident_db_path() -> Path:
    """Return the incident operational database path for the active incident."""
    return get_active_incident_paths().incident_db


def get_active_spatial_db_path() -> Path:
    """Return the spatial database path for the active incident."""
    return get_active_incident_paths().spatial_db


__all__ = [
    "set_active_incident",
    "get_active_incident_id",
    "get_active_incident_paths",
    "get_active_incident_db_path",
    "get_active_spatial_db_path",
]
