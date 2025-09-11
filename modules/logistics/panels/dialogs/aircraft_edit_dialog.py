"""Dialog for editing aircraft."""

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

from ...models.dto import Aircraft, ResourceStatus


class AircraftEditDialog(QDialog):  # pragma: no cover
    def __init__(self, item: Aircraft | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aircraft")
        layout = QFormLayout(self)
        self.tail = QLineEdit(item.tail if item else "")
        self.type = QLineEdit(item.type if item else "")
        self.callsign = QLineEdit(item.callsign if item else "")
        layout.addRow("Tail", self.tail)
        layout.addRow("Type", self.type)
        layout.addRow("Callsign", self.callsign)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]
        layout.addWidget(buttons)
        self._orig = item

    def get_result(self) -> Aircraft:
        a = self._orig or Aircraft(
            id=None,
            tail="",
            type="",
            callsign="",
            assigned_team_id=None,
            status=ResourceStatus.AVAILABLE,
        )
        a.tail = self.tail.text()
        a.type = self.type.text()
        a.callsign = self.callsign.text()
        return a
