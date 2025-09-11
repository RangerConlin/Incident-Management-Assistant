"""Dialog for creating or editing personnel."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from PySide6 import QtWidgets

from ...models.dto import CheckInStatus, PersonStatus, Personnel


class PersonnelEditDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None, person: Optional[Personnel] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Personnel")
        self._person = person

        layout = QtWidgets.QFormLayout(self)
        self.callsign = QtWidgets.QLineEdit(person.callsign if person else "")
        self.first_name = QtWidgets.QLineEdit(person.first_name if person else "")
        self.last_name = QtWidgets.QLineEdit(person.last_name if person else "")
        self.role = QtWidgets.QLineEdit(person.role if person else "")
        self.phone = QtWidgets.QLineEdit(person.phone if person else "")
        self.status = QtWidgets.QComboBox()
        self.status.addItems([s.value for s in PersonStatus])
        if person:
            self.status.setCurrentText(person.status.value)
        self.checkin_status = QtWidgets.QComboBox()
        self.checkin_status.addItems([c.value for c in CheckInStatus])
        if person:
            self.checkin_status.setCurrentText(person.checkin_status.value)

        layout.addRow("Callsign", self.callsign)
        layout.addRow("First Name", self.first_name)
        layout.addRow("Last Name", self.last_name)
        layout.addRow("Role", self.role)
        layout.addRow("Phone", self.phone)
        layout.addRow("Status", self.status)
        layout.addRow("Check-In", self.checkin_status)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_person(self) -> Optional[Personnel]:
        if self.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        person_dict = {
            "id": self._person.id if self._person else None,
            "callsign": self.callsign.text(),
            "first_name": self.first_name.text(),
            "last_name": self.last_name.text(),
            "role": self.role.text(),
            "team_id": self._person.team_id if self._person else None,
            "phone": self.phone.text(),
            "status": PersonStatus(self.status.currentText()),
            "checkin_status": CheckInStatus(self.checkin_status.currentText()),
            "notes": self._person.notes if self._person else "",
        }
        return Personnel(**person_dict)
