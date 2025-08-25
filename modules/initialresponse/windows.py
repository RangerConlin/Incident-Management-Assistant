from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_hasty_panel", "get_reflex_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    t = QLabel(title)
    t.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(t)
    layout.addWidget(QLabel(body))
    return w

def get_hasty_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Hasty Tools."""
    return _make_panel("Hasty Tools", f"Hasty tools — mission: {mission_id}")

def get_reflex_panel(mission_id=None) -> QWidget:
    """Return placeholder QWidget for Reflex Taskings."""
    return _make_panel("Reflex Taskings", f"Reflex taskings — mission: {mission_id}")
