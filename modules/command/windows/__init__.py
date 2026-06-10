"""Windows and panel factories for the Command module."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from modules.command.incident_organization import get_incident_organization_panel
from modules.command.panels.incident_dashboard_panel import IncidentDashboardPanel
from modules.command.panels.incident_objectives_panel import IncidentObjectivesPanel

__all__ = [
    "get_incident_dashboard_panel",
    "get_incident_overview_panel",
    "get_iap_builder_panel",
    "get_objectives_panel",
    "get_staff_org_panel",
    "get_incident_organization_management_panel",
    "get_sitrep_panel",
]


def _make_panel(title: str, body: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_label)
    layout.addWidget(QLabel(body))
    return widget


def get_incident_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return the dockable Incident Dashboard panel."""

    return IncidentDashboardPanel()


def get_incident_overview_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Overview."""

    return _make_panel(
        "Incident Overview",
        f"Overview of the incident - incident: {incident_id}",
    )


def get_iap_builder_panel(incident_id: object | None = None) -> QWidget:
    """Return the Planning module's IAP Builder widget."""

    from modules.planning.windows import get_iap_builder_panel as planning_iap_builder

    return planning_iap_builder(incident_id)


def get_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return the Qt Widgets incident objectives panel."""

    return IncidentObjectivesPanel()


def get_incident_organization_management_panel(
    incident_id: object | None = None,
) -> QWidget:
    """Return the Incident Organization Management panel."""

    return get_incident_organization_panel(
        str(incident_id) if incident_id is not None else None
    )


def get_staff_org_panel(incident_id: object | None = None) -> QWidget:
    """Return the Incident Organization Management panel for staff organization."""

    return get_incident_organization_management_panel(incident_id)


def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Situation Report."""

    return _make_panel(
        "Situation Report",
        f"SITREP - incident: {incident_id}",
    )
