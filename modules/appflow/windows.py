from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_exit_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_exit_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Exit Workflow."""
    return _make_panel(
        "Exit Workflow",
        f"Save, discard, or cancel changes — mission: {mission_id}",
    )
