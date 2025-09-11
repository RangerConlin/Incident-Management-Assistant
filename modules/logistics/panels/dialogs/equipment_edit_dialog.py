"""Dialog for editing equipment items."""

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

from ...models.dto import Equipment, ResourceStatus


class EquipmentEditDialog(QDialog):  # pragma: no cover
    def __init__(self, item: Equipment | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equipment")
        layout = QFormLayout(self)
        self.name = QLineEdit(item.name if item else "")
        self.type = QLineEdit(item.type if item else "")
        self.serial = QLineEdit(item.serial if item else "")
        layout.addRow("Name", self.name)
        layout.addRow("Type", self.type)
        layout.addRow("Serial", self.serial)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]
        layout.addWidget(buttons)
        self._orig = item

    def get_result(self) -> Equipment:
        e = self._orig or Equipment(
            id=None,
            name="",
            type="",
            serial="",
            assigned_team_id=None,
            status=ResourceStatus.AVAILABLE,
        )
        e.name = self.name.text()
        e.type = self.type.text()
        e.serial = self.serial.text()
        return e
