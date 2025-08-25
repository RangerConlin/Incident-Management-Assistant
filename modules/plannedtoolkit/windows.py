from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_promotions_panel",
    "get_vendors_panel",
    "get_safety_panel",
    "get_tasking_panel",
    "get_health_sanitation_panel",
    "get_planned_toolkit_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    t = QLabel(title)
    t.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(t)
    layout.addWidget(QLabel(body))
    return w

def get_promotions_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for External Messaging."""
    return _make_panel("External Messaging", f"Promotions — mission: {mission_id}")

def get_vendors_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Vendors & Permits."""
    return _make_panel("Vendors & Permits", f"Vendors — mission: {mission_id}")

def get_safety_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Public Safety."""
    return _make_panel("Public Safety", f"Safety — mission: {mission_id}")

def get_tasking_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Tasking & Assignments."""
    return _make_panel("Tasking & Assignments", f"Tasking — mission: {mission_id}")

def get_health_sanitation_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Health & Sanitation."""
    return _make_panel("Health & Sanitation", f"Health & sanitation — mission: {mission_id}")

def get_planned_toolkit_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Planned Event Toolkit."""
    return _make_panel("Planned Event Toolkit", f"Toolkit — mission: {mission_id}")
