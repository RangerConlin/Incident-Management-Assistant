"""Dialog for equipment records."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from ...models.dto import Equipment, ResourceStatus


class EquipmentEditDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None, equipment: Optional[Equipment] = None) -> None:
        super().__init__(parent)
        self._equipment = equipment
        self.setWindowTitle("Equipment")
        layout = QtWidgets.QFormLayout(self)
        self.name = QtWidgets.QLineEdit(equipment.name if equipment else "")
        self.type = QtWidgets.QLineEdit(equipment.type if equipment else "")
        self.serial = QtWidgets.QLineEdit(equipment.serial if equipment else "")
        self.team = QtWidgets.QSpinBox()
        self.team.setMaximum(999999)
        if equipment and equipment.assigned_team_id:
            self.team.setValue(equipment.assigned_team_id)
        self.status = QtWidgets.QComboBox()
        self.status.addItems([s.value for s in ResourceStatus])
        if equipment:
            self.status.setCurrentText(equipment.status.value)
        layout.addRow("Name", self.name)
        layout.addRow("Type", self.type)
        layout.addRow("Serial", self.serial)
        layout.addRow("Team", self.team)
        layout.addRow("Status", self.status)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_equipment(self) -> Optional[Equipment]:
        if self.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        eq = Equipment(
            id=self._equipment.id if self._equipment else None,
            name=self.name.text(),
            type=self.type.text(),
            serial=self.serial.text(),
            assigned_team_id=self.team.value() or None,
            status=ResourceStatus(self.status.currentText()),
            notes=self._equipment.notes if self._equipment else "",
        )
        return eq
