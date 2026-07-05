from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

__all__ = [
    "get_dashboard_panel",
    "get_approvals_panel",
    "get_demobilization_panel",
    "get_iap_builder_panel",
    "get_op_manager_panel",
    "get_meetings_panel",
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


def get_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planning Dashboard."""
    return _make_panel(
        "Planning Dashboard",
        f"Placeholder panel - incident: {incident_id}",
    )


def get_approvals_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Pending Approvals."""
    return _make_panel(
        "Pending Approvals",
        f"Approvals queue - incident: {incident_id}",
    )


def get_demobilization_panel(incident_id: object | None = None) -> QWidget:
    """Return the demobilization planning panel."""
    from modules.planning.demobilization.panel import make_demobilization_panel

    incident_key = str(incident_id) if incident_id is not None else None
    return make_demobilization_panel(incident_id=incident_key)


def get_op_manager_panel(incident_id: object | None = None) -> QWidget:
    """Return the operational period manager panel."""
    from modules.planning.operational_periods.panel import (
        make_operational_period_manager_panel,
    )

    incident_key = str(incident_id) if incident_id is not None else None
    return make_operational_period_manager_panel(incident_id=incident_key)


def get_meetings_panel(incident_id: object | None = None) -> QWidget:
    """Return the Planning Meetings submodule panel."""
    from modules.planning.meetings.panel import make_meetings_panel

    incident_key = str(incident_id) if incident_id is not None else None
    return make_meetings_panel(incident_id=incident_key)


def get_iap_builder_panel(incident_id: object | None = None) -> QWidget:
    """Return the Qt Widgets based IAP Builder panel."""
    from app.modules.planning.iap.ui.iap_builder_window import IAPBuilderWindow

    incident_key = str(incident_id) if incident_id is not None else "demo-incident"
    return IAPBuilderWindow(incident_id=incident_key)


def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return the Situation Report (ICS-209) panel (owned by the command sitrep submodule)."""
    from modules.command.sitrep import get_sitrep_panel as _sitrep

    return _sitrep(str(incident_id) if incident_id is not None else None)
