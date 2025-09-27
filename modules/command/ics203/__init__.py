"""ICS-203 (Organization Assignment List) command submodule."""
from __future__ import annotations

from .panels.ics203_panel import ICS203Panel

__all__ = ["ICS203Panel", "get_ics203_panel"]


def get_ics203_panel(incident_id: str | None = None) -> ICS203Panel:
    """Return an instantiated :class:`ICS203Panel`.

    Parameters
    ----------
    incident_id:
        Optional identifier for the incident whose organization will be loaded.
        When provided the panel immediately initialises its data sources.
    """

    panel = ICS203Panel()
    if incident_id:
        panel.load(incident_id)
    return panel
