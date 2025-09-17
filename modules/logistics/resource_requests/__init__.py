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

    if incident_id is None:
        from utils import incident_db

        incident_id = incident_db.get_active_incident_id()
        if not incident_id:
            raise RuntimeError(
                "Active incident is not set. Call utils.incident_db.set_active_incident_id first."
            )

    db_path = Path("data") / "incidents" / f"{incident_id}.db"
    return ResourceRequestService(incident_id=incident_id, db_path=db_path)
