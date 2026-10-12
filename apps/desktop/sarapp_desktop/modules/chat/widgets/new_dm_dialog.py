"""Dialog for starting a direct message, wrapping the existing single-select
personnel picker."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from modules.logistics.facilities.widgets.personnel_picker import PersonnelPicker


class NewDmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Direct Message")

        self._picker = PersonnelPicker(self)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Message to"))
        layout.addWidget(self._picker)
        layout.addWidget(self._buttons)

    @property
    def selected_person_id(self) -> str:
        return self._picker.personnel_id


__all__ = ["NewDmDialog"]
