"""Modern manager dialog for the master hospital catalog."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QByteArray,
    QModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from models.hospital import Hospital
from services.hospital_service import HospitalService

from .hospital_edit_dialog import HospitalEditDialog


@dataclass(frozen=True)
class _ColumnConfig:
    key: str
    label: str
    stretch: bool = False
    default_width: int | None = None


_DISPLAY_CANDIDATES = [
    _ColumnConfig("name", "Name", stretch=True),
    _ColumnConfig("city", "City"),
    _ColumnConfig("state", "State/Prov"),
    _ColumnConfig("code", "Code"),
    _ColumnConfig("trauma_level", "Trauma"),
    _ColumnConfig("helipad", "Helipad"),
    _ColumnConfig("phone_er", "ER Phone", default_width=140),
    _ColumnConfig("phone", "Phone", default_width=140),
    _ColumnConfig("contact_name", "Contact"),
]


_BOOL_FIELDS = {"helipad", "burn_center", "pediatric_capability", "is_active"}
_INT_FIELDS = {"travel_time_min", "bed_available"}


class _HospitalTableModel(QAbstractTableModel):
    def __init__(self, columns: list[_ColumnConfig], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._hospitals: list[Hospital] = []

    # --- convenience -------------------------------------------------
    def set_hospitals(self, rows: Iterable[Hospital]) -> None:
        self.beginResetModel()
        self._hospitals = list(rows)
        self.endResetModel()

    def hospital_at(self, row: int) -> Hospital | None:
        if 0 <= row < len(self._hospitals):
            return self._hospitals[row]
        return None

    def column_index(self, key: str) -> int:
        for idx, col in enumerate(self._columns):
            if col.key == key:
                return idx
        return -1

    def row_for_id(self, hospital_id: int | None) -> int:
        if hospital_id is None:
            return -1
        for idx, row in enumerate(self._hospitals):
            if row.id == hospital_id:
                return idx
        return -1

    # --- Qt model interface -----------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        if parent and parent.isValid():  # pragma: no cover - tree behaviour unused
            return 0
        return len(self._hospitals)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        if parent and parent.isValid():  # pragma: no cover - tree behaviour unused
            return 0
        return len(self._columns)

    def headerData(  # type: ignore[override]
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> str | None:
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(self._columns):
            return self._columns[section].label
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._hospitals[index.row()]
        column = self._columns[index.column()].key
        value = getattr(row, column, None)

        if role == Qt.DisplayRole:
            if column in _BOOL_FIELDS:
                if value is None:
                    return ""
                return "Yes" if bool(value) else "No"
            if value is None:
                return ""
            return str(value)
        if role == Qt.TextAlignmentRole:
            if column in _BOOL_FIELDS or column in _INT_FIELDS:
                return int(Qt.AlignCenter)
            return int(Qt.AlignVCenter | Qt.AlignLeft)
        return None


class _HospitalFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, filter_keys: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filter_keys = list(filter_keys)
        self._needle = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def set_filter_text(self, text: str) -> None:
        self._needle = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self._needle:
            return True
        model = self.sourceModel()
        if not isinstance(model, _HospitalTableModel):
            return super().filterAcceptsRow(source_row, source_parent)
        for key in self._filter_keys:
            col = model.column_index(key)
            if col < 0:
                continue
            idx = model.index(source_row, col, source_parent)
            text = model.data(idx, Qt.DisplayRole)
            if text and self._needle in str(text).lower():
                return True
        return False


class HospitalManagerDialog(QDialog):
    """Dialog that manages hospital catalog entries using a table view."""

    def __init__(
        self,
        service: HospitalService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service or HospitalService()
        self._settings = QSettings()
        self._columns = self._resolve_columns()
        self._model = _HospitalTableModel(self._columns, self)
        filter_keys = [key for key in ("name", "city", "state", "code", "contact_name") if self._column_available(key)]
        self._proxy = _HospitalFilterProxyModel(filter_keys, self)
        self._proxy.setSourceModel(self._model)
        self._total_rows = 0

        self.setWindowTitle("Hospital Manager")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- top toolbar ------------------------------------------------
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._new_button = QPushButton("New")
        self._edit_button = QPushButton("Edit")
        self._duplicate_button = QPushButton("Duplicate")
        self._delete_button = QPushButton("Delete")
        for btn in (self._new_button, self._edit_button, self._duplicate_button, self._delete_button):
            btn.setCursor(Qt.PointingHandCursor)

        toolbar.addWidget(self._new_button)
        toolbar.addWidget(self._edit_button)
        toolbar.addWidget(self._duplicate_button)
        toolbar.addWidget(self._delete_button)
        toolbar.addStretch(1)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search hospitals…")
        self._search_edit.setClearButtonEnabled(True)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search_edit)

        self._close_button = QPushButton("Close")
        self._close_button.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._close_button)

        layout.addLayout(toolbar)

        # --- table ------------------------------------------------------
        self._table = QTableView(self)
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header: QHeaderView = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionsClickable(True)
        header.setSectionResizeMode(QHeaderView.Interactive)

        for idx, column in enumerate(self._columns):
            if column.stretch:
                header.setSectionResizeMode(idx, QHeaderView.Stretch)
            elif column.default_width:
                self._table.setColumnWidth(idx, column.default_width)

        layout.addWidget(self._table)

        # --- footer -----------------------------------------------------
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        self._status_label = QLabel("Loading hospitals…")
        footer.addWidget(self._status_label)
        layout.addLayout(footer)

        # --- shortcuts --------------------------------------------------
        self._delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self._delete_shortcut.activated.connect(self._on_delete)
        self._enter_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self._enter_shortcut.activated.connect(self._on_edit_shortcut)
        self._enter_shortcut2 = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self._enter_shortcut2.activated.connect(self._on_edit_shortcut)
        self._new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self._new_shortcut.activated.connect(self._on_new)
        self._duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self._duplicate_shortcut.activated.connect(self._on_duplicate)
        self._escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._escape_shortcut.activated.connect(self.close)

        # --- signal wiring ---------------------------------------------
        self._new_button.clicked.connect(self._on_new)
        self._edit_button.clicked.connect(self._on_edit)
        self._duplicate_button.clicked.connect(self._on_duplicate)
        self._delete_button.clicked.connect(self._on_delete)
        self._close_button.clicked.connect(self.close)
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._table.doubleClicked.connect(lambda _: self._on_edit())

        sel_model = self._table.selectionModel()
        if sel_model:
            sel_model.selectionChanged.connect(lambda *_: self._update_button_states())

        self._proxy.modelReset.connect(self._update_status)
        self._proxy.rowsInserted.connect(lambda *_: self._update_status())
        self._proxy.rowsRemoved.connect(lambda *_: self._update_status())
        self._proxy.layoutChanged.connect(self._update_status)

        self._restore_state()
        self._refresh()
        self.resize(960, 600)

    # ----- helpers -----------------------------------------------------
    def _column_available(self, key: str) -> bool:
        return any(col.key == key for col in self._columns)

    def _resolve_columns(self) -> list[_ColumnConfig]:
        columns: list[_ColumnConfig] = []
        available = set(self._service.available_columns)
        for candidate in _DISPLAY_CANDIDATES:
            if candidate.key == "phone" and "phone_er" in available:
                continue
            if candidate.key not in available and candidate.key != "name":
                continue
            if candidate.key == "name":
                columns.insert(0, candidate)
            else:
                columns.append(candidate)
        # Ensure name column exists even if schema omitted it (should never happen)
        if not any(col.key == "name" for col in columns):
            columns.insert(0, _ColumnConfig("name", "Name", stretch=True))
        return columns

    def _restore_state(self) -> None:
        geometry = self._settings.value("hospital_manager/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)

        widths_value = self._settings.value("hospital_manager/column_widths")
        try:
            widths = json.loads(widths_value) if widths_value else []
        except (TypeError, ValueError):  # pragma: no cover - corrupted settings
            widths = []
        header = self._table.horizontalHeader()
        for idx, width in enumerate(widths):
            if 0 <= idx < header.count():
                try:
                    header.resizeSection(idx, int(width))
                except (TypeError, ValueError):
                    continue

        sort_section = self._settings.value("hospital_manager/sort_section")
        sort_order = self._settings.value("hospital_manager/sort_order")
        try:
            section = int(sort_section)
            order = Qt.SortOrder(int(sort_order))
            if 0 <= section < header.count():
                self._table.sortByColumn(section, order)
        except (TypeError, ValueError):
            pass

    def _save_state(self) -> None:
        self._settings.setValue("hospital_manager/geometry", self.saveGeometry())
        header = self._table.horizontalHeader()
        widths = [header.sectionSize(i) for i in range(header.count())]
        self._settings.setValue("hospital_manager/column_widths", json.dumps(widths))
        self._settings.setValue("hospital_manager/sort_section", header.sortIndicatorSection())
        sort_order = header.sortIndicatorOrder()
        try:
            sort_order_value = int(sort_order)
        except (TypeError, ValueError):
            value = getattr(sort_order, "value", None)
            sort_order_value = int(value) if value is not None else 0
        self._settings.setValue("hospital_manager/sort_order", sort_order_value)

    def _refresh(self, select_id: int | None = None) -> None:
        try:
            rows = self._service.list_hospitals()
        except sqlite3.Error as exc:  # pragma: no cover - depends on runtime DB
            QMessageBox.critical(self, "Database error", f"Unable to load hospitals: {exc}")
            rows = []
        self._model.set_hospitals(rows)
        self._total_rows = len(rows)
        self._update_status()
        if select_id:
            self._select_hospital(select_id)
        else:
            self._update_button_states()

    def _selected_hospitals(self) -> list[Hospital]:
        sel_model = self._table.selectionModel()
        if not sel_model:
            return []
        hospitals: list[Hospital] = []
        for proxy_index in sel_model.selectedRows():
            source_index = self._proxy.mapToSource(proxy_index)
            row = self._model.hospital_at(source_index.row())
            if row:
                hospitals.append(row)
        return hospitals

    def _select_hospital(self, hospital_id: int) -> None:
        row = self._model.row_for_id(hospital_id)
        if row < 0:
            return
        source_index = self._model.index(row, 0)
        proxy_index = self._proxy.mapFromSource(source_index)
        if not proxy_index.isValid():
            return
        sel_model = self._table.selectionModel()
        if not sel_model:
            return
        sel_model.clearSelection()
        sel_model.select(proxy_index, sel_model.Select | sel_model.Rows)
        self._table.scrollTo(proxy_index)
        self._update_button_states()

    def _update_button_states(self) -> None:
        selected = self._selected_hospitals()
        has_selection = bool(selected)
        single = len(selected) == 1
        self._edit_button.setEnabled(single)
        self._duplicate_button.setEnabled(single)
        self._delete_button.setEnabled(has_selection)

    def _update_status(self) -> None:
        visible = self._proxy.rowCount()
        selected = len(self._selected_hospitals())
        total = self._total_rows
        if total == visible:
            summary = f"{visible} hospital" if visible == 1 else f"{visible} hospitals"
        else:
            summary = f"Showing {visible} of {total} hospitals"
        if selected:
            summary += f" — {selected} selected"
        self._status_label.setText(summary)
        self._update_button_states()

    # ----- actions -----------------------------------------------------
    def _on_new(self) -> None:
        dialog = HospitalEditDialog(self._service, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.hospital and dialog.hospital.id:
            self._refresh(select_id=dialog.hospital.id)

    def _on_edit(self) -> None:
        selected = self._selected_hospitals()
        if len(selected) != 1:
            return
        dialog = HospitalEditDialog(self._service, hospital=selected[0], parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.hospital and dialog.hospital.id:
            self._refresh(select_id=dialog.hospital.id)

    def _on_edit_shortcut(self) -> None:
        if self._table.hasFocus():
            self._on_edit()

    def _on_duplicate(self) -> None:
        selected = self._selected_hospitals()
        if len(selected) != 1:
            return
        original = selected[0]
        duplicate = replace(original)
        duplicate.id = None
        duplicate.name = (original.name or "") + " (Copy)"
        dialog = HospitalEditDialog(self._service, hospital=duplicate, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.hospital and dialog.hospital.id:
            self._refresh(select_id=dialog.hospital.id)

    def _on_delete(self) -> None:
        selected = self._selected_hospitals()
        if not selected:
            return
        count = len(selected)
        title = "Delete Hospital" if count == 1 else "Delete Hospitals"
        prompt = "Delete the selected hospital?" if count == 1 else f"Delete {count} hospitals?"
        if QMessageBox.question(self, title, prompt) != QMessageBox.Yes:
            return
        ids = [row.id for row in selected if row.id is not None]
        try:
            self._service.delete_hospitals(ids)
        except sqlite3.Error as exc:  # pragma: no cover - depends on runtime DB
            QMessageBox.critical(self, "Database error", f"Unable to delete hospitals: {exc}")
            return
        self._refresh()

    def _on_search_changed(self, text: str) -> None:
        self._proxy.set_filter_text(text)
        self._update_status()

    # ----- Qt overrides -----------------------------------------------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_state()
        super().closeEvent(event)


__all__ = ["HospitalManagerDialog"]

