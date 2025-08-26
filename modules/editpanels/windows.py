from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_ems_hospitals_panel",
    "get_canned_comm_entries_panel",
    "get_objectives_panel",
    "get_task_types_panel",
    "get_team_types_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_ems_hospitals_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for EMS & Hospitals editor."""
    return _make_panel(
        "EMS & Hospitals",
        f"Edit EMS and hospitals — incident: {incident_id}",
    )

def get_canned_comm_entries_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for canned communication entries editor."""
    return _make_panel(
        "Canned Communication Entries",
        f"Manage canned communication entries — incident: {incident_id}",
    )

def get_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for objectives editor."""
    return _make_panel(
        "Objectives Editor",
        f"Manage incident objectives — incident: {incident_id}",
    )

def get_task_types_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for task types editor."""
    return _make_panel(
        "Task Types Editor",
        f"Manage task types — incident: {incident_id}",
    )

def get_team_types_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for team types editor."""
    return _make_panel(
        "Team Types Editor",
        f"Manage team types — incident: {incident_id}",
    )
