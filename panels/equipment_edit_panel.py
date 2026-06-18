"""Equipment master catalog editor — MongoDB-backed via API."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.itemview_delegates import RowOutlineSelectionDelegate

log = logging.getLogger(__name__)

_BASE = "/api/master/equipment"

EQUIPMENT_TYPES: Tuple[str, ...] = (
    "Radio",
    "Medical",
    "Tool",
    "Other",
    "Communications",
    "Protective Gear",
    "Electronics",
    "Lighting",
    "Navigation",
    "Support Equipment",
)

CONDITION_OPTIONS: Tuple[str, ...] = (
    "Serviceable",
    "Needs Repair",
    "Out of Service",
    "Unknown",
)

_COLUMNS: List[Tuple[str, str]] = [
    ("name",          "Name"),
    ("type",          "Type"),
    ("id_number",     "ID Number"),
    ("serial_number", "Serial Number"),
    ("condition",     "Condition"),
    ("notes",         "Notes"),
]


def _api():
    from utils.api_client import api_client
    return api_client


class _EquipmentTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def load(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = _COLUMNS[index.column()][0]
        if role == Qt.DisplayRole:
            return str(row.get(key) or "")
        return None

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        return dict(self._rows[row]) if 0 <= row < len(self._rows) else None

    def insert_record(self, data: Dict[str, Any]) -> None:
        r = len(self._rows)
        self.beginInsertRows(QModelIndex(), r, r)
        self._rows.append(data)
        self.endInsertRows()

    def update_record(self, row: int, data: Dict[str, Any]) -> None:
        self._rows[row] = data
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(_COLUMNS) - 1))

    def remove_record(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        self._rows.pop(row)
        self.endRemoveRows()


class _FilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._needle = ""

    def set_pattern(self, text: str) -> None:
        self._needle = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._needle:
            return True
        m = self.sourceModel()
        for col in range(m.columnCount()):
            val = m.data(m.index(source_row, col, source_parent), Qt.DisplayRole)
            if val and self._needle in str(val).lower():
                return True
        return False


class _EquipmentEditDialog(QDialog):
    def __init__(self, record: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Equipment" if record is None else "Edit Equipment")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.e_name = QLineEdit()
        self.e_type = QComboBox(); self.e_type.addItems([""] + list(EQUIPMENT_TYPES))
        self.e_id_number = QLineEdit()
        self.e_serial = QLineEdit()
        self.e_condition = QComboBox(); self.e_condition.addItems(list(CONDITION_OPTIONS))
        self.e_notes = QTextEdit(); self.e_notes.setFixedHeight(64)

        form.addRow("Name *", self.e_name)
        form.addRow("Type", self.e_type)
        form.addRow("ID Number", self.e_id_number)
        form.addRow("Serial Number", self.e_serial)
        form.addRow("Condition", self.e_condition)
        form.addRow("Notes", self.e_notes)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if record:
            self._load(record)

    def _load(self, r: Dict[str, Any]) -> None:
        self.e_name.setText(str(r.get("name") or ""))
        i = self.e_type.findText(str(r.get("type") or ""))
        self.e_type.setCurrentIndex(i if i >= 0 else 0)
        self.e_id_number.setText(str(r.get("id_number") or ""))
        self.e_serial.setText(str(r.get("serial_number") or ""))
        i = self.e_condition.findText(str(r.get("condition") or ""))
        self.e_condition.setCurrentIndex(i if i >= 0 else 0)
        self.e_notes.setPlainText(str(r.get("notes") or ""))

    def _on_accept(self) -> None:
        if not self.e_name.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        self.accept()

    def payload(self) -> Dict[str, Any]:
        return {
            "name": self.e_name.text().strip(),
            "type": self.e_type.currentText() or None,
            "id_number": self.e_id_number.text().strip() or None,
            "serial_number": self.e_serial.text().strip() or None,
            "condition": self.e_condition.currentText() or None,
            "notes": self.e_notes.toPlainText().strip() or None,
        }


class EquipmentEditPanel(QMainWindow):
    """Master equipment catalog editor (MongoDB-backed)."""

    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equipment")
        self.resize(900, 580)
        self._model = _EquipmentTableModel(self)
        self._proxy = _FilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Equipment")
        f = title.font(); f.setPointSize(14); f.setBold(True); title.setFont(f)
        layout.addWidget(title)

        tb = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_delete = QPushButton("Delete")
        self.btn_refresh = QPushButton("Refresh")
        for btn in (self.btn_add, self.btn_edit, self.btn_delete, self.btn_refresh):
            tb.addWidget(btn)
        tb.addStretch(1)
        tb.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter equipment...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(220)
        tb.addWidget(self.search_edit)
        layout.addLayout(tb)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self._sel_delegate = RowOutlineSelectionDelegate(self.table, QColor("#FFFFFF"))
        self.table.setItemDelegate(self._sel_delegate)
        layout.addWidget(self.table, 1)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.search_edit.textChanged.connect(self._on_search)
        self.table.doubleClicked.connect(lambda _: self._on_edit())
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self._update_buttons()

    def refresh(self) -> None:
        try:
            rows = _api().get(_BASE) or []
        except Exception as exc:
            log.warning("Failed to load equipment: %s", exc)
            rows = []
        self._model.load(rows)
        self._update_count()

    def _selected_source_row(self) -> Optional[int]:
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return None
        return self._proxy.mapToSource(idxs[0]).row()

    def _update_buttons(self) -> None:
        has = self._selected_source_row() is not None
        self.btn_edit.setEnabled(has)
        self.btn_delete.setEnabled(has)

    def _update_count(self) -> None:
        total = self._model.rowCount()
        shown = self._proxy.rowCount()
        self.count_label.setText(f"{shown} of {total} items" if shown != total else f"{total} items")

    def _on_search(self, text: str) -> None:
        self._proxy.set_pattern(text)
        self._update_count()

    def _on_add(self) -> None:
        dlg = _EquipmentEditDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            created = _api().post(_BASE, json=dlg.payload())
            self._model.insert_record(created)
            self._update_count()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to create equipment:\n{exc}")

    def _on_edit(self) -> None:
        row = self._selected_source_row()
        if row is None:
            return
        rec = self._model.record_at(row)
        dlg = _EquipmentEditDialog(record=rec, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        eq_id = rec.get("id")
        if eq_id is None:
            return
        try:
            updated = _api().patch(f"{_BASE}/{eq_id}", json=dlg.payload())
            self._model.update_record(row, updated)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update equipment:\n{exc}")

    def _on_delete(self) -> None:
        row = self._selected_source_row()
        if row is None:
            return
        rec = self._model.record_at(row)
        name = rec.get("name") or "this item"
        if QMessageBox.question(self, "Confirm Delete", f"Delete '{name}'?") != QMessageBox.Yes:
            return
        eq_id = rec.get("id")
        if eq_id is None:
            return
        try:
            _api().delete(f"{_BASE}/{eq_id}")
            self._model.remove_record(row)
            self._update_count()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete equipment:\n{exc}")
