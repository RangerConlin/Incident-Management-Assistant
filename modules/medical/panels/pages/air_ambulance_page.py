"""Air Ambulance page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QPlainTextEdit,
    QDialogButtonBox, QMenu
)

from ...models.ics206_models import AirAmbulanceModel


class AirAmbulanceDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Air Ambulance")
        form = QFormLayout(self)
        self.provider = QLineEdit()
        self.contact = QLineEdit()
        self.notes = QPlainTextEdit(); self.notes.setFixedHeight(60)
        form.addRow("Provider", self.provider)
        form.addRow("Contact", self.contact)
        form.addRow("Notes", self.notes)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        if data:
            self.provider.setText(data.get("provider", ""))
            self.contact.setText(data.get("contact", ""))
            self.notes.setPlainText(data.get("notes", ""))

    def get_data(self) -> dict:
        return {
            "provider": self.provider.text(),
            "contact": self.contact.text(),
            "notes": self.notes.toPlainText(),
        }


class AirAmbulancePage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Remove")
        for b in (self.btn_add, self.btn_edit, self.btn_del):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        self.btn_browse = QPushButton("Browse LZ Map")
        btn_row.addWidget(self.btn_browse)
        layout.addLayout(btn_row)

        self.model = AirAmbulanceModel(self.bridge)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        layout.addWidget(self.table, 1)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_browse.clicked.connect(lambda: None)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)

    def reload(self) -> None:
        self.model.refresh()

    def current_row(self) -> dict | None:
        idx = self.table.currentIndex()
        return self.model.row(idx) if idx.isValid() else None

    def on_add(self) -> None:
        dlg = AirAmbulanceDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.model.insertRow(dlg.get_data())

    def on_edit(self) -> None:
        row = self.current_row()
        if not row:
            return
        dlg = AirAmbulanceDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            self.model.updateRow(row["id"], dlg.get_data())

    def on_delete(self) -> None:
        row = self.current_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove", "Delete selected provider?") == QMessageBox.Yes:
            self.model.removeRow(row["id"])

    def open_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self.on_edit)
        menu.addAction("Remove", self.on_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))
