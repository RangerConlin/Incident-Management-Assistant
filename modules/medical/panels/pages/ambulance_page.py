"""Ambulance Services page for ICS 206."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QPlainTextEdit, QDialogButtonBox, QMenu
)

from ...models.ics206_models import AmbulanceModel


class AmbulanceDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ambulance Service")
        form = QFormLayout(self)
        self.agency = QLineEdit()
        self.level = QComboBox(); self.level.addItems(["MFR", "BLS", "ALS"])
        self.et = QSpinBox(); self.et.setRange(0, 600)
        self.notes = QPlainTextEdit(); self.notes.setFixedHeight(60)
        form.addRow("Agency", self.agency)
        form.addRow("Level", self.level)
        form.addRow("ET (min)", self.et)
        form.addRow("Notes", self.notes)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        if data:
            self.agency.setText(data.get("agency", ""))
            self.level.setCurrentText(data.get("level", "MFR"))
            self.et.setValue(int(data.get("et_minutes", 0)))
            self.notes.setPlainText(data.get("notes", ""))

    def get_data(self) -> dict:
        return {
            "agency": self.agency.text(),
            "level": self.level.currentText(),
            "et_minutes": self.et.value(),
            "notes": self.notes.toPlainText(),
        }


class AmbulancePage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Remove")
        self.btn_import = QPushButton("Import from Master")
        for b in (self.btn_add, self.btn_edit, self.btn_del, self.btn_import):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.model = AmbulanceModel(self.bridge)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        layout.addWidget(self.table, 1)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_import.clicked.connect(self.on_import)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)

    def reload(self) -> None:
        self.model.refresh()

    def current_row(self) -> dict | None:
        idx = self.table.currentIndex()
        return self.model.row(idx) if idx.isValid() else None

    # slots -------------------------------------------------------------
    def on_add(self) -> None:
        dlg = AmbulanceDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.model.insertRow(dlg.get_data())

    def on_edit(self) -> None:
        row = self.current_row()
        if not row:
            return
        dlg = AmbulanceDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            self.model.updateRow(row["id"], dlg.get_data())

    def on_delete(self) -> None:
        row = self.current_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove", "Delete selected service?") == QMessageBox.Yes:
            self.model.removeRow(row["id"])

    def on_import(self) -> None:
        self.bridge.import_ambulance_from_master([])
        self.reload()

    def open_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self.on_edit)
        menu.addAction("Remove", self.on_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))
