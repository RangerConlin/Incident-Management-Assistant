from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_208_panel",
    "get_215A_panel",
    "get_caporm_panel",
    "get_safety_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_208_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Safety Plan (ICS-208)."""
    return _make_panel(
        "Safety Plan (ICS-208)",
        f"ICS-208 form — mission: {mission_id}",
    )

def get_215A_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Action Safety Analysis (ICS-215A)."""
    return _make_panel(
        "Incident Action Safety Analysis (ICS-215A)",
        f"ICS-215A form — mission: {mission_id}",
    )

def get_caporm_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for CAP ORM."""
    return _make_panel(
        "CAP ORM",
        f"Operational risk management — mission: {mission_id}",
    )

def get_safety_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Safety Dashboard."""
    return _make_panel(
        "Safety Dashboard",
        f"Safety overview — mission: {mission_id}",
    )
