from __future__ import annotations

"""Modal dialog for importing channels from an ICS‑217‑like source.

For now, this surfaces the master catalog with filters and allows
multi‑select import applying defaults.
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


class ImportICS217Dialog(QDialog):
    def __init__(self, master_repo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from ICS‑217")
        self.setModal(True)
        self._repo = master_repo

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
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self.table, 1)

        # Defaults
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Function:"))
        self.def_function = QLineEdit2("Tactical")
        row2.addWidget(self.def_function)
        row2.addWidget(QLabel("Priority:"))
        self.def_priority = QLineEdit2("Normal")
        row2.addWidget(self.def_priority)
        layout.addLayout(row2)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire
        self.ed_search.textChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        filters: Dict[str, Any] = {}
        if self.ed_search.text().strip():
            filters["search"] = self.ed_search.text().strip()
        rows = self._repo.list_channels(filters)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            for c, key in enumerate(["display_name", "system", "mode", "rx_freq", "tx_freq", "function"]):
                item = QTableWidgetItem(str(r.get(key) or ""))
                if c in (3, 4):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, c, item)
            # stash row data
            self.table.setRowHeight(i, 22)
            for k, v in r.items():
                # no direct per-row storage in QTableWidget; attach to alpha column
                self.table.item(i, 0).setData(Qt.UserRole + 1 + hash(k) % 100, v)

    def get_selected_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx in self.table.selectionModel().selectedRows():
            # reconstruct minimal row from visible cells
            i = idx.row()
            r = {
                "id": None,
                "name": self.table.item(i, 0).text(),
                "system": self.table.item(i, 1).text(),
                "mode": self.table.item(i, 2).text(),
                "rx_freq": float(self.table.item(i, 3).text() or 0),
                "tx_freq": float(self.table.item(i, 4).text() or 0) if (self.table.item(i, 4).text() or "").strip() else None,
                "function": self.table.item(i, 5).text() or "Tactical",
                "rx_tone": None,
                "tx_tone": None,
                "notes": None,
                "line_a": 0,
                "line_c": 0,
            }
            rows.append(r)
        return rows

    def get_defaults(self) -> Dict[str, Any]:
        return {
            "priority": self.def_priority.text().strip() or "Normal",
        }


class QLineEdit2(QLineEdit):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)

