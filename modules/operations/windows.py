from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = ["get_dashboard_panel", "get_team_assignments_panel"]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_dashboard_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Operations Dashboard."""
    return _make_panel(
        "Operations Dashboard",
        f"Operations overview — mission: {mission_id}",
    )

def get_team_assignments_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Team Assignments."""
    return _make_panel(
        "Team Assignments",
        f"Manage team assignments — mission: {mission_id}",
    )
