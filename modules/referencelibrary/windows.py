from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_form_library_panel", "get_library_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_form_library_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Form Library."""
    return _make_panel(
        "Form Library",
        f"Browse ICS forms — incident: {incident_id}",
    )

def get_library_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Reference Library."""
    return _make_panel(
        "Reference Library",
        f"Reference documents — incident: {incident_id}",
    )
