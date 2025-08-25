from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_time_panel",
    "get_procurement_panel",
    "get_summary_panel",
    "get_finance_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_time_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Time Tracking."""
    return _make_panel(
        "Time Tracking",
        f"Record time entries — mission: {mission_id}",
    )

def get_procurement_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Procurement."""
    return _make_panel(
        "Procurement",
        f"Manage purchasing — mission: {mission_id}",
    )

def get_summary_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Finance Summary."""
    return _make_panel(
        "Finance Summary",
        f"View summaries — mission: {mission_id}",
    )

def get_finance_panel(mission_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Finance Dashboard."""
    return _make_panel(
        "Finance Dashboard",
        f"Finance overview — mission: {mission_id}",
    )
