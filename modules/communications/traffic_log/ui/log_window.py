"""Main window for the communications traffic log."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ..models import CommsLogQuery
from ..services import CommsLogService
from .log_detail import LogDetailDrawer
from .log_filters import LogFilterPanel
from .log_table import CommsLogTableView
from .quick_entry import QuickEntryWidget


class CommunicationsLogWindow(QMainWindow):
    """Dockable window implementing the traffic log workflow."""

    def __init__(self, service: CommsLogService, parent=None):
        super().__init__(parent)
        self.service = service
        self._current_query = CommsLogQuery()
        self._build_ui()
        self._load_initial_data()
        self._refresh_entries()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle("Communications Traffic Log")

        toolbar = QToolBar("Log Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_new = QAction("New Entry", self)
        self.action_new.setShortcut(QKeySequence("Ctrl+N"))
        self.action_new.triggered.connect(self._focus_quick_entry)
        toolbar.addAction(self.action_new)

        self.action_save = QAction("Save", self)
        self.action_save.setShortcut(QKeySequence("Ctrl+S"))
        self.action_save.triggered.connect(self._save_current_entry)
        toolbar.addAction(self.action_save)

        self.action_export_csv = QAction("Export CSV", self)
        self.action_export_csv.triggered.connect(lambda: self._export("csv"))
        toolbar.addAction(self.action_export_csv)

        self.action_export_pdf = QAction("Export PDF", self)
        self.action_export_pdf.triggered.connect(lambda: self._export("pdf"))
        toolbar.addAction(self.action_export_pdf)

        self.filter_panel = LogFilterPanel()
        self.filter_panel.setMinimumWidth(320)
        self.filter_menu = QMenu("Filters", self)
        self.filter_menu.setMinimumWidth(320)
        filter_widget_action = QWidgetAction(self)
        filter_widget_action.setDefaultWidget(self.filter_panel)
        self.filter_menu.addAction(filter_widget_action)

        self.filter_button = QToolButton(self)
        self.filter_button.setText("Filters")
        self.filter_button.setPopupMode(QToolButton.InstantPopup)
        self.filter_button.setMenu(self.filter_menu)
        self.filter_button.setToolTip("Show filter options")
        toolbar.addWidget(self.filter_button)

        toolbar.addSeparator()
        self.action_toggle_time = QAction("Toggle UTC", self)
        self.action_toggle_time.setShortcut(QKeySequence("Ctrl+U"))
        self.action_toggle_time.setCheckable(True)
        self.action_toggle_time.triggered.connect(self._toggle_time_view)
        toolbar.addAction(self.action_toggle_time)

        self.action_create_task = QAction("Create Task", self)
        self.action_create_task.triggered.connect(self._create_follow_up_task)
        toolbar.addAction(self.action_create_task)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(6)

        self.quick_entry = QuickEntryWidget()
        central_layout.addWidget(self.quick_entry)

        content_splitter = QSplitter(Qt.Vertical)
        content_splitter.setChildrenCollapsible(False)
        self.table_view = CommsLogTableView()
        content_splitter.addWidget(self.table_view)

        self.detail_drawer = LogDetailDrawer()
        content_splitter.addWidget(self.detail_drawer)
        content_splitter.setStretchFactor(0, 3)
        content_splitter.setStretchFactor(1, 2)

        central_layout.addWidget(content_splitter, 1)
        central_layout.setStretch(0, 0)
        central_layout.setStretch(1, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        # Wire signals
        self.filter_panel.filtersChanged.connect(self._on_filters_changed)
        self.filter_panel.presetSaveRequested.connect(self._on_save_preset)
        self.filter_panel.presetDeleteRequested.connect(self._on_delete_preset)
        self.quick_entry.submitted.connect(self._on_quick_entry_submitted)
        self.quick_entry.attachmentsRequested.connect(self._on_quick_entry_attachments)
        self.detail_drawer.saveRequested.connect(self._on_detail_save)
        self.detail_drawer.createTaskRequested.connect(lambda entry_id: self._create_follow_up_task(entry_id))
        self.table_view.selectionModel().currentChanged.connect(self._on_selection_changed)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_filters)

    # ------------------------------------------------------------------
    def _load_initial_data(self) -> None:
        channels = self.service.list_channels()
        self.filter_panel.populate_channels(channels)
        self.quick_entry.set_channels(channels)
        self.quick_entry.set_default_resource(self.service.last_used_resource())
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)

    # ------------------------------------------------------------------
    def _refresh_entries(self, *, select_id: Optional[int] = None) -> None:
        entries = self.service.list_entries(self._current_query)
        self.table_view.set_entries(entries)
        if select_id is not None:
            for row, entry in enumerate(entries):
                if entry.id == select_id:
                    self.table_view.selectRow(row)
                    self.detail_drawer.display_entry(entry)
                    break
        else:
            self._update_detail_from_selection()
        self.statusBar().showMessage(f"{len(entries)} entries")

    def _update_detail_from_selection(self) -> None:
        entry = self.table_view.selected_entry()
        self.detail_drawer.display_entry(entry)

    # ------------------------------------------------------------------
    def _on_filters_changed(self, query: CommsLogQuery) -> None:
        self._current_query = query
        self._refresh_entries()

    def _on_selection_changed(self, current, previous) -> None:  # noqa: D401
        self._update_detail_from_selection()

    def _on_quick_entry_submitted(self, payload: dict) -> None:
        try:
            entry = self.service.create_entry(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Entry Error", str(exc))
            return
        self.statusBar().showMessage("Entry added", 2000)
        self._refresh_entries(select_id=entry.id)
        self.quick_entry.set_default_resource(self.service.last_used_resource())

    def _on_quick_entry_attachments(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Attachments")
        if paths:
            self.quick_entry.add_attachments(paths)

    def _on_detail_save(self, entry_id: int, patch: dict) -> None:
        try:
            updated = self.service.update_entry(entry_id, patch)
        except Exception as exc:
            QMessageBox.warning(self, "Save Error", str(exc))
            return
        self.statusBar().showMessage("Entry updated", 2000)
        self._refresh_entries(select_id=updated.id)

    def _save_current_entry(self) -> None:
        entry = self.table_view.selected_entry()
        if not entry:
            return
        patch = self.detail_drawer.pending_patch()
        if not patch:
            return
        self._on_detail_save(int(entry.id), patch)

    def _focus_quick_entry(self) -> None:
        self.quick_entry.message_edit.setFocus()

    def _focus_filters(self) -> None:
        if getattr(self, "filter_button", None) and self.filter_button.menu():
            self.filter_button.showMenu()
            QTimer.singleShot(0, self.filter_panel.text_field.setFocus)
        else:
            self.filter_panel.text_field.setFocus()

    def _toggle_time_view(self) -> None:
        self.table_view.model.set_use_utc(self.action_toggle_time.isChecked())

    def _create_follow_up_task(self, entry_id: Optional[int] = None) -> None:
        entry = self.table_view.selected_entry() if entry_id is None else self.service.get_entry(entry_id)
        if not entry:
            return
        task_id = self.service.create_follow_up_task(int(entry.id))
        if task_id:
            self.statusBar().showMessage(f"Task {task_id} created", 3000)
            self._refresh_entries(select_id=entry.id)
        else:
            QMessageBox.information(self, "Task Creation", "Task module unavailable or task could not be created.")

    def _export(self, fmt: str) -> None:
        if fmt == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "Export CSV", filter="CSV Files (*.csv)")
            if not path:
                return
            self.service.export_to_csv(Path(path), self._current_query)
            QMessageBox.information(self, "Export", f"Exported to {path}")
        elif fmt == "pdf":
            path, _ = QFileDialog.getSaveFileName(self, "Export PDF", filter="PDF Files (*.pdf)")
            if not path:
                return
            self.service.export_to_pdf(Path(path), self._current_query)
            QMessageBox.information(self, "Export", f"Exported to {path}")

    def _on_save_preset(self, name: str, filters: dict) -> None:
        preset = self.service.save_filter_preset(name, filters)
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)
        self.statusBar().showMessage(f"Preset '{preset.name}' saved", 2000)

    def _on_delete_preset(self, preset_id: int) -> None:
        try:
            self.service.delete_filter_preset(preset_id)
        except Exception as exc:
            QMessageBox.warning(self, "Preset", str(exc))
            return
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)


__all__ = ["CommunicationsLogWindow"]
