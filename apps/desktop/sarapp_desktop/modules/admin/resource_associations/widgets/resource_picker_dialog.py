"""Generic cross-kind resource search/picker dialog.

Reused everywhere a feature needs to let the operator pick "an existing
personnel/vehicle/aircraft/equipment master record" -- Resource Associations
(Stage 2) and Resource Package membership (Stage 3) both need exactly this,
so it lives once here instead of being duplicated per module.
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

_KIND_LABELS: dict[str, str] = {
    "personnel": "Personnel",
    "vehicle": "Vehicle",
    "aircraft": "Aircraft",
    "equipment": "Equipment",
}

_KIND_SEARCH_ENDPOINTS: dict[str, tuple[str, str]] = {
    # resource_type -> (endpoint path, query param name)
    "personnel": ("/api/master/personnel/search", "q"),
    "vehicle": ("/api/master/vehicles", "search"),
    "aircraft": ("/api/master/aircraft", "search"),
    "equipment": ("/api/master/equipment", "search"),
}

_KIND_RECORD_FIELD: dict[str, str] = {
    "personnel": "person_record",
    "vehicle": "vehicle_record",
    "aircraft": "aircraft_record",
    "equipment": "equipment_record",
}


def _display_label(resource_type: str, row: dict) -> str:
    if resource_type == "personnel":
        return str(row.get("name") or row.get("callsign") or "")
    if resource_type == "vehicle":
        return str(row.get("vehicle_id") or " ".join(filter(None, [row.get("make"), row.get("model")])).strip())
    if resource_type == "aircraft":
        return str(row.get("tail_number") or row.get("callsign") or row.get("aircraft_id") or "")
    if resource_type == "equipment":
        return str(row.get("name") or row.get("equipment_id") or "")
    return ""


class ResourcePickerDialog(QDialog):
    """Pick one existing master resource of any kind.

    After ``exec() == QDialog.Accepted``, read ``selected_resource_type``,
    ``selected_resource_id``, and ``selected_label``.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        allowed_kinds: tuple[str, ...] = ("personnel", "vehicle", "aircraft", "equipment"),
        exclude: tuple[tuple[str, int], ...] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Resource")
        self.resize(640, 480)
        self._allowed_kinds = allowed_kinds
        self._exclude = set(exclude)
        self.selected_resource_type: Optional[str] = None
        self.selected_resource_id: Optional[int] = None
        self.selected_label: str = ""

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Kind:"))
        self.kind_combo = QComboBox()
        for kind in allowed_kinds:
            self.kind_combo.addItem(_KIND_LABELS.get(kind, kind), kind)
        top.addWidget(self.kind_combo)
        top.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Name, ID, callsign…")
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
        return self.kind_combo.currentData() or self._allowed_kinds[0]

    def _reload(self) -> None:
        kind = self._current_kind()
        path, param = _KIND_SEARCH_ENDPOINTS[kind]
        query = self.search_edit.text().strip()
        try:
            from utils.api_client import api_client

            rows = api_client.get(path, params={param: query}) or []
        except Exception:
            rows = []
        record_field = _KIND_RECORD_FIELD[kind]
        self.table.setRowCount(0)
        for row in rows:
            rid = row.get(record_field)
            if rid is None:
                continue
            if (kind, int(rid)) in self._exclude:
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            id_item = QTableWidgetItem(str(rid))
            id_item.setData(Qt.UserRole, int(rid))
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, QTableWidgetItem(_display_label(kind, row)))
        self.table.resizeColumnsToContents()

    def _accept(self) -> None:
        sel = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        row = sel[0].row() if sel else self.table.currentRow()
        if row is None or row < 0:
            QMessageBox.information(self, "Select Resource", "Select a resource from the list.")
            return
        id_item = self.table.item(row, 0)
        label_item = self.table.item(row, 1)
        self.selected_resource_type = self._current_kind()
        self.selected_resource_id = int(id_item.data(Qt.UserRole))
        self.selected_label = label_item.text() if label_item else ""
        self.accept()
