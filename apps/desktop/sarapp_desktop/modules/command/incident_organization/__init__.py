"""Incident Organization Management module."""
from __future__ import annotations

from .controller import IncidentOrganizationController

__all__ = [
    "IncidentOrganizationController",
    "IncidentOrganizationPanel",
    "get_incident_organization_panel",
]


def __getattr__(name: str):
    if name == "IncidentOrganizationPanel":
        from .panels.incident_organization_panel import IncidentOrganizationPanel

        return IncidentOrganizationPanel
    raise AttributeError(name)


def get_incident_organization_panel(incident_id: str | None = None):
    """Return the Qt Widgets panel for incident organization management."""

    from .panels.incident_organization_panel import IncidentOrganizationPanel

    panel = IncidentOrganizationPanel()
    if incident_id:
        panel.load(incident_id)
    return panel
