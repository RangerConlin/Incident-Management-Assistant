"""Home panel for logistics module with tabs."""
from __future__ import annotations

from PySide6 import QtWidgets

from .personnel_panel import PersonnelPanel
from .equipment_panel import EquipmentPanel
from .vehicles_panel import VehiclesPanel
from .aircraft_panel import AircraftPanel


class LogisticsHomePanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(PersonnelPanel(), "Personnel")
        tabs.addTab(EquipmentPanel(), "Equipment")
        tabs.addTab(VehiclesPanel(), "Vehicles")
        tabs.addTab(AircraftPanel(), "Aircraft")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(tabs)
