"""Release manager window and panel for Public Information releases."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QComboBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from modules.public_information.dialogs.release_editor_dialog import ReleaseEditorDialog
from modules.public_information.models.constants import MESSAGE_STATUSES
from modules.public_information.services import PublicInformationRepository
from modules.public_information.services.release_workflow import is_actionable_status
from modules.public_information.widgets.common import fill_table, selected_row_data
from utils.table_view_styles import apply_statusboard_table_behavior


class ReleaseManagerPanel(QWidget):
    changed = Signal()

    def __init__(self, repo: PublicInformationRepository, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user or {}

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New Release")
        self.open_button = QPushButton("Open Selected")
        self.refresh_button = QPushButton("Refresh")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Releases", "Needs Action", *MESSAGE_STATUSES])
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search titles, types, audiences, or names")
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.filter_combo)
        toolbar.addWidget(self.search_edit, 1)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_selected())
        layout.addWidget(self.table, 1)

        self.new_button.clicked.connect(self.create_new_release)
        self.open_button.clicked.connect(self.open_selected)
        self.refresh_button.clicked.connect(self.refresh)
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        self.search_edit.textChanged.connect(self.refresh)

        self.refresh()

    def set_status_filter(self, status: str | None) -> None:
        target = status or "All Releases"
        index = self.filter_combo.findText(target)
        if index >= 0:
            self.filter_combo.setCurrentIndex(index)

    def refresh(self) -> None:
        rows = self.repo.list_messages()
        rows = self._apply_filters(rows)
        fill_table(
            self.table,
            rows,
            [
                ("ID", "id"),
                ("Title", "title"),
                ("Type", "type"),
                ("Audience", "audience"),
                ("Priority", "priority"),
                ("Status", "status"),
                ("Updated", "updated_at"),
                ("Prepared By", "created_by"),
                ("Approved By", "approved_by"),
                ("Needs Action", "needs_action"),
            ],
        )
        self.changed.emit()

    def create_new_release(self, defaults: dict[str, Any] | None = None) -> None:
        message = dict(defaults or {})
        message.setdefault("status", "Draft")
        message.setdefault("type", "Press Release")
        message.setdefault("audience", "Public")
        message.setdefault("priority", "Normal")
        dialog = ReleaseEditorDialog(self.repo, self.current_user, message, self)
        dialog.saved.connect(lambda _message: self.refresh())
        dialog.exec()
        self.refresh()

    def open_selected(self) -> None:
        message = selected_row_data(self.table)
        if not message:
            return
        self.open_release(message)

    def open_release(self, message: dict[str, Any], defaults: dict[str, Any] | None = None) -> None:
        payload = dict(message)
        if defaults:
            payload.update(defaults)
        dialog = ReleaseEditorDialog(self.repo, self.current_user, payload, self)
        dialog.saved.connect(lambda _message: self.refresh())
        dialog.exec()
        self.refresh()

    def _apply_filters(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filter_name = self.filter_combo.currentText()
        search = self.search_edit.text().strip().lower()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            status = str(row.get("status") or "Draft")
            if filter_name == "Needs Action" and not is_actionable_status(status):
                continue
            if filter_name not in {"All Releases", "Needs Action"} and status != filter_name:
                continue
            if search:
                haystack = " ".join(
                    str(row.get(key, ""))
                    for key in ("title", "type", "audience", "priority", "status", "created_by", "approved_by")
                ).lower()
                if search not in haystack:
                    continue
            row = dict(row)
            row["needs_action"] = "Yes" if is_actionable_status(status) else "No"
            filtered.append(row)
        return filtered


class ReleaseManagerWindow(QMainWindow):
    def __init__(self, repo: PublicInformationRepository, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Public Information - Release Manager")
        self.resize(1400, 840)
        self.setMinimumSize(1000, 700)
        self.repo = repo
        self.current_user = current_user or {}
        self.panel = ReleaseManagerPanel(repo, self.current_user, self)
        self.setCentralWidget(self.panel)

    def set_status_filter(self, status: str | None) -> None:
        self.panel.set_status_filter(status)

    def refresh(self) -> None:
        self.panel.refresh()

