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
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_promotions_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Promotions Manager."""
    return _make_panel(
        "Promotions Manager",
        f"Handle promotions — mission: {mission_id}",
    )

def get_vendors_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Vendors Manager."""
    return _make_panel(
        "Vendors Manager",
        f"Manage vendors — mission: {mission_id}",
    )

def get_safety_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Event Safety."""
    return _make_panel(
        "Event Safety",
        f"Safety planning — mission: {mission_id}",
    )

def get_tasking_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Event Tasking."""
    return _make_panel(
        "Event Tasking",
        f"Task assignments — mission: {mission_id}",
    )

def get_health_sanitation_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Health & Sanitation."""
    return _make_panel(
        "Health & Sanitation",
        f"Health measures — mission: {mission_id}",
    )

def get_planned_toolkit_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planned Event Toolkit."""
    return _make_panel(
        "Planned Event Toolkit",
        f"Toolkit overview — mission: {mission_id}",
    )
