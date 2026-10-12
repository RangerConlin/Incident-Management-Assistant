from PySide6.QtWidgets import QWidget

from .panels import FacilitiesManagerPanel

__all__ = ["get_facilities_manager_panel"]


def get_facilities_manager_panel(incident_id: object | None = None) -> QWidget:
    return FacilitiesManagerPanel(incident_id=incident_id)
