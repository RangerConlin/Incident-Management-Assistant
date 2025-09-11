from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QLabel
)

from ..controller import ICS205Controller


class ImportICS217Dialog(QDialog):
    def __init__(self, controller: ICS205Controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Import from ICS-217')
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Select channels to import:'))
        self.list = QListWidget()
        self.list.setSelectionMode(self.list.MultiSelection)
        layout.addWidget(self.list)
        for row in controller.masterModel.rows:
            item = QListWidgetItem(row['display_name'])
            item.setData(0x0100, row)  # Qt.UserRole
            self.list.addItem(item)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        for item in self.list.selectedItems():
            row = item.data(0x0100)
            self.controller.addMasterIdToPlan(row['id'])
        self.accept()
