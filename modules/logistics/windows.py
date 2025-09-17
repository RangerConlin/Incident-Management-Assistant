from PySide6 import QtCore
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QSplitter,
)
from utils import incident_context

__all__ = [
    "get_logistics_panel",
    "get_checkin_panel",
    "get_requests_panel",
    "get_equipment_panel",
    "get_213rr_panel",
    "get_personnel_panel",
    "get_vehicles_panel",
]


def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w


def _get_checkin_panel():
    # Lazy import to avoid circular imports at module load time
    from modules.logistics.checkin import CheckInPanel
    return CheckInPanel


def _get_home_panel():
    """Return the concrete QWidget class for the dashboard."""
    from .panels.logistics_home_panel import LogisticsHomePanel

    return LogisticsHomePanel


def get_logistics_panel(incident_id: object | None = None) -> QWidget:
    """Return the main Logistics dashboard panel."""

    HomePanel = _get_home_panel()
    incident = str(incident_id) if incident_id is not None else None
    return HomePanel(incident)


def get_checkin_panel(incident_id: object | None = None) -> QWidget:
    if incident_id is not None:
        incident_context.set_active_incident(str(incident_id))
    CheckInPanel = _get_checkin_panel()
    return CheckInPanel()


def get_equipment_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Equipment Management."""
    return _make_panel(
        "Equipment Management",
        f"Manage equipment — incident: {incident_id}",
    )


def get_213rr_panel(incident_id: object | None = None) -> QWidget:
    """Return the full Resource Request (ICS-213RR) workspace panel."""

    from modules.logistics.resource_requests import get_service
    from modules.logistics.resource_requests.panels.request_detail_panel import (
        ResourceRequestDetailPanel,
    )
    from modules.logistics.resource_requests.panels.request_list_panel import (
        ResourceRequestListPanel,
    )

    service = get_service(str(incident_id) if incident_id is not None else None)

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    splitter = QSplitter(QtCore.Qt.Orientation.Horizontal, container)
    list_panel = ResourceRequestListPanel(service=service, parent=splitter)
    detail_panel = ResourceRequestDetailPanel(service=service, parent=splitter)
    detail_panel.start_new()

    splitter.addWidget(list_panel)
    splitter.addWidget(detail_panel)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)

    layout.addWidget(splitter)

    def _activate(request_id: str) -> None:
        if request_id == "NEW":
            detail_panel.start_new()
            return
        detail_panel.load_request(request_id)

    list_panel.requestActivated.connect(_activate)
    detail_panel.requestSaved.connect(lambda _: list_panel.refresh())

    return container


def get_personnel_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Personnel Manager."""
    return _make_panel(
        "Personnel Manager",
        f"Manage personnel — incident: {incident_id}",
    )


def get_vehicles_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Vehicle Roster."""
    return _make_panel(
        "Vehicle Roster",
        f"Manage vehicles — incident: {incident_id}",
    )

