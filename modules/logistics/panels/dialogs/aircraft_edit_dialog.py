"""Dialog for aircraft records."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from ...models.dto import Aircraft, ResourceStatus


class AircraftEditDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None, aircraft: Optional[Aircraft] = None) -> None:
        super().__init__(parent)
        self._aircraft = aircraft
        self.setWindowTitle("Aircraft")
        layout = QtWidgets.QFormLayout(self)
        self.tail = QtWidgets.QLineEdit(aircraft.tail if aircraft else "")
        self.type = QtWidgets.QLineEdit(aircraft.type if aircraft else "")
        self.callsign = QtWidgets.QLineEdit(aircraft.callsign if aircraft else "")
        self.team = QtWidgets.QSpinBox()
        self.team.setMaximum(999999)
        if aircraft and aircraft.assigned_team_id:
            self.team.setValue(aircraft.assigned_team_id)
        self.status = QtWidgets.QComboBox()
        self.status.addItems([s.value for s in ResourceStatus])
        if aircraft:
            self.status.setCurrentText(aircraft.status.value)
        layout.addRow("Tail", self.tail)
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

    def get_aircraft(self) -> Optional[Aircraft]:
        if self.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        ac = Aircraft(
            id=self._aircraft.id if self._aircraft else None,
            tail=self.tail.text(),
            type=self.type.text(),
            callsign=self.callsign.text(),
            assigned_team_id=self.team.value() or None,
            status=ResourceStatus(self.status.currentText()),
            notes=self._aircraft.notes if self._aircraft else "",
        )
        return ac
