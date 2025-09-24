from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .panels.incident_dashboard_panel import IncidentDashboardPanel

__all__ = [
    "get_incident_dashboard_panel",
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


def get_incident_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return the dockable Incident Dashboard panel.

    TODO: pass ``incident_id`` to panel once wired to real data stores.
    """
    return IncidentDashboardPanel()


def get_incident_overview_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Incident Overview."""
    return _make_panel(
        "Incident Overview",
        f"Overview of the incident — incident: {incident_id}",
    )


def get_iap_builder_panel(incident_id: object | None = None) -> QWidget:
    """Return the Planning module's IAP Builder widget."""

    from modules.planning.windows import get_iap_builder_panel as planning_iap_builder

    return planning_iap_builder(incident_id)


def get_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return the strategic objectives panel from Planning."""
    from modules.planning.windows import get_strategic_objectives_panel

    return get_strategic_objectives_panel(incident_id)


def get_staff_org_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget wrapping the QML staff organization panel."""
    qml_file = Path(__file__).resolve().parent / "qml" / "StaffOrg.qml"
    widget = QQuickWidget()
    widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
    widget.setSource(QUrl.fromLocalFile(qml_file.as_posix()))
    return widget


def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Situation Report."""
    return _make_panel(
        "Situation Report",
        f"SITREP — incident: {incident_id}",
    )
