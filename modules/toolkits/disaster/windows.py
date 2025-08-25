from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_damage_panel",
    "get_urban_interview_panel",
    "get_photos_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_damage_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Damage Assessment."""
    return _make_panel(
        "Damage Assessment",
        f"Assess damage — mission: {mission_id}",
    )

def get_urban_interview_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Urban Interview."""
    return _make_panel(
        "Urban Interview",
        f"Conduct interviews — mission: {mission_id}",
    )

def get_photos_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Disaster Photos."""
    return _make_panel(
        "Disaster Photos",
        f"Photo records — mission: {mission_id}",
    )
