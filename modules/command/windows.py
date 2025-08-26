from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_incident_overview_panel",
    "get_iap_builder_panel",
    "get_objectives_panel",
    "get_staff_org_panel",
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

def get_incident_overview_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Overview."""
    return _make_panel(
        "Incident Overview",
        f"Overview of the incident — incident: {incident_id}",
    )

def get_iap_builder_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for IAP Builder."""
    return _make_panel(
        "IAP Builder",
        f"Build an Incident Action Plan — incident: {incident_id}",
    )

def get_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Objectives."""
    return _make_panel(
        "Incident Objectives",
        f"Manage incident objectives — incident: {incident_id}",
    )

def get_staff_org_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Staff Organization."""
    return _make_panel(
        "Staff Organization",
        f"View organization chart — incident: {incident_id}",
    )

def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Situation Report."""
    return _make_panel(
        "Situation Report",
        f"SITREP — incident: {incident_id}",
    )
