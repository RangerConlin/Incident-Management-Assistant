"""Dialog to select a canned communication entry."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QCheckBox,
)

from bridge.catalog_bridge import CatalogBridge


class CannedCommPickerDialog(QDialog):
    """Picker for canned communication entries — Title / Team Status / Message."""

    def __init__(self, parent=None, *, catalog_bridge: CatalogBridge | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Insert Canned Communication")
        self.setModal(True)
        self.resize(680, 440)

        self._bridge = catalog_bridge or CatalogBridge()
        self._entries: list[dict] = []
        self._selected: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Search row
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by title, status or message…")
        self.search_input.setStyleSheet(
            "QLineEdit { border-radius:3px; padding:4px 8px; }"
        )
        self.search_input.textChanged.connect(self._refresh)
        search_row.addWidget(self.search_input, 1)
        self.active_only = QCheckBox("Active only")
        self.active_only.setChecked(True)
        self.active_only.toggled.connect(lambda _: self._refresh())
        search_row.addWidget(self.active_only)
        layout.addLayout(search_row)

        # Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Title", "Team Status", "Message"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            "QTableWidget { font-size:12px; }"
            "QTableWidget::item:selected { background:#3949ab; color:white; }"
            "QHeaderView::section { font-weight:700; font-size:11px; padding:4px; }"
        )
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.cellDoubleClicked.connect(lambda *_: self._accept())
        layout.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(
            "QPushButton { background:#f5f5f5; color:#616161; border:1px solid #e0e0e0;"
            " border-radius:3px; padding:5px 18px; font-weight:600; }"
        )
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._use_btn = QPushButton("⚡  Use Selected")
        self._use_btn.setEnabled(False)
        self._use_btn.setDefault(True)
        self._use_btn.setStyleSheet(
            "QPushButton { background:#1a237e; color:white; border-radius:3px;"
            " padding:5px 18px; font-weight:700; }"
            "QPushButton:disabled { background:#bdbdbd; color:#f5f5f5; }"
            "QPushButton:hover:!disabled { background:#283593; }"
        )
        self._use_btn.clicked.connect(self._accept)
        btn_row.addWidget(self._use_btn)
        layout.addLayout(btn_row)

        self._refresh()

    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        q = self.search_input.text().lower().strip()
        active_only = self.active_only.isChecked()
        try:
            all_entries = self._bridge.listCannedCommEntries("") or []
            entries = [e for e in all_entries if (not active_only or bool(e.get("is_active", 1)))]
        except Exception:
            entries = []
        if q:
            def _match(e: dict) -> bool:
                return (
                    q in (e.get("title") or "").lower()
                    or q in (e.get("status_update") or "").lower()
                    or q in (e.get("message") or "").lower()
                )
            entries = [e for e in entries if _match(e)]
        self._entries = entries
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for entry in entries:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(entry.get("title") or ""))
            self.table.setItem(r, 1, QTableWidgetItem(entry.get("status_update") or ""))
            msg = (entry.get("message") or "").replace("\n", " ")
            self.table.setItem(r, 2, QTableWidgetItem(msg))
        self.table.setSortingEnabled(True)
        self._on_selection()

    def _on_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        self._use_btn.setEnabled(bool(rows))

    def _accept(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._entries):
            self._selected = self._entries[idx]
        self.accept()

    def selected_entry(self) -> dict | None:
        return self._selected


__all__ = ["CannedCommPickerDialog"]
