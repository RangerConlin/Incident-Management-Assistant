from PySide6.QtWidgets import QWidget

from .panels import HastyToolsPanel, ReflexTaskingPanel

__all__ = ["get_hasty_panel", "get_reflex_panel"]


def get_hasty_panel(incident_id: object | None = None) -> QWidget:
    del incident_id
    return HastyToolsPanel()


def get_reflex_panel(incident_id: object | None = None) -> QWidget:
    del incident_id
    return ReflexTaskingPanel()
