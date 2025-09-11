"""Aid Stations page for ICS 206."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QPlainTextEdit, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QComboBox, QCheckBox, QDialogButtonBox, QMenu
)

from ...models.ics206_models import AidStationsModel


class AidStationDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aid Station")
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.type = QLineEdit()
        self.level = QComboBox(); self.level.addItems(["MFR", "BLS", "ALS"])
        self.is247 = QCheckBox("24/7")
        self.notes = QPlainTextEdit(); self.notes.setFixedHeight(60)
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Level", self.level)
        form.addRow("", self.is247)
        form.addRow("Notes", self.notes)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        if data:
            self.name.setText(data.get("name", ""))
            self.type.setText(data.get("type", ""))
            self.level.setCurrentText(data.get("level", "MFR"))
            self.is247.setChecked(bool(data.get("is_24_7")))
            self.notes.setPlainText(data.get("notes", ""))

    def get_data(self) -> dict:
        return {
            "name": self.name.text(),
            "type": self.type.text(),
            "level": self.level.currentText(),
            "is_24_7": 1 if self.is247.isChecked() else 0,
            "notes": self.notes.toPlainText(),
        }


class AidStationsPage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        # Button row
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Remove")
        self.btn_copy = QPushButton("Copy From 205")
        for b in (self.btn_add, self.btn_edit, self.btn_del, self.btn_copy):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Table
        self.model = AidStationsModel(self.bridge)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        layout.addWidget(self.table, 1)

        # Notes
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Notes…")
        layout.addWidget(self.notes)

        # Connections
        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_copy.clicked.connect(self.on_copy)
        self.table.selectionModel().currentChanged.connect(self.on_selection)
        self.notes.textChanged.connect(self.on_notes_changed)

        # Context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)

        self.current_id: int | None = None

    # ------------------------------------------------------------------
    def reload(self) -> None:
        self.model.refresh()

    def current_row(self) -> dict | None:
        idx = self.table.currentIndex()
        return self.model.row(idx) if idx.isValid() else None

    # slots -------------------------------------------------------------
    def on_add(self) -> None:
        dlg = AidStationDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.model.insertRow(dlg.get_data())

    def on_edit(self) -> None:
        row = self.current_row()
        if not row:
            return
        dlg = AidStationDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            self.model.updateRow(row["id"], dlg.get_data())

    def on_delete(self) -> None:
        row = self.current_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove", "Delete selected aid station?") == QMessageBox.Yes:
            self.model.removeRow(row["id"])

    def on_copy(self) -> None:
        self.bridge.import_aid_from_205()
        self.reload()

    def on_selection(self, current, _previous) -> None:
        row = self.current_row()
        if row:
            self.current_id = row["id"]
            self.notes.blockSignals(True)
            self.notes.setPlainText(row.get("notes", ""))
            self.notes.blockSignals(False)
        else:
            self.current_id = None
            self.notes.blockSignals(True)
            self.notes.clear()
            self.notes.blockSignals(False)

    def on_notes_changed(self) -> None:
        if self.current_id is not None:
            self.bridge.update_aid_station(self.current_id, {"notes": self.notes.toPlainText()})
            self.model.refresh()

    def open_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self.on_edit)
        menu.addAction("Remove", self.on_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))
