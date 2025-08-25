from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_agencies_panel", "get_requests_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_agencies_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Cooperating Agencies."""
    return _make_panel(
        "Cooperating Agencies",
        f"Track partner agencies — mission: {mission_id}",
    )

def get_requests_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Liaison Requests."""
    return _make_panel(
        "Liaison Requests",
        f"Handle external requests — mission: {mission_id}",
    )
