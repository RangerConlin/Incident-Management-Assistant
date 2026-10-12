from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

__all__ = ["get_dashboard_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Operations Dashboard."""
    return _make_panel(
        "Operations Dashboard",
        f"Operations overview — incident: {incident_id}",
    )
