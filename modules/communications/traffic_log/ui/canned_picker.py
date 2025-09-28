from __future__ import annotations

"""Dialog to select a canned communication entry and return it to caller."""

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QCheckBox,
)

from bridge.catalog_bridge import CatalogBridge


class CannedCommPickerDialog(QDialog):
    """Simple picker for canned communication entries.

    Returns the selected entry via ``selected_entry()`` when accepted.
    """

    def __init__(self, parent=None, *, catalog_bridge: CatalogBridge | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Insert Canned Communication")
        self.setModal(True)
        self.resize(800, 520)

        self._bridge = catalog_bridge or CatalogBridge()
        self._entries: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search + filters row
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        search_row.addWidget(QLabel("Search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find by title, category or message…")
        self.search_input.textChanged.connect(self._refresh)
        search_row.addWidget(self.search_input, 1)
        self.active_only = QCheckBox("Active only")
        self.active_only.setChecked(True)
        self.active_only.toggled.connect(lambda _checked: self._refresh())
        search_row.addWidget(self.active_only)
        layout.addLayout(search_row)

        # Table of entries
        self.table = QTableWidget(0, 4)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalHeaderLabels(["Title", "Category", "Priority", "Message"])
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self._accept_if_valid())
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._refresh()
        self._update_buttons()

    # ------------------------------------------------------------------
    def selected_entry(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        row_index = rows[0].row()
        # Resolve entry by stable id stored in UserRole on the first column
        try:
            id_item = self.table.item(row_index, 0)
            entry_id = id_item.data(Qt.UserRole) if id_item is not None else None
            if entry_id is None and id_item is not None:
                # fallback to text if role not set
                entry_id = id_item.text()
            if entry_id is not None:
                try:
                    target = int(entry_id)
                except Exception:
                    target = entry_id
                for e in self._entries:
                    if int(e.get("id", -1)) == target:
                        return e
        except Exception:
            pass
        # Fallback: index-based mapping (may be incorrect if user-sorted)
        if 0 <= row_index < len(self._entries):
            return self._entries[row_index]
        return None

    # ------------------------------------------------------------------
    def _accept_if_valid(self) -> None:
        if self.selected_entry() is None:
            return
        self.accept()

    def _update_buttons(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(self.selected_entry() is not None)

    def _refresh(self) -> None:
        query = self.search_input.text().strip()
        try:
            entries = self._bridge.listCannedCommEntries(query)
        except Exception:
            entries = []
        if self.active_only.isChecked():
            entries = [e for e in entries if bool(e.get("is_active", True))]
        # Sort by title, then id
        entries = sorted(entries, key=lambda e: (str(e.get("title") or "").lower(), int(e.get("id") or 0)))
        self._entries = entries
        self._populate(entries)

    def _populate(self, entries: List[dict]) -> None:
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            title = str(entry.get("title") or "")
            category = str(entry.get("category") or "")
            priority = str(entry.get("priority") or "")
            message = str(entry.get("message") or "")
            # Basic trimming for display purposes
            if len(message) > 160:
                message = message[:157] + "…"
            for col, value in enumerate((title, category, priority, message)):
                item = QTableWidgetItem(value)
                if col == 0:
                    # Store id for stable selection retrieval regardless of sort order
                    item.setData(Qt.UserRole, entry.get("id"))
                if col == 3:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self._update_buttons()


__all__ = ["CannedCommPickerDialog"]
