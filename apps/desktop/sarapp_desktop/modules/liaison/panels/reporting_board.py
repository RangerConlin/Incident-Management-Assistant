"""Reporting Board — the LOFR's curated, customer-facing status digest.

Ops/Planning push a resolution note here (from a Task or Objective, or a
standalone entry) when something is worth telling an external agency. The
LOFR then rewrites it into customer-safe language and gates it behind a
Ready to Report toggle before it's ever shared outward.
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
from utils.itemview_delegates import RowOutlineSelectionDelegate
from utils.styles import get_palette, liaison_report_state_colors, subscribe_theme

HEADERS = ["Type", "Source", "Status", "Customer-Facing Summary", "Submitted By", "Last Updated"]
STATUS_NEW = "New"
STATUS_IN_PROGRESS = "In Progress"
STATUS_READY = "Ready"


def _digest_status(digest: dict[str, Any]) -> str:
    if digest.get("ready_to_report"):
        return STATUS_READY
    if str(digest.get("lofr_summary") or "").strip():
        return STATUS_IN_PROGRESS
    return STATUS_NEW


class CreateEntryDialog(QDialog):
    """Add a Reporting Board entry: either linked to a live Task/Objective, or standalone."""

    def __init__(self, incident_id: object | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.setWindowTitle("Create Reporting Board Entry")
        layout = QVBoxLayout(self)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Source Type:"))
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["Manual", "Objective", "Task"])
        self.type_combo.currentTextChanged.connect(self._reload_sources)
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox(self)
        source_row.addWidget(self.source_combo, 1)
        layout.addLayout(source_row)

        layout.addWidget(QLabel("Note (what happened — this is internal; the LOFR will rewrite it for the customer):"))
        self.note_edit = QTextEdit(self)
        layout.addWidget(self.note_edit, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._reload_sources(self.type_combo.currentText())

    def _reload_sources(self, source_type: str) -> None:
        self.source_combo.clear()
        self.source_combo.setEnabled(source_type != "Manual")
        if source_type == "Manual":
            return
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

    def accept(self) -> None:  # type: ignore[override]
        if not self.note_edit.toPlainText().strip():
            QMessageBox.warning(self, "Note Required", "Enter a note describing what happened.")
            return
        if self.type_combo.currentText() != "Manual" and self.source_combo.currentData() is None:
            QMessageBox.warning(self, "Source Required", "Select a source, or switch Source Type to Manual.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        source_type = self.type_combo.currentText()
        source_id = self.source_combo.currentData() if source_type != "Manual" else None
        return {
            "source_type": source_type.lower() if source_type != "Manual" else None,
            "source_id": str(source_id) if source_id is not None else None,
            "raw_note": self.note_edit.toPlainText().strip(),
        }


class DigestDetailDialog(QDialog):
    def __init__(self, digest: dict[str, Any], incident_id: object | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.digest = digest
        self.incident_id = incident_id
        self.setWindowTitle(f"Reporting Digest — {digest.get('source_title') or 'Manual Entry'}")
        self.resize(600, 500)
        layout = QVBoxLayout(self)

        source_type = str(digest.get("source_type") or "").title() or "Manual"
        source_title = digest.get("source_title") or ""
        source_line = f"Source: {source_type}" + (f" — {source_title}" if source_title else "")
        layout.addWidget(QLabel(source_line))
        submitted_by = digest.get("submitted_by") or "Unknown"
        layout.addWidget(QLabel(f"Submitted by: {submitted_by}  •  Last updated: {digest.get('updated_at', '')}"))

        layout.addWidget(QLabel("Note from Ops/Planning (read-only):"))
        self.note_view = QTextEdit(self)
        self.note_view.setPlainText(digest.get("raw_note", ""))
        self.note_view.setReadOnly(True)
        self.note_view.setMaximumHeight(100)
        layout.addWidget(self.note_view)

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
        try:
            pal = get_palette()
            color = pal.get("ctrl_focus", pal.get("accent"))
            self._outline_delegate = RowOutlineSelectionDelegate(self.table, color)
            self.table.setItemDelegate(self._outline_delegate)
        except Exception:
            self._outline_delegate = None

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search Reporting Board...")
        self.search.textChanged.connect(self._apply_search)

        toolbar = QHBoxLayout()
        create_btn = QPushButton("+ Create Entry", self)
        create_btn.clicked.connect(self._create_entry)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(create_btn)
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
            status = _digest_status(digest)
            values = [
                str(digest.get("source_type") or "Manual").title(),
                str(digest.get("source_title") or ""),
                status,
                str(digest.get("lofr_summary") or "")[:120],
                str(digest.get("submitted_by") or ""),
                str(digest.get("updated_at") or ""),
            ]
            items = [QStandardItem(v) for v in values]
            items[0].setData(int(digest["int_id"]), Qt.UserRole)
            state_key = "ready" if status == STATUS_READY else "not_ready"
            brushes = colors.get(state_key)
            if brushes and status != STATUS_NEW:
                # Color only the Status cell the badge represents, not the
                # whole row, so the tint stays legible against other columns.
                items[2].setBackground(brushes["bg"])
                items[2].setForeground(brushes["fg"])
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

    def _create_entry(self) -> None:
        dialog = CreateEntryDialog(self.incident_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        try:
            from utils.state import AppState

            submitted_by = str(AppState.get_active_user_display() or "")
        except Exception:
            submitted_by = ""
        try:
            liaison_repo.create_reporting_digest(
                values["raw_note"],
                source_type=values["source_type"],
                source_id=values["source_id"],
                submitted_by=submitted_by,
                incident_id=self.incident_id,
            )
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Create Entry", f"Failed to create entry:\n{exc}")

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
        if QMessageBox.question(
            self,
            "Remove from Reporting Board",
            "Remove this digest from the Reporting Board? This does not affect the source Objective/Task.",
        ) != QMessageBox.Yes:
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
