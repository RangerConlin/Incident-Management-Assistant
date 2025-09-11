"""Dialog for vehicle records."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from ...models.dto import ResourceStatus, Vehicle


class VehicleEditDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None, vehicle: Optional[Vehicle] = None) -> None:
        super().__init__(parent)
        self._vehicle = vehicle
        self.setWindowTitle("Vehicle")
        layout = QtWidgets.QFormLayout(self)
        self.name = QtWidgets.QLineEdit(vehicle.name if vehicle else "")
        self.type = QtWidgets.QLineEdit(vehicle.type if vehicle else "")
        self.callsign = QtWidgets.QLineEdit(vehicle.callsign if vehicle else "")
        self.team = QtWidgets.QSpinBox()
        self.team.setMaximum(999999)
        if vehicle and vehicle.assigned_team_id:
            self.team.setValue(vehicle.assigned_team_id)
        self.status = QtWidgets.QComboBox()
        self.status.addItems([s.value for s in ResourceStatus])
        if vehicle:
            self.status.setCurrentText(vehicle.status.value)
        layout.addRow("Name", self.name)
        layout.addRow("Type", self.type)
        layout.addRow("Callsign", self.callsign)
        layout.addRow("Team", self.team)
        layout.addRow("Status", self.status)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_vehicle(self) -> Optional[Vehicle]:
        if self.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        veh = Vehicle(
            id=self._vehicle.id if self._vehicle else None,
            name=self.name.text(),
            type=self.type.text(),
            callsign=self.callsign.text(),
            assigned_team_id=self.team.value() or None,
            status=ResourceStatus(self.status.currentText()),
            notes=self._vehicle.notes if self._vehicle else "",
        )
        return veh
