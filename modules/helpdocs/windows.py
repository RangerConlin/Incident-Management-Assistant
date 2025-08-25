from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_user_guide_panel", "get_about_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_user_guide_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for User Guide."""
    return _make_panel(
        "User Guide",
        f"Documentation — mission: {mission_id}",
    )

def get_about_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for About dialog."""
    return _make_panel(
        "About",
        f"About this application — mission: {mission_id}",
    )
