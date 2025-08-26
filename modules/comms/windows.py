from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_chat_panel", "get_213_panel", "get_205_panel", "get_217_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_chat_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Chat."""
    return _make_panel(
        "Incident Chat",
        f"Chat window — incident: {incident_id}",
    )

def get_213_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for General Message (ICS-213)."""
    return _make_panel(
        "General Message (ICS-213)",
        f"ICS-213 form — incident: {incident_id}",
    )

def get_205_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Communications Plan (ICS-205)."""
    return _make_panel(
        "Communications Plan (ICS-205)",
        f"ICS-205 form — incident: {incident_id}",
    )

def get_217_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Radio Log (ICS-217)."""
    return _make_panel(
        "Radio Log (ICS-217)",
        f"ICS-217 log — incident: {incident_id}",
    )
