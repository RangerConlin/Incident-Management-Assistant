"""Reusable checklist list/filter widget.

Lists the checklists for one incident with search and filters, and emits
Qt signals on selection / "new checklist" rather than opening anything
itself — the container (`checklists_tab.py` today; potentially another
module's panel later) decides what happens next. This widget depends only
on the generic checklist JSON shape the shared backend returns, never on
anything Planned-Events-specific.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import APIError
from utils.styles import subscribe_theme
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.timefmt import format_display_datetime

from .. import api
from ..progress_utils import progress_text, summarize
from ..styles_support import checklist_status_brush

_ALL = "All"
_STATUSES = ["Not Started", "In Progress", "Completed", "Archived"]
_STATUS_VALUES = {"Not Started": "not_started", "In Progress": "in_progress", "Completed": "completed", "Archived": "archived"}
_COLUMNS = ("Name", "Status", "Progress", "Owner", "Last Updated", "Failures", "Completed")


class ChecklistListWidget(QWidget):
    checklistSelected = Signal(dict)
    newChecklistRequested = Signal()

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id: Optional[str] = None if incident_id is None else str(incident_id)
        self._checklists: list[dict[str, Any]] = []
        self._template_names: dict[int, str] = {}
        self._build_ui()
        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    # -- construction -----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New Checklist…")
        self.new_button.clicked.connect(self.newChecklistRequested.emit)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name…")
        self.status_combo = QComboBox()
        self.status_combo.addItems([_ALL, *_STATUSES])
        self.template_combo = QComboBox()
        self.template_combo.addItem(_ALL)
        self.owner_edit = QLineEdit()
        self.owner_edit.setPlaceholderText("Filter by owner…")
        self.failures_only_check = QCheckBox("Unresolved failures only")
        for widget in (self.search_edit, self.status_combo, self.template_combo, self.owner_edit, self.failures_only_check):
            filters.addWidget(widget)
        layout.addLayout(filters)

        self.search_edit.textChanged.connect(self._apply_filters)
        self.status_combo.currentTextChanged.connect(self._apply_filters)
        self.template_combo.currentTextChanged.connect(self._apply_filters)
        self.owner_edit.textChanged.connect(self._apply_filters)
        self.failures_only_check.toggled.connect(self._apply_filters)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        apply_statusboard_table_behavior(self.table, stretch_last_section=False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

    # -- incident / data ----------------------------------------------------

    def set_incident(self, incident_id: object | None) -> None:
        normalized = None if incident_id is None else str(incident_id)
        if normalized == self.incident_id:
            return
        self.incident_id = normalized
        self._checklists = []
        self.table.setRowCount(0)
        self.refresh()

    def refresh(self) -> None:
        if not self.incident_id:
            self._checklists = []
            self.table.setRowCount(0)
            self.status_label.setText("Select an incident to view checklists.")
            return
        try:
            self._checklists = api.list_checklists(self.incident_id)
            self._load_template_names()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            self._checklists = []
            self.table.setRowCount(0)
            self.status_label.setText(self._describe_error(exc))
            return
        self._sync_template_filter_options()
        self._apply_filters()

    def _load_template_names(self) -> None:
        try:
            templates = api.list_templates(include_inactive=True)
        except Exception:
            templates = []
        self._template_names = {row["id"]: row.get("name", "") for row in templates if row.get("id") is not None}

    def _sync_template_filter_options(self) -> None:
        current = self.template_combo.currentText()
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem(_ALL)
        seen: set[str] = set()
        for checklist in self._checklists:
            name = self._template_label(checklist)
            if name and name not in seen:
                seen.add(name)
                self.template_combo.addItem(name)
        index = self.template_combo.findText(current)
        self.template_combo.setCurrentIndex(index if index >= 0 else 0)
        self.template_combo.blockSignals(False)

    def _template_label(self, checklist: dict[str, Any]) -> str:
        template_id = checklist.get("template_id")
        if template_id is None:
            return "Blank (no template)"
        return self._template_names.get(template_id) or f"Template {template_id}"

    # -- filtering / rendering ---------------------------------------------

    def _apply_filters(self, *_args: Any) -> None:
        search = self.search_edit.text().strip().lower()
        status_filter = self.status_combo.currentText()
        template_filter = self.template_combo.currentText()
        owner_filter = self.owner_edit.text().strip().lower()
        failures_only = self.failures_only_check.isChecked()

        rows: list[dict[str, Any]] = []
        for checklist in self._checklists:
            if search and search not in (checklist.get("name") or "").lower():
                continue
            if status_filter != _ALL and checklist.get("status") != _STATUS_VALUES.get(status_filter):
                continue
            if template_filter != _ALL and self._template_label(checklist) != template_filter:
                continue
            summary = summarize(checklist.get("sections"))
            if failures_only and not summary["failed_items"]:
                continue
            owner_display = self._owner_display(checklist)
            if owner_filter and owner_filter not in owner_display.lower():
                continue
            rows.append(checklist)

        previously_selected = self.selected_checklist_id()
        self._populate(rows)
        self.status_label.setText(f"{len(rows)} of {len(self._checklists)} checklists")
        if previously_selected:
            # Restore the selection without re-emitting checklistSelected —
            # rebuilding the table (e.g. after `update_checklist_in_place`)
            # must not make the detail panel reload the checklist it just
            # finished updating.
            self.table.blockSignals(True)
            self.select_checklist_id(previously_selected)
            self.table.blockSignals(False)

    def _owner_display(self, checklist: dict[str, Any]) -> str:
        owner = checklist.get("owner_person_record")
        if owner is None:
            return ""
        try:
            return api.resolve_person_display(int(owner))
        except Exception:
            return str(owner)

    def _populate(self, rows: list[dict[str, Any]]) -> None:
        self.table.setRowCount(len(rows))
        for row_idx, checklist in enumerate(rows):
            summary = summarize(checklist.get("sections"))
            status = str(checklist.get("status") or "not_started")
            values = [
                checklist.get("name") or "",
                status.replace("_", " ").title(),
                progress_text(checklist.get("sections")),
                self._owner_display(checklist) or "—",
                format_display_datetime(checklist.get("updated_at"), include_seconds=False) or "—",
                str(len(summary["failed_items"])),
                format_display_datetime(checklist.get("completed_at"), include_seconds=False) or "—",
            ]
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col_idx == 1:
                    brush = checklist_status_brush(status)
                    if brush is not None:
                        cell.setBackground(brush["bg"])
                        cell.setForeground(brush["fg"])
                cell.setData(Qt.ItemDataRole.UserRole, checklist.get("id"))
                self.table.setItem(row_idx, col_idx, cell)

    def _on_selection_changed(self, current: QTableWidgetItem | None, _previous: QTableWidgetItem | None) -> None:
        if current is None:
            return
        row = current.row()
        checklist_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        checklist = next((c for c in self._checklists if c.get("id") == checklist_id), None)
        if checklist is not None:
            self.checklistSelected.emit(checklist)

    def update_checklist_in_place(self, checklist: dict[str, Any]) -> None:
        """Patch one row's underlying data from an already-fetched checklist
        (e.g. after the execution widget records a response or completes a
        lifecycle action), without a network round trip. No-ops if that
        checklist isn't currently in this list's incident/dataset."""

        checklist_id = checklist.get("id")
        for index, existing in enumerate(self._checklists):
            if existing.get("id") == checklist_id:
                self._checklists[index] = checklist
                self._sync_template_filter_options()
                self._apply_filters()
                return

    def select_checklist_id(self, checklist_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == checklist_id:
                self.table.setCurrentItem(item)
                return

    def selected_checklist_id(self) -> Optional[str]:
        current = self.table.currentItem()
        if current is None:
            return None
        row = current.row()
        name_item = self.table.item(row, 0)
        return name_item.data(Qt.ItemDataRole.UserRole) if name_item is not None else None

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Checklists API unavailable: {exc}"
            return f"Checklists API error {exc.status_code}: {exc}"
        return str(exc)

    def _on_theme_changed(self, _name: str) -> None:
        self._apply_filters()
