"""Reporting Board — the LOFR's curated, customer-facing status digest.

Lets the Liaison Officer pull a live Objective or Task status/result, then
write (and gate behind a Ready to Report toggle) the version that's actually
safe to hand to an external customer.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel

from modules.liaison import repository as liaison_repo
from utils.styles import liaison_report_state_colors, subscribe_theme

HEADERS = ["Type", "Source", "Customer-Facing Summary", "Ready?", "Last Synced"]


class SourcePickerDialog(QDialog):
    """Pick a live Objective or Task to pull into the Reporting Board."""

    def __init__(self, incident_id: object | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.setWindowTitle("Pull Status for Reporting")
        layout = QVBoxLayout(self)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Source Type:"))
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["Objective", "Task"])
        self.type_combo.currentTextChanged.connect(self._reload_sources)
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox(self)
        source_row.addWidget(self.source_combo, 1)
        layout.addLayout(source_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._reload_sources(self.type_combo.currentText())

    def _reload_sources(self, source_type: str) -> None:
        self.source_combo.clear()
        try:
            if source_type == "Objective":
                from modules.command.models.objectives import ApiObjectiveRepository

                repo = ApiObjectiveRepository(str(self.incident_id))
                for obj in repo.list_objectives():
                    self.source_combo.addItem(f"{obj.code} — {obj.text}", obj.id)
            else:
                from modules.operations.taskings.repository import list_tasks

                for task in list_tasks():
                    label = f"{task.get('task_id') or task.get('int_id')} — {task.get('title', '')}"
                    self.source_combo.addItem(label, task.get("int_id"))
        except Exception as exc:
            QMessageBox.warning(self, "Load Sources", f"Failed to load sources:\n{exc}")

    def values(self) -> dict[str, Any] | None:
        source_id = self.source_combo.currentData()
        if source_id is None:
            return None
        return {
            "source_type": self.type_combo.currentText().lower(),
            "source_id": str(source_id),
        }


class DigestDetailDialog(QDialog):
    def __init__(self, digest: dict[str, Any], incident_id: object | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.digest = digest
        self.incident_id = incident_id
        self.setWindowTitle(f"Reporting Digest — {digest.get('source_title', '')}")
        self.resize(600, 500)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Source: {digest.get('source_type', '').title()} — {digest.get('source_title', '')}"))
        layout.addWidget(QLabel(f"Last synced: {digest.get('last_synced_at', '')}"))

        layout.addWidget(QLabel("Live status (auto-pulled, read-only):"))
        self.auto_view = QTextEdit(self)
        self.auto_view.setPlainText(digest.get("auto_summary", ""))
        self.auto_view.setReadOnly(True)
        self.auto_view.setMaximumHeight(100)
        layout.addWidget(self.auto_view)

        resync_btn = QPushButton("Re-sync from Source", self)
        resync_btn.clicked.connect(self._resync)
        layout.addWidget(resync_btn, alignment=Qt.AlignLeft)

        layout.addWidget(QLabel("Customer-facing summary (editable — this is what gets shared):"))
        self.customer_edit = QTextEdit(self)
        self.customer_edit.setPlainText(digest.get("lofr_summary", ""))
        layout.addWidget(self.customer_edit, 1)

        self.ready_check = QCheckBox("Ready to Report", self)
        self.ready_check.setChecked(bool(digest.get("ready_to_report")))
        layout.addWidget(self.ready_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _resync(self) -> None:
        try:
            self.digest = liaison_repo.resync_reporting_digest(self.digest["int_id"], self.incident_id)
            self.auto_view.setPlainText(self.digest.get("auto_summary", ""))
        except Exception as exc:
            QMessageBox.critical(self, "Re-sync", f"Failed to re-sync:\n{exc}")

    def _save(self) -> None:
        try:
            liaison_repo.update_reporting_digest(
                self.digest["int_id"],
                {
                    "lofr_summary": self.customer_edit.toPlainText().strip(),
                    "ready_to_report": self.ready_check.isChecked(),
                },
                self.incident_id,
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Digest", f"Failed to save:\n{exc}")


class ReportingBoard(QWidget):
    """List of curated reporting digests, color-coded by Ready-to-Report state."""

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.model = QStandardItemModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(lambda _idx: self._open_selected())

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search Reporting Board...")
        self.search.textChanged.connect(self._apply_search)

        toolbar = QHBoxLayout()
        pull_objective_btn = QPushButton("+ Pull Status", self)
        pull_objective_btn.clicked.connect(self._pull_source)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(pull_objective_btn)
        toolbar.addWidget(refresh_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.model.setHorizontalHeaderLabels(HEADERS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self._digests_cache: list[dict[str, Any]] = []
        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass
        self.reload()

    def _on_theme_changed(self, _name: str) -> None:
        self._render_rows(self._digests_cache)

    def reload(self) -> None:
        try:
            self._digests_cache = liaison_repo.fetch_reporting_digests(self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Reporting Board", f"Failed to load digests:\n{exc}")
            self._digests_cache = []
        self._render_rows(self._digests_cache)

    def _render_rows(self, digests: list[dict[str, Any]]) -> None:
        self.model.removeRows(0, self.model.rowCount())
        colors = liaison_report_state_colors()
        for digest in digests:
            ready = bool(digest.get("ready_to_report"))
            values = [
                str(digest.get("source_type", "")).title(),
                str(digest.get("source_title", "")),
                str(digest.get("lofr_summary", ""))[:120],
                "Yes" if ready else "No",
                str(digest.get("last_synced_at", "")),
            ]
            items = [QStandardItem(v) for v in values]
            items[0].setData(int(digest["int_id"]), Qt.UserRole)
            state_key = "ready" if ready else "not_ready"
            brushes = colors.get(state_key)
            if brushes:
                for item in items:
                    item.setBackground(brushes["bg"])
                    item.setForeground(brushes["fg"])
            self.model.appendRow(items)
        self.table.resizeColumnsToContents()

    def _apply_search(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.model.rowCount()):
            visible = not needle or any(
                needle in str(self.model.item(row, col).text()).lower()
                for col in range(self.model.columnCount())
            )
            self.table.setRowHidden(row, not visible)

    def _selected_digest_id(self) -> int | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.model.item(indexes[0].row(), 0)
        value = item.data(Qt.UserRole) if item else None
        return int(value) if value is not None else None

    def _selected_digest(self) -> dict[str, Any] | None:
        digest_id = self._selected_digest_id()
        if digest_id is None:
            return None
        return next((d for d in self._digests_cache if d.get("int_id") == digest_id), None)

    def _open_selected(self) -> None:
        digest = self._selected_digest()
        if digest is None:
            return
        dialog = DigestDetailDialog(digest, self.incident_id, self)
        dialog.exec()
        self.reload()

    def _pull_source(self) -> None:
        dialog = SourcePickerDialog(self.incident_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        if not values:
            return
        try:
            liaison_repo.create_reporting_digest(
                values["source_type"], values["source_id"], incident_id=self.incident_id
            )
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Pull Status", f"Failed to pull status:\n{exc}")

    def _show_context_menu(self, position) -> None:
        if self.table.indexAt(position).row() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Open / Edit", self._open_selected)
        menu.addAction("Remove from Reporting Board", self._delete_selected)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _delete_selected(self) -> None:
        digest_id = self._selected_digest_id()
        if digest_id is None:
            return
        try:
            liaison_repo.delete_reporting_digest(digest_id, self.incident_id)
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Remove Digest", f"Failed to remove:\n{exc}")


def get_reporting_panel(incident_id: object | None = None) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Liaison Reporting Board")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(ReportingBoard(incident_id, panel))
    return panel
