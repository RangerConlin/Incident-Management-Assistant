"""Logistics Resource Requests module (QtWidgets only).

This subpackage exposes helper factories used by the host application to
construct list/detail panels and services.  All heavy lifting lives inside the
subdirectories so import here stays intentionally lightweight to avoid pulling
Qt during module discovery.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .api.service import ResourceRequestService

__all__ = ["get_service", "ResourceRequestService"]


_DEFAULT_TRAINING_INCIDENT_ID = "TRAINING-001"


def _sync_contexts(incident_id: str) -> None:
    """Propagate the active incident identifier to shared context helpers."""

    try:
        from utils import incident_context

        incident_context.set_active_incident(incident_id)
    except Exception:
        # ``incident_context`` is a best-effort helper that may not be available
        # in light-weight unit tests.  Failing silently keeps the fallback logic
        # robust without introducing hard dependencies.
        pass


def get_service(incident_id: Optional[str] = None) -> ResourceRequestService:
    """Return a service instance bound to ``incident_id``.

    Parameters
    ----------
    incident_id:
        Optional identifier for the incident database.  When omitted we fall
        back to :func:`utils.incident_db.get_active_incident_id`.  The service
        will create the underlying database file if it does not yet exist to
        support offline-first behaviour mandated by the spec.
    """

    from utils import incident_db

    resolved_id = str(incident_id) if incident_id is not None else None

    if resolved_id:
        incident_db.set_active_incident_id(resolved_id)
        _sync_contexts(resolved_id)
    else:
        resolved_id = incident_db.get_active_incident_id()

        if not resolved_id:
            try:
                from utils import incident_context

                resolved_id = incident_context.get_active_incident_id()
                if resolved_id:
                    incident_db.set_active_incident_id(resolved_id)
            except Exception:
                resolved_id = None

        if not resolved_id:
            resolved_id = _DEFAULT_TRAINING_INCIDENT_ID
            incident_db.set_active_incident_id(resolved_id)

        _sync_contexts(resolved_id)

    db_path = Path("data") / "incidents" / f"{resolved_id}.db"
    return ResourceRequestService(incident_id=resolved_id, db_path=db_path)
