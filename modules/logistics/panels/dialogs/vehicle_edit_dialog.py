"""Dialog for editing vehicles."""

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

from ...models.dto import Vehicle, ResourceStatus


class VehicleEditDialog(QDialog):  # pragma: no cover
    def __init__(self, item: Vehicle | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vehicle")
        layout = QFormLayout(self)
        self.name = QLineEdit(item.name if item else "")
        self.type = QLineEdit(item.type if item else "")
        self.callsign = QLineEdit(item.callsign if item else "")
        layout.addRow("Name", self.name)
        layout.addRow("Type", self.type)
        layout.addRow("Callsign", self.callsign)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]
        layout.addWidget(buttons)
        self._orig = item

    def get_result(self) -> Vehicle:
        v = self._orig or Vehicle(
            id=None,
            name="",
            type="",
            callsign="",
            assigned_team_id=None,
            status=ResourceStatus.AVAILABLE,
        )
        v.name = self.name.text()
        v.type = self.type.text()
        v.callsign = self.callsign.text()
        return v
