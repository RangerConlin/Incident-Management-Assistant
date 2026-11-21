"""Picker dialog for an Assignment's assignee: an incident Personnel or
Operations Team record. Free-text assignees are entered directly on the
Assignment Detail dialog and never go through this picker.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils import incident_context

_KIND_LABELS = {"personnel": "Personnel", "team": "Operations Team"}


class AssigneePickerDialog(QDialog):
    """Pick an existing Personnel or Operations Team record.

    After ``exec() == QDialog.Accepted``, read ``selected_kind``
    (``"personnel"`` or ``"team"``), ``selected_id``, and ``selected_label``.
    """

    def __init__(self, parent: Optional[QWidget] = None, *, incident_id: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Assignee")
        self.resize(560, 420)
        self._incident_id = incident_id or incident_context.get_active_incident_id()
        self.selected_kind: Optional[str] = None
        self.selected_id: Optional[int] = None
        self.selected_label: str = ""

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Kind:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItem(_KIND_LABELS["personnel"], "personnel")
        self.kind_combo.addItem(_KIND_LABELS["team"], "team")
        top.addWidget(self.kind_combo)
        top.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Name, callsign…")
        top.addWidget(self.search_edit, 1)
        layout.addLayout(top)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["ID", "Name/Label"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.kind_combo.currentIndexChanged.connect(self._reload)
        self.search_edit.textChanged.connect(self._reload)
        self.table.itemDoubleClicked.connect(lambda *_: self._accept())
        self._reload()

    def _current_kind(self) -> str:
        return self.kind_combo.currentData() or "personnel"

    def _reload(self) -> None:
        kind = self._current_kind()
        query = self.search_edit.text().strip()
        try:
            from utils.api_client import api_client

            if kind == "personnel":
                rows = api_client.get("/api/master/personnel/search", params={"q": query}) or []
                id_field, label_fields = "person_record", ("name", "callsign")
            else:
                rows = []
                if self._incident_id:
                    rows = api_client.get(
                        f"/api/incidents/{self._incident_id}/operations/teams",
                    ) or []
                id_field, label_fields = "int_id", ("name", "callsign")
                if query:
                    needle = query.lower()
                    rows = [
                        row
                        for row in rows
                        if needle in str(row.get("name", "")).lower()
                        or needle in str(row.get("callsign", "")).lower()
                    ]
        except Exception:
            rows = []
            id_field, label_fields = ("person_record" if kind == "personnel" else "int_id"), ("name", "callsign")

        self.table.setRowCount(0)
        for row in rows:
            rid = row.get(id_field)
            if rid is None:
                continue
            label = ""
            for field in label_fields:
                label = str(row.get(field) or "")
                if label:
                    break
            r = self.table.rowCount()
            self.table.insertRow(r)
            id_item = QTableWidgetItem(str(rid))
            id_item.setData(Qt.UserRole, rid)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QTableWidgetItem(label))
        self.table.resizeColumnsToContents()

    def _accept(self) -> None:
        sel = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        row = sel[0].row() if sel else self.table.currentRow()
        if row is None or row < 0:
            QMessageBox.information(self, "Select Assignee", "Select a record from the list.")
            return
        id_item = self.table.item(row, 0)
        label_item = self.table.item(row, 1)
        self.selected_kind = self._current_kind()
        self.selected_id = id_item.data(Qt.UserRole)
        self.selected_label = label_item.text() if label_item else ""
        self.accept()
