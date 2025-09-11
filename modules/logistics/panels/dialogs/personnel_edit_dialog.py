"""Dialog for adding/editing a personnel record."""

from __future__ import annotations

try:  # pragma: no cover
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLineEdit,
    )
except Exception:  # pragma: no cover
    QDialog = QDialogButtonBox = QFormLayout = QLineEdit = object  # type: ignore

from ...models.dto import Personnel, PersonStatus, CheckInStatus


class PersonnelEditDialog(QDialog):  # pragma: no cover
    def __init__(self, person: Personnel | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Personnel")
        layout = QFormLayout(self)
        self.callsign = QLineEdit(person.callsign if person else "")
        self.first = QLineEdit(person.first_name if person else "")
        self.last = QLineEdit(person.last_name if person else "")
        self.role = QLineEdit(person.role if person else "")
        self.phone = QLineEdit(person.phone if person else "")
        layout.addRow("Callsign", self.callsign)
        layout.addRow("First", self.first)
        layout.addRow("Last", self.last)
        layout.addRow("Role", self.role)
        layout.addRow("Phone", self.phone)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]
        layout.addWidget(buttons)
        self._orig = person

    def get_result(self) -> Personnel:
        p = self._orig or Personnel(
            id=None,
            callsign="",
            first_name="",
            last_name="",
            role="",
            team_id=None,
            phone="",
            status=PersonStatus.AVAILABLE,
            checkin_status=CheckInStatus.PENDING,
        )
        p.callsign = self.callsign.text()
        p.first_name = self.first.text()
        p.last_name = self.last.text()
        p.role = self.role.text()
        p.phone = self.phone.text()
        return p
