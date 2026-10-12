from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_missing_person_panel", "get_pod_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    t = QLabel(title)
    t.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(t)
    layout.addWidget(QLabel(body))
    return w

def get_missing_person_panel(incident_id=None) -> QWidget:
    """Return placeholder QWidget for Missing Person Toolkit."""
    return _make_panel("Missing Person Toolkit", f"Toolkit — incident: {incident_id}")

def get_pod_panel(incident_id=None) -> QWidget:
    """Return placeholder QWidget for POD Calculator."""
    return _make_panel("POD Calculator", f"POD — incident: {incident_id}")
