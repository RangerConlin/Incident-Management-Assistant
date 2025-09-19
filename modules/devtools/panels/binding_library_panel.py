from __future__ import annotations

from typing import List

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
)

from ..services.binding_library import load_binding_library, BindingOption
from utils.profile_manager import profile_manager


class BindingLibraryPanel(QWidget):
    """Display the centralized catalog of bindings for quick reference."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Library")

        self._bindings: List[BindingOption] = []

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.lbl_profile = QLabel("")
        header.addWidget(self.lbl_profile)
        header.addStretch(1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter bindings…")
        self.txt_filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.txt_filter)

        self.tbl = QTableWidget(0, 3, self)
        self.tbl.setHorizontalHeaderLabels(["Key", "Source", "Description"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.itemSelectionChanged.connect(self._update_copy_enabled)
        self.tbl.itemDoubleClicked.connect(lambda *_: self._copy_selected_key())
        layout.addWidget(self.tbl, 1)

        footer = QHBoxLayout()
        self.lbl_count = QLabel("")
        footer.addWidget(self.lbl_count)
        footer.addStretch(1)
        self.btn_copy = QPushButton("Copy Key")
        self.btn_copy.clicked.connect(self._copy_selected_key)
        footer.addWidget(self.btn_copy)
        layout.addLayout(footer)

        self.btn_copy.setEnabled(False)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload bindings from the active profile catalog."""

        active = profile_manager.get_active_profile_id() or "(no active profile)"
        self.lbl_profile.setText(f"Active profile: {active}")
        try:
            bindings = load_binding_library()
        except Exception as exc:  # pragma: no cover - defensive UI path
            QMessageBox.warning(self, "Binding Library", f"Failed to load bindings: {exc}")
            bindings = []
        self._bindings = bindings
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.tbl.setRowCount(0)
        for binding in self._bindings:
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, QTableWidgetItem(binding.key))
            self.tbl.setItem(row, 1, QTableWidgetItem(binding.source))
            self.tbl.setItem(row, 2, QTableWidgetItem(binding.description))
        self.lbl_count.setText(f"{len(self._bindings)} bindings")
        self._apply_filter(self.txt_filter.text())
        first_visible = None
        for idx in range(self.tbl.rowCount()):
            if not self.tbl.isRowHidden(idx):
                first_visible = idx
                break
        if first_visible is not None:
            self.tbl.selectRow(first_visible)
        else:
            self.tbl.clearSelection()
        self._update_copy_enabled()

    def _apply_filter(self, text: str) -> None:
        query = (text or "").strip().lower()
        for row in range(self.tbl.rowCount()):
            if not query:
                self.tbl.setRowHidden(row, False)
                continue
            content = " ".join(
                self.tbl.item(row, col).text() if self.tbl.item(row, col) else ""
                for col in range(self.tbl.columnCount())
            )
            self.tbl.setRowHidden(row, query not in content.lower())
        self._update_copy_enabled()

    def _copy_selected_key(self) -> None:
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self._bindings):
            QMessageBox.information(self, "Copy Key", "Select a binding to copy.")
            return
        key = self._bindings[row].key
        QGuiApplication.clipboard().setText(key)
        QMessageBox.information(self, "Copy Key", f"Copied {key} to clipboard.")

    def _update_copy_enabled(self) -> None:
        has_selection = False
        row = self.tbl.currentRow()
        if row >= 0 and not self.tbl.isRowHidden(row):
            has_selection = True
        self.btn_copy.setEnabled(has_selection)


__all__ = ["BindingLibraryPanel"]
