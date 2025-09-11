from PySide6.QtWidgets import QWidget

from .panels import (
    IAPBuilderPanel,
    IncidentDashboardPanel,
    IncidentOverviewPanel,
    ObjectivesPanel,
    StaffOrgPanel,
    SitRepPanel,
)

__all__ = [
    "get_incident_dashboard_panel",
    "get_incident_overview_panel",
    "get_iap_builder_panel",
    "get_objectives_panel",
    "get_staff_org_panel",
    "get_sitrep_panel",
]


def get_incident_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return the dockable Incident Dashboard panel.

    TODO: pass ``incident_id`` to panel once wired to real data stores.
    """
    return IncidentDashboardPanel()


def get_incident_overview_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget for Incident Overview."""
    return IncidentOverviewPanel(incident_id)


def get_iap_builder_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget for IAP Builder."""
    return IAPBuilderPanel(incident_id)


def get_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget for Objectives."""
    return ObjectivesPanel(incident_id)


def get_staff_org_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget for staff organization."""
    return StaffOrgPanel(incident_id)


def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget for Situation Report."""
    return SitRepPanel(incident_id)
