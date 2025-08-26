from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_dashboard_panel",
    "get_approvals_panel",
    "get_forecast_panel",
    "get_op_manager_panel",
    "get_taskmetrics_panel",
    "get_strategic_objectives_panel",
    "get_sitrep_panel",
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
    """Return placeholder QWidget for Planning Dashboard."""
    return _make_panel(
        "Planning Dashboard",
        f"Placeholder panel — incident: {incident_id}",
    )

def get_approvals_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Pending Approvals."""
    return _make_panel(
        "Pending Approvals",
        f"Approvals queue — incident: {incident_id}",
    )

def get_forecast_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planning Forecast."""
    return _make_panel(
        "Planning Forecast",
        f"Forecast tools — incident: {incident_id}",
    )

def get_op_manager_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Operational Period Manager."""
    return _make_panel(
        "Operational Period Manager",
        f"OP builder — incident: {incident_id}",
    )

def get_taskmetrics_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Task Metrics Dashboard."""
    return _make_panel(
        "Task Metrics Dashboard",
        f"Metrics — incident: {incident_id}",
    )

def get_strategic_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Strategic Objective Tracker."""
    return _make_panel(
        "Strategic Objective Tracker",
        f"Objectives — incident: {incident_id}",
    )

def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Situation Report."""
    return _make_panel(
        "Situation Report",
        f"SITREP — incident: {incident_id}",
    )
