from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_dashboard_panel",
    "get_clue_log_panel",
    "get_add_clue_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Intel Dashboard."""
    return _make_panel(
        "Intel Dashboard",
        f"Intel overview — incident: {incident_id}",
    )

def get_clue_log_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Clue Log (SAR-134)."""
    return _make_panel(
        "Clue Log (SAR-134)",
        f"Track clues — incident: {incident_id}",
    )

def get_add_clue_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Add Clue (SAR-135)."""
    return _make_panel(
        "Add Clue (SAR-135)",
        f"Log a new clue — incident: {incident_id}",
    )
