"""ICS-217 Communications Resource editor — MongoDB-backed via API."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

log = logging.getLogger(__name__)

_BASE = "/api/comms/master-channels"

# (api_key, header_label, visible)
_COLUMNS: List[Tuple[str, str, bool]] = [
    ("name",     "Channel Name", True),
    ("function", "Function / Use", True),
    ("rx_freq",  "RX Freq (MHz)", True),
    ("rx_tone",  "RX Tone / NAC", True),
    ("tx_freq",  "TX Freq (MHz)", True),
    ("tx_tone",  "TX Tone / NAC", True),
    ("system",   "System / Network", True),
    ("mode",     "Mode", True),
    ("notes",    "Notes", True),
    ("line_a",   "Line A", False),
    ("line_c",   "Line C", False),
    ("band",     "Band", False),
]

_KEY = [c[0] for c in _COLUMNS]
_LABEL = {c[0]: c[1] for c in _COLUMNS}
_VISIBLE = {c[0]: c[2] for c in _COLUMNS}

MODE_OPTIONS = ["FM", "AM", "A", "D", "M"]
FREQ_RE = re.compile(r"^\d{2,4}\.\d{3,}$")


def _api():
    from utils.api_client import api_client
    return api_client


def _bool_display(val) -> str:
    return "Yes" if val else "No"


# ---------------------------------------------------------------------------
# Table model
# ---------------------------------------------------------------------------

class _ChannelTableModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def load(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._rows) if not parent.isValid() else 0

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(_COLUMNS) if not parent.isValid() else 0

    def headerData(self, section: int, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return _COLUMNS[section][1]
        return None

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = _KEY[index.column()]
        val = row.get(key)
        if role == QtCore.Qt.DisplayRole:
            if key in ("line_a", "line_c"):
                return _bool_display(val)
            return "" if val is None else str(val)
        if role == QtCore.Qt.UserRole:
            return val
        return None

    def record_at(self, row: int) -> Dict[str, Any]:
        return dict(self._rows[row])

    def update_record(self, row: int, data: Dict[str, Any]) -> None:
        self._rows[row] = data
        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, len(_COLUMNS) - 1),
        )

    def insert_record(self, data: Dict[str, Any]) -> None:
        r = len(self._rows)
        self.beginInsertRows(QtCore.QModelIndex(), r, r)
        self._rows.append(data)
        self.endInsertRows()

    def remove_record(self, row: int) -> None:
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self._rows.pop(row)
        self.endRemoveRows()


# ---------------------------------------------------------------------------
# Filter proxy
# ---------------------------------------------------------------------------

class _FilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern = ""
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

    def set_pattern(self, text: str) -> None:
        self._pattern = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        if not self._pattern:
            return True
        m = self.sourceModel()
        for col in range(m.columnCount()):
            val = m.data(m.index(source_row, col, source_parent), QtCore.Qt.DisplayRole)
            if val and self._pattern in str(val).lower():
                return True
        return False


# ---------------------------------------------------------------------------
# Detail dialog
# ---------------------------------------------------------------------------

class _ChannelDetailDialog(QtWidgets.QDialog):
    def __init__(self, record: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._new = record is None
        self.setWindowTitle("New Channel" if self._new else "Edit Channel")
        self.setMinimumWidth(480)
        self._build_ui()
        if record:
            self._load(record)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self.e_name = QtWidgets.QLineEdit()
        self.e_function = QtWidgets.QLineEdit()
        self.e_rx_freq = QtWidgets.QLineEdit(); self.e_rx_freq.setPlaceholderText("e.g. 155.7525")
        self.e_rx_tone = QtWidgets.QLineEdit(); self.e_rx_tone.setPlaceholderText("e.g. 100.0 or 0x293")
        self.e_tx_freq = QtWidgets.QLineEdit(); self.e_tx_freq.setPlaceholderText("e.g. 155.7525")
        self.e_tx_tone = QtWidgets.QLineEdit()
        self.e_system = QtWidgets.QLineEdit()
        self.e_mode = QtWidgets.QComboBox(); self.e_mode.addItems(MODE_OPTIONS)
        self.e_notes = QtWidgets.QTextEdit(); self.e_notes.setFixedHeight(72)
        self.e_line_a = QtWidgets.QCheckBox("Line A restrictions apply")
        self.e_line_c = QtWidgets.QCheckBox("Line C restrictions apply")

        form.addRow("Channel Name *", self.e_name)
        form.addRow("Function / Use", self.e_function)
        form.addRow("RX Freq (MHz) *", self.e_rx_freq)
        form.addRow("RX Tone / NAC", self.e_rx_tone)
        form.addRow("TX Freq (MHz) *", self.e_tx_freq)
        form.addRow("TX Tone / NAC", self.e_tx_tone)
        form.addRow("System / Network", self.e_system)
        form.addRow("Mode *", self.e_mode)
        form.addRow("Notes", self.e_notes)
        form.addRow("", self.e_line_a)
        form.addRow("", self.e_line_c)

        layout.addLayout(form)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self, rec: Dict[str, Any]) -> None:
        self.e_name.setText(str(rec.get("name") or ""))
        self.e_function.setText(str(rec.get("function") or ""))
        self.e_rx_freq.setText(str(rec.get("rx_freq") or ""))
        self.e_rx_tone.setText(str(rec.get("rx_tone") or ""))
        self.e_tx_freq.setText(str(rec.get("tx_freq") or ""))
        self.e_tx_tone.setText(str(rec.get("tx_tone") or ""))
        self.e_system.setText(str(rec.get("system") or ""))
        mode = str(rec.get("mode") or "FM").upper()
        i = self.e_mode.findText(mode)
        self.e_mode.setCurrentIndex(i if i >= 0 else 0)
        self.e_notes.setPlainText(str(rec.get("notes") or ""))
        self.e_line_a.setChecked(bool(rec.get("line_a")))
        self.e_line_c.setChecked(bool(rec.get("line_c")))

    def _on_accept(self) -> None:
        err = self._validate()
        if err:
            QtWidgets.QMessageBox.warning(self, "Validation Error", err)
            return
        self.accept()

    def _validate(self) -> Optional[str]:
        if not self.e_name.text().strip():
            return "Channel Name is required."
        for label, widget in [("RX Freq", self.e_rx_freq), ("TX Freq", self.e_tx_freq)]:
            v = widget.text().strip()
            if not v:
                return f"{label} is required."
        return None

    def payload(self) -> Dict[str, Any]:
        return {
            "name": self.e_name.text().strip(),
            "function": self.e_function.text().strip() or None,
            "rx_freq": self.e_rx_freq.text().strip() or None,
            "rx_tone": self.e_rx_tone.text().strip() or None,
            "tx_freq": self.e_tx_freq.text().strip() or None,
            "tx_tone": self.e_tx_tone.text().strip() or None,
            "system": self.e_system.text().strip() or None,
            "mode": self.e_mode.currentText().strip(),
            "notes": self.e_notes.toPlainText().strip() or None,
            "line_a": self.e_line_a.isChecked(),
            "line_c": self.e_line_c.isChecked(),
        }


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class CommsResourceEditor(QtWidgets.QMainWindow):
    """ICS-217 Communications Resource editor (MongoDB-backed)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Communications Resources (ICS-217)")
        self.resize(1100, 600)
        self._model = _ChannelTableModel(self)
        self._proxy = _FilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._build_ui()
        self._apply_default_visibility()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        title = QtWidgets.QLabel("Communications Resources (ICS-217)")
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(line)

        # Toolbar row
        tb = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        for btn in (self.btn_add, self.btn_edit, self.btn_delete, self.btn_refresh):
            tb.addWidget(btn)
        tb.addStretch(1)
        tb.addWidget(QtWidgets.QLabel("Search:"))
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Filter channels...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(240)
        tb.addWidget(self.search_edit)
        layout.addLayout(tb)

        # Table
        self.table = QtWidgets.QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")

        from utils.itemview_delegates import RowOutlineSelectionDelegate
        self._sel_delegate = RowOutlineSelectionDelegate(self.table, QtGui.QColor("#FFFFFF"))
        self.table.setItemDelegate(self._sel_delegate)

        layout.addWidget(self.table, 1)

        # Footer
        self.count_label = QtWidgets.QLabel()
        layout.addWidget(self.count_label)

        # Connections
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.search_edit.textChanged.connect(self._on_search)
        self.table.doubleClicked.connect(lambda _: self._on_edit())
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self._update_buttons()

    def _apply_default_visibility(self) -> None:
        for col_idx, (key, _label, visible) in enumerate(_COLUMNS):
            self.table.setColumnHidden(col_idx, not visible)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        try:
            rows = _api().get(_BASE) or []
        except Exception as exc:
            log.warning("Failed to load master channels: %s", exc)
            rows = []
        self._model.load(rows)
        self._update_count()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        dlg = _ChannelDetailDialog(parent=self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            created = _api().post(_BASE, json=dlg.payload())
            self._model.insert_record(created)
            self._update_count()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to create channel:\n{exc}")

    def _on_edit(self) -> None:
        row = self._selected_source_row()
        if row is None:
            return
        rec = self._model.record_at(row)
        dlg = _ChannelDetailDialog(record=rec, parent=self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        channel_id = rec.get("id")
        if channel_id is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Cannot update: record has no ID.")
            return
        try:
            updated = _api().patch(f"{_BASE}/{channel_id}", json=dlg.payload())
            self._model.update_record(row, updated)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to update channel:\n{exc}")

    def _on_delete(self) -> None:
        row = self._selected_source_row()
        if row is None:
            return
        rec = self._model.record_at(row)
        name = rec.get("name") or "this channel"
        if QtWidgets.QMessageBox.question(
            self, "Confirm Delete", f"Delete '{name}'? This cannot be undone."
        ) != QtWidgets.QMessageBox.Yes:
            return
        channel_id = rec.get("id")
        if channel_id is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Cannot delete: record has no ID.")
            return
        try:
            _api().delete(f"{_BASE}/{channel_id}")
            self._model.remove_record(row)
            self._update_count()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to delete channel:\n{exc}")

    def _on_search(self, text: str) -> None:
        self._proxy.set_pattern(text)
        self._update_count()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        self.count_label.setText(
            f"{shown} of {total} channels" if shown != total else f"{total} channels"
        )
