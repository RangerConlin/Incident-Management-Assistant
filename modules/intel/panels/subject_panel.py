"""Panel for managing subject profiles."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QMessageBox,
)

from ..models import Subject
from .subject_editor import SubjectEditor
from .. import services


class SubjectPanel(QWidget):
    headers = ["Name", "Sex", "DOB", "Race"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        self.add_btn = QPushButton("New Subject")
        self.edit_btn = QPushButton("Edit")
        self.del_btn = QPushButton("Delete")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.del_btn.clicked.connect(self._delete)

        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        try:
            subjects = services.list_subjects()
        except Exception:
            return
        for row, sub in enumerate(subjects):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(sub.name))
            self.table.setItem(row, 1, QTableWidgetItem(sub.sex or ""))
            self.table.setItem(row, 2, QTableWidgetItem(sub.dob or ""))
            self.table.setItem(row, 3, QTableWidgetItem(sub.race or ""))
            self.table.item(row, 0).setData(Qt.UserRole, sub.id)

    def _current_subject_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def _add(self) -> None:
        dlg = SubjectEditor(parent=self)
        if dlg.exec() == QDialog.Accepted:
            try:
                services.add_subject(dlg.subject)
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, "Error", str(exc))

    def _edit(self) -> None:
        sid = self._current_subject_id()
        if sid is None:
            QMessageBox.warning(self, "Edit Subject", "Select a subject to edit")
            return
        sub = services.get_subject(sid)
        if not sub:
            QMessageBox.warning(self, "Edit Subject", "Subject not found")
            return
        dlg = SubjectEditor(sub, self)
        if dlg.exec() == QDialog.Accepted:
            try:
                services.update_subject(dlg.subject)
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, "Error", str(exc))

    def _delete(self) -> None:
        sid = self._current_subject_id()
        if sid is None:
            QMessageBox.warning(self, "Delete Subject", "Select a subject to delete")
            return
        if QMessageBox.question(self, "Delete Subject", "Delete selected subject?") != QMessageBox.Yes:
            return
        try:
            services.delete_subject(sid)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))
