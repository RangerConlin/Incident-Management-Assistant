from __future__ import annotations

from .api import router
from .panels.PlannedToolkitHome import PlannedToolkitHome


def get_planned_toolkit_panel():
    """Return the main panel instance for the Planned Event Toolkit."""
    return PlannedToolkitHome()

__all__ = ["router", "get_planned_toolkit_panel"]
