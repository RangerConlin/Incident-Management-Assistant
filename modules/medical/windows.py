from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_206_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_206_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Medical Plan (ICS-206)."""
    return _make_panel(
        "Medical Plan (ICS-206)",
        f"ICS-206 form — mission: {mission_id}",
    )
