"""Modeless manager window for the master hospital catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QByteArray,
    QModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QScrollArea,
)

from utils.itemview_delegates import RowOutlineSelectionDelegate

_BASE = "/api/master/hospitals"

_COLUMNS = [
    ("name",          "Name",        True),
    ("city",          "City",        True),
    ("state",         "State",       True),
    ("code",          "Code",        True),
    ("trauma_level",  "Trauma",      True),
    ("helipad",       "Helipad",     True),
    ("phone_er",      "ER Phone",    True),
    ("phone",         "Phone",       True),
    ("contact_name",  "Contact",     True),
]

_BOOL_KEYS = {"helipad", "burn_center", "pediatric_capability", "is_active"}


def _api():
    from utils.api_client import api_client
    return api_client


class _HospitalTableModel(QAbstractTableModel):
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
        val = row.get(key)
        if role == Qt.DisplayRole:
            if key in _BOOL_KEYS:
                return "Yes" if bool(val) else "No"
            return "" if val is None else str(val)
        if role == Qt.TextAlignmentRole:
            if key in _BOOL_KEYS:
                return int(Qt.AlignCenter)
            return int(Qt.AlignVCenter | Qt.AlignLeft)
        return None

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        return dict(self._rows[row]) if 0 <= row < len(self._rows) else None

    def update_record(self, row: int, data: Dict[str, Any]) -> None:
        self._rows[row] = data
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(_COLUMNS) - 1))

    def insert_record(self, data: Dict[str, Any]) -> None:
        r = len(self._rows)
        self.beginInsertRows(QModelIndex(), r, r)
        self._rows.append(data)
        self.endInsertRows()

    def remove_record(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        self._rows.pop(row)
        self.endRemoveRows()


class _FilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._needle = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def set_filter(self, text: str) -> None:
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


class _HospitalEditDialog(QDialog):
    def __init__(self, record: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._new = record is None
        self.setWindowTitle("New Hospital" if self._new else "Edit Hospital")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.e_name = QLineEdit()
        self.e_code = QLineEdit()
        self.e_address = QLineEdit()
        self.e_city = QLineEdit()
        self.e_state = QLineEdit(); self.e_state.setMaximumWidth(80)
        self.e_zip = QLineEdit(); self.e_zip.setMaximumWidth(100)
        self.e_phone_er = QLineEdit(); self.e_phone_er.setPlaceholderText("ER / main emergency line")
        self.e_phone = QLineEdit(); self.e_phone.setPlaceholderText("General")
        self.e_contact_name = QLineEdit()
        self.e_trauma_level = QComboBox()
        self.e_trauma_level.addItems(["", "I", "II", "III", "IV", "V", "Pediatric"])
        self.e_helipad = QCheckBox("Helipad available")
        self.e_burn = QCheckBox("Burn center")
        self.e_peds = QCheckBox("Pediatric capability")
        self.e_active = QCheckBox("Active")
        self.e_active.setChecked(True)
        self.e_notes = QLineEdit()

        form.addRow("Name *", self.e_name)
        form.addRow("Code", self.e_code)
        form.addRow("Address", self.e_address)
        form.addRow("City", self.e_city)
        form.addRow("State", self.e_state)
        form.addRow("ZIP", self.e_zip)
        form.addRow("ER Phone", self.e_phone_er)
        form.addRow("Phone", self.e_phone)
        form.addRow("Contact", self.e_contact_name)
        form.addRow("Trauma Level", self.e_trauma_level)
        form.addRow("", self.e_helipad)
        form.addRow("", self.e_burn)
        form.addRow("", self.e_peds)
        form.addRow("", self.e_active)
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
        self.e_code.setText(str(r.get("code") or ""))
        self.e_address.setText(str(r.get("address") or ""))
        self.e_city.setText(str(r.get("city") or ""))
        self.e_state.setText(str(r.get("state") or ""))
        self.e_zip.setText(str(r.get("zip") or ""))
        self.e_phone_er.setText(str(r.get("phone_er") or ""))
        self.e_phone.setText(str(r.get("phone") or ""))
        self.e_contact_name.setText(str(r.get("contact_name") or ""))
        trauma = str(r.get("trauma_level") or "")
        i = self.e_trauma_level.findText(trauma)
        self.e_trauma_level.setCurrentIndex(i if i >= 0 else 0)
        self.e_helipad.setChecked(bool(r.get("helipad")))
        self.e_burn.setChecked(bool(r.get("burn_center")))
        self.e_peds.setChecked(bool(r.get("pediatric_capability")))
        self.e_active.setChecked(bool(r.get("is_active", True)))
        self.e_notes.setText(str(r.get("notes") or ""))

    def _on_accept(self) -> None:
        if not self.e_name.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        self.accept()

    def payload(self) -> Dict[str, Any]:
        return {
            "name": self.e_name.text().strip(),
            "code": self.e_code.text().strip() or None,
            "address": self.e_address.text().strip() or None,
            "city": self.e_city.text().strip() or None,
            "state": self.e_state.text().strip() or None,
            "zip": self.e_zip.text().strip() or None,
            "phone_er": self.e_phone_er.text().strip() or None,
            "phone": self.e_phone.text().strip() or None,
            "contact_name": self.e_contact_name.text().strip() or None,
            "trauma_level": self.e_trauma_level.currentText() or None,
            "helipad": self.e_helipad.isChecked(),
            "burn_center": self.e_burn.isChecked(),
            "pediatric_capability": self.e_peds.isChecked(),
            "is_active": self.e_active.isChecked(),
            "notes": self.e_notes.text().strip() or None,
        }


class HospitalManagerDialog(QMainWindow):
    """Modeless window for managing the master hospital catalog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hospital Manager")
        self.resize(1000, 620)
        self._model = _HospitalTableModel(self)
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

        title = QLabel("Hospital Manager")
        f = title.font(); f.setPointSize(14); f.setBold(True); title.setFont(f)
        layout.addWidget(title)

        tb = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_edit = QPushButton("Edit")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_delete = QPushButton("Delete")
        self.btn_refresh = QPushButton("Refresh")
        for btn in (self.btn_new, self.btn_edit, self.btn_duplicate, self.btn_delete, self.btn_refresh):
            tb.addWidget(btn)
        tb.addStretch(1)
        tb.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search hospitals...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(240)
        tb.addWidget(self.search_edit)
        layout.addLayout(tb)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self._sel_delegate = RowOutlineSelectionDelegate(self.table, QColor("#FFFFFF"))
        self.table.setItemDelegate(self._sel_delegate)
        layout.addWidget(self.table, 1)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        self.btn_new.clicked.connect(self._on_new)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_duplicate.clicked.connect(self._on_duplicate)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.search_edit.textChanged.connect(lambda t: (self._proxy.set_filter(t), self._update_count()))
        self.table.doubleClicked.connect(lambda _: self._on_edit())
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self._update_buttons()

    def refresh(self) -> None:
        try:
            rows = _api().get(_BASE) or []
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load hospitals:\n{exc}")
            rows = []
        self._model.load(rows)
        self._update_count()

    def _selected_source_row(self) -> Optional[int]:
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return None
        return self._proxy.mapToSource(idxs[0]).row()

    def _selected_source_rows(self) -> List[int]:
        return [self._proxy.mapToSource(i).row() for i in self.table.selectionModel().selectedRows()]

    def _update_buttons(self) -> None:
        rows = self._selected_source_rows()
        self.btn_edit.setEnabled(len(rows) == 1)
        self.btn_duplicate.setEnabled(len(rows) == 1)
        self.btn_delete.setEnabled(bool(rows))

    def _update_count(self) -> None:
        total = self._model.rowCount()
        shown = self._proxy.rowCount()
        self.count_label.setText(f"{shown} of {total} hospitals" if shown != total else f"{total} hospitals")

    def _on_new(self) -> None:
        dlg = _HospitalEditDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            created = _api().post(_BASE, json=dlg.payload())
            self._model.insert_record(created)
            self._update_count()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to create hospital:\n{exc}")

    def _on_edit(self) -> None:
        row = self._selected_source_row()
        if row is None:
            return
        rec = self._model.record_at(row)
        dlg = _HospitalEditDialog(record=rec, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        hospital_id = rec.get("id")
        if hospital_id is None:
            return
        try:
            updated = _api().patch(f"{_BASE}/{hospital_id}", json=dlg.payload())
            self._model.update_record(row, updated)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update hospital:\n{exc}")

    def _on_duplicate(self) -> None:
        row = self._selected_source_row()
        if row is None:
            return
        rec = dict(self._model.record_at(row))
        rec.pop("id", None)
        rec["name"] = (rec.get("name") or "") + " (Copy)"
        dlg = _HospitalEditDialog(record=rec, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            created = _api().post(_BASE, json=dlg.payload())
            self._model.insert_record(created)
            self._update_count()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to duplicate hospital:\n{exc}")

    def _on_delete(self) -> None:
        rows = self._selected_source_rows()
        if not rows:
            return
        count = len(rows)
        prompt = "Delete the selected hospital?" if count == 1 else f"Delete {count} hospitals?"
        if QMessageBox.question(self, "Confirm Delete", prompt) != QMessageBox.Yes:
            return
        failed = 0
        for row in sorted(rows, reverse=True):
            rec = self._model.record_at(row)
            hospital_id = rec.get("id") if rec else None
            if hospital_id is None:
                continue
            try:
                _api().delete(f"{_BASE}/{hospital_id}")
                self._model.remove_record(row)
            except Exception:
                failed += 1
        self._update_count()
        if failed:
            QMessageBox.warning(self, "Delete", f"{failed} hospital(s) could not be deleted.")


__all__ = ["HospitalManagerDialog"]
