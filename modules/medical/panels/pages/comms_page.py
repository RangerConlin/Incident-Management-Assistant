"""Medical Communications page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QPlainTextEdit,
    QDialogButtonBox, QMenu
)

from ...models.ics206_models import CommsModel


class CommDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Medical Communication")
        form = QFormLayout(self)
        self.function = QLineEdit()
        self.channel = QLineEdit()
        self.notes = QPlainTextEdit(); self.notes.setFixedHeight(60)
        form.addRow("Function", self.function)
        form.addRow("Channel", self.channel)
        form.addRow("Notes", self.notes)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        if data:
            self.function.setText(data.get("function", ""))
            self.channel.setText(data.get("channel", ""))
            self.notes.setPlainText(data.get("notes", ""))

    def get_data(self) -> dict:
        return {
            "function": self.function.text(),
            "channel": self.channel.text(),
            "notes": self.notes.toPlainText(),
        }


class CommsPage(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Remove")
        self.btn_import = QPushButton("Import from Master")
        self.btn_link = QPushButton("Link to ICS 205")
        for b in (self.btn_add, self.btn_edit, self.btn_del, self.btn_import, self.btn_link):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.model = CommsModel(self.bridge)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        layout.addWidget(self.table, 1)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_del.clicked.connect(self.on_delete)
        self.btn_import.clicked.connect(self.on_import)
        self.btn_link.clicked.connect(lambda: None)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)

    def reload(self) -> None:
        self.model.refresh()

    def current_row(self) -> dict | None:
        idx = self.table.currentIndex()
        return self.model.row(idx) if idx.isValid() else None

    def on_add(self) -> None:
        dlg = CommDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.model.insertRow(dlg.get_data())

    def on_edit(self) -> None:
        row = self.current_row()
        if not row:
            return
        dlg = CommDialog(self, row)
        if dlg.exec() == QDialog.Accepted:
            self.model.updateRow(row["id"], dlg.get_data())

    def on_delete(self) -> None:
        row = self.current_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove", "Delete selected comm?") == QMessageBox.Yes:
            self.model.removeRow(row["id"])

    def on_import(self) -> None:
        self.bridge.import_comms_from_master([])
        self.reload()

    def open_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self.on_edit)
        menu.addAction("Remove", self.on_delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))
