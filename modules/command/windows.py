from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
