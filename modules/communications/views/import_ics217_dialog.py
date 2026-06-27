from __future__ import annotations

"""Modal dialog for adding multiple channels from the master catalog to the
active incident's plan in one go, applying shared assignment defaults.

Channels are referenced by id only - this dialog never copies channel
identity fields, it just lets the user multi-select master channels and
hands their ids back to the caller (see ``get_selected_rows``).
"""

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QDialogButtonBox,
)

_PRIORITIES = ["Normal", "Primary", "Alternate", "Emergency"]


class ImportICS217Dialog(QDialog):
    def __init__(self, master_repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add from Master Library")
        self.setModal(True)
        self._repo = master_repo
        self._rows: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)

        # Filters
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Search:"))
        self.ed_search = QLineEdit()
        row1.addWidget(self.ed_search, 1)
        row1.addWidget(QLabel("System:"))
        self.cmb_system = QComboBox(); self.cmb_system.addItem("All", "")
        row1.addWidget(self.cmb_system)
        row1.addWidget(QLabel("Mode:"))
        self.cmb_mode = QComboBox(); self.cmb_mode.addItem("All", "")
        row1.addWidget(self.cmb_mode)
        row1.addWidget(QLabel("Band:"))
        self.cmb_band = QComboBox(); self.cmb_band.addItem("All", "")
        row1.addWidget(self.cmb_band)
        layout.addLayout(row1)

        # Table (multi select)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Alpha", "System", "Mode", "RX", "TX", "Function"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.table, 1)

        # Defaults applied to every channel added from this dialog
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Priority:"))
        self.def_priority = QComboBox()
        self.def_priority.addItems(_PRIORITIES)
        row2.addWidget(self.def_priority)
        layout.addLayout(row2)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire
        self.ed_search.textChanged.connect(self._refresh)
        self.cmb_system.currentIndexChanged.connect(self._apply_filters)
        self.cmb_mode.currentIndexChanged.connect(self._apply_filters)
        self.cmb_band.currentIndexChanged.connect(self._apply_filters)
        self._refresh()

    def _refresh(self):
        filters: Dict[str, Any] = {}
        if self.ed_search.text().strip():
            filters["search"] = self.ed_search.text().strip()
        self._rows = self._repo.list_channels(filters)
        self._populate_filter_options()
        self._apply_filters()

    def _populate_filter_options(self):
        for combo, key in ((self.cmb_system, "system"), (self.cmb_mode, "mode"), (self.cmb_band, "band")):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("All", "")
            for value in sorted({r.get(key) for r in self._rows if r.get(key)}):
                combo.addItem(value, value)
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _apply_filters(self):
        system = self.cmb_system.currentData()
        mode = self.cmb_mode.currentData()
        band = self.cmb_band.currentData()
        rows = [
            r for r in self._rows
            if (not system or r.get("system") == system)
            and (not mode or r.get("mode") == mode)
            and (not band or r.get("band") == band)
        ]
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            for c, key in enumerate(["display_name", "system", "mode", "rx_freq", "tx_freq", "function"]):
                item = QTableWidgetItem(str(r.get(key) or ""))
                if c in (3, 4):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == 0:
                    item.setData(Qt.UserRole, r.get("id"))
                self.table.setItem(i, c, item)
            self.table.setRowHeight(i, 22)

    def get_selected_rows(self) -> List[Any]:
        """Return the master channel ids selected for import."""
        ids: List[Any] = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                ids.append(item.data(Qt.UserRole))
        return ids

    def get_defaults(self) -> Dict[str, Any]:
        return {
            "priority": self.def_priority.currentText().strip() or "Normal",
        }


__all__ = ["ImportICS217Dialog"]
