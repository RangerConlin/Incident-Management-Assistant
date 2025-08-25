from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_damage_panel",
    "get_urban_interview_panel",
    "get_photos_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    t = QLabel(title)
    t.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(t)
    layout.addWidget(QLabel(body))
    return w

def get_damage_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Damage Assessment."""
    return _make_panel("Damage Assessment", f"Damage assessment — mission: {mission_id}")

def get_urban_interview_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Urban Interview Log."""
    return _make_panel("Urban Interview Log", f"Urban interviews — mission: {mission_id}")

def get_photos_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Damage Photos."""
    return _make_panel("Damage Photos", f"Photos — mission: {mission_id}")
