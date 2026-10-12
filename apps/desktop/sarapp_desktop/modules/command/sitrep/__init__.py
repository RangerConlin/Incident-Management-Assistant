"""Command Situation Report (ICS-209) submodule."""
from __future__ import annotations


__all__ = [
    "get_sitrep_panel",
]


def get_sitrep_panel(incident_id: str | None = None):
    """Return the Situation Report panel for the given incident.

    SitrepPanel.__init__ loads from the active incident context automatically.
    If an explicit incident_id is passed that differs from the current context,
    call load() to override.
    """
    from .panel import SitrepPanel
    from utils import incident_context

    panel = SitrepPanel()
    if incident_id and incident_id != incident_context.get_active_incident_id():
        panel.load(incident_id)
    return panel
