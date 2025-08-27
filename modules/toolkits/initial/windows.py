from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_hasty_panel", "get_reflex_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_hasty_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Hasty Team Form."""
    return _make_panel(
        "Hasty Team Form",
        f"Log hasty team data — incident: {incident_id}",
    )

def get_reflex_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Reflex Tasking."""
    return _make_panel(
        "Reflex Tasking",
        f"Plan reflex tasks — incident: {incident_id}",
    )
