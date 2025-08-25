from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_logistics_panel",
    "get_checkin_panel",
    "get_requests_panel",
    "get_equipment_panel",
    "get_213rr_panel",
    "get_personnel_panel",
    "get_vehicles_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_logistics_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Logistics Dashboard."""
    return _make_panel(
        "Logistics Dashboard",
        f"Logistics overview — mission: {mission_id}",
    )

def get_checkin_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Check-In (ICS-211)."""
    return _make_panel(
        "Check-In (ICS-211)",
        f"Personnel check-in — mission: {mission_id}",
    )

def get_requests_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Resource Requests."""
    return _make_panel(
        "Resource Requests",
        f"Submit and track requests — mission: {mission_id}",
    )

def get_equipment_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Equipment Management."""
    return _make_panel(
        "Equipment Management",
        f"Manage equipment — mission: {mission_id}",
    )

def get_213rr_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Resource Request (ICS-213RR)."""
    return _make_panel(
        "Resource Request (ICS-213RR)",
        f"ICS-213RR form — mission: {mission_id}",
    )

def get_personnel_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Personnel Manager."""
    return _make_panel(
        "Personnel Manager",
        f"Manage personnel — mission: {mission_id}",
    )

def get_vehicles_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Vehicle Roster."""
    return _make_panel(
        "Vehicle Roster",
        f"Manage vehicles — mission: {mission_id}",
    )
