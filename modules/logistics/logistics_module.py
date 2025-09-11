"""Entry point for registering the Logistics module with the host application."""

from __future__ import annotations

from .panels.logistics_home_panel import LogisticsHomePanel
from .bridges import logistics_bridge


def create_panel(incident_id: str | None = None):  # pragma: no cover - thin wrapper
    """Factory used by the application to create the module's main widget."""

    if incident_id:
        logistics_bridge.set_active_incident(incident_id)
    return LogisticsHomePanel()
