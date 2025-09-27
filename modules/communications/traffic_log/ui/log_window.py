"""Main window for the communications traffic log."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, Qt, QTimer
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

from ..models import (
    CommsLogQuery,
    PRIORITY_EMERGENCY,
    PRIORITY_PRIORITY,
    PRIORITY_ROUTINE,
)
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

        self.action_toggle_details = QAction("Show Details", self)
        self.action_toggle_details.setEnabled(False)
        self.action_toggle_details.triggered.connect(self._toggle_detail_panel)
        toolbar.addAction(self.action_toggle_details)

        self.action_export_csv = QAction("Export CSV", self)
        self.action_export_csv.triggered.connect(lambda: self._export("csv"))
        toolbar.addAction(self.action_export_csv)

        self.action_export_pdf = QAction("Export PDF", self)
        self.action_export_pdf.triggered.connect(lambda: self._export("pdf"))
        toolbar.addAction(self.action_export_pdf)

        self._column_actions: Dict[str, QAction] = {}
        self.columns_menu = QMenu("Columns", self)
        self.columns_button = QToolButton(self)
        self.columns_button.setText("Columns")
        self.columns_button.setPopupMode(QToolButton.InstantPopup)
        self.columns_button.setMenu(self.columns_menu)
        self.columns_button.setToolTip("Choose visible columns")
        toolbar.addWidget(self.columns_button)

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
        self._priority_shortcuts: List[QShortcut] = []
        for key, priority in (
            ("1", PRIORITY_ROUTINE),
            ("2", PRIORITY_PRIORITY),
            ("3", PRIORITY_EMERGENCY),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda p=priority: self.quick_entry.set_priority(p))
            self._priority_shortcuts.append(shortcut)
        self.quick_entry.message_edit.focusChanged.connect(self._on_entry_message_focus_changed)
        self._on_entry_message_focus_changed(self.quick_entry.message_edit.hasFocus())

        content_splitter = QSplitter(Qt.Vertical)
        self.table_view = CommsLogTableView()
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        content_splitter.addWidget(self.table_view)

        self._populate_column_menu()

        self.detail_drawer = LogDetailDrawer()
        self.detail_drawer.setMinimumHeight(0)
        content_splitter.addWidget(self.detail_drawer)
        content_splitter.setCollapsible(0, False)
        content_splitter.setCollapsible(1, True)
        content_splitter.setStretchFactor(0, 6)
        content_splitter.setStretchFactor(1, 1)

        self.content_splitter = content_splitter
        self._detail_last_size = 240
        self._detail_visible = True
        content_splitter.splitterMoved.connect(self._on_splitter_moved)

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
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table_view.doubleClicked.connect(self._on_table_double_clicked)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_filters)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self._toggle_status_update_shortcut)

        self._set_detail_visible(False)
        self._update_detail_button_state()

    # ------------------------------------------------------------------
    def _populate_column_menu(self) -> None:
        self.columns_menu.clear()
        self._column_actions.clear()
        visible = self.table_view.visible_columns()
        for label in self.table_view.column_labels():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(label in visible)
            action.toggled.connect(lambda checked, name=label: self._on_column_toggled(name, checked))
            self.columns_menu.addAction(action)
            self._column_actions[label] = action

    def _refresh_column_checks(self) -> None:
        visible = self.table_view.visible_columns()
        for name, action in self._column_actions.items():
            expected = name in visible
            if action.isChecked() != expected:
                action.blockSignals(True)
                action.setChecked(expected)
                action.blockSignals(False)

    def _on_column_toggled(self, name: str, checked: bool) -> None:
        if not self.table_view.set_column_visible(name, checked):
            action = self._column_actions.get(name)
            if action:
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
        self._refresh_column_checks()

    # ------------------------------------------------------------------
    def _load_initial_data(self) -> None:
        channels = self.service.list_channels()
        self.filter_panel.populate_channels(channels)
        self.quick_entry.set_channels(channels)
        self.quick_entry.set_default_resource(self.service.last_used_resource())
        self.quick_entry.set_contact_suggestions(self.service.list_contact_entities())
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)

    # ------------------------------------------------------------------
    def _refresh_entries(self, *, select_id: Optional[int] = None) -> None:
        entries = self.service.list_entries(self._current_query)
        self.table_view.set_entries(entries)
        entry_displayed = False
        if select_id is not None:
            for row, entry in enumerate(entries):
                if entry.id == select_id:
                    self.table_view.selectRow(row)
                    self.detail_drawer.display_entry(entry)
                    entry_displayed = True
                    break
        if not entry_displayed:
            self._update_detail_from_selection()
        self.statusBar().showMessage(f"{len(entries)} entries")

    def _update_detail_from_selection(self) -> None:
        entry = self.table_view.selected_entry()
        self.detail_drawer.display_entry(entry)
        self._update_detail_button_state()

    def _update_detail_button_state(self) -> None:
        has_entry = self.table_view.selected_entry() is not None
        self.action_toggle_details.setEnabled(has_entry)
        if not has_entry:
            self._set_detail_visible(False)
        self.action_save.setEnabled(self._detail_visible and self.detail_drawer.isEnabled())

    def _set_detail_visible(self, visible: bool) -> None:
        if visible == self._detail_visible:
            self.action_save.setEnabled(self._detail_visible and self.detail_drawer.isEnabled())
            return
        self._detail_visible = visible
        if visible:
            self.detail_drawer.show()
            sizes = self.content_splitter.sizes()
            total = sum(sizes)
            if total <= 0:
                total = self.content_splitter.size().height()
            if total <= 0:
                total = self.height() or 600
            detail_size = self._detail_last_size
            if detail_size <= 0 or detail_size >= total:
                detail_size = max(180, total // 4) if total > 0 else 180
            table_size = max(total - detail_size, 0)
            if table_size <= 0:
                table_size = max(int(total * 0.7), 1)
                detail_size = total - table_size
            self.content_splitter.setSizes([table_size, detail_size])
            self.action_toggle_details.setText("Hide Details")
        else:
            sizes = self.content_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 0:
                self._detail_last_size = sizes[1]
            self.detail_drawer.hide()
            total = sum(sizes)
            if total <= 0:
                total = self.content_splitter.size().height()
            if total <= 0:
                total = self.height() or 600
            self.content_splitter.setSizes([total, 0])
            self.action_toggle_details.setText("Show Details")
        self.action_save.setEnabled(self._detail_visible and self.detail_drawer.isEnabled())

    def _toggle_detail_panel(self) -> None:
        if self._detail_visible:
            self._set_detail_visible(False)
        else:
            if self.table_view.selected_entry() is None:
                return
            self._set_detail_visible(True)

    def _on_table_double_clicked(self, index) -> None:  # noqa: D401
        if not index.isValid():
            return
        if self.table_view.selected_entry() is None:
            return
        self._set_detail_visible(True)

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:  # noqa: D401
        if not self._detail_visible:
            return
        sizes = self.content_splitter.sizes()
        if len(sizes) >= 2 and sizes[1] > 0:
            self._detail_last_size = sizes[1]

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
        self.quick_entry.focus_message()

    def _focus_filters(self) -> None:
        if getattr(self, "filter_button", None) and self.filter_button.menu():
            self.filter_button.showMenu()
            QTimer.singleShot(0, self.filter_panel.text_field.setFocus)
        else:
            self.filter_panel.text_field.setFocus()

    def _toggle_time_view(self) -> None:
        self.table_view.model.set_use_utc(self.action_toggle_time.isChecked())

    def _toggle_status_update_shortcut(self) -> None:
        entry = self.table_view.selected_entry()
        if not entry or entry.id is None:
            return
        self._apply_status_update(int(entry.id), not entry.is_status_update)

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

    def _on_table_context_menu(self, pos: QPoint) -> None:
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        entry = self.table_view.entry_at(index.row())
        if not entry or entry.id is None:
            return
        menu = QMenu(self.table_view)

        status_action = QAction("Status Update", self)
        status_action.setCheckable(True)
        status_action.setChecked(entry.is_status_update)
        status_action.triggered.connect(
            lambda checked, entry_id=int(entry.id): self._apply_status_update(entry_id, checked)
        )
        menu.addAction(status_action)

        follow_action = QAction("Follow-up Required", self)
        follow_action.setCheckable(True)
        follow_action.setChecked(entry.follow_up_required)
        follow_action.triggered.connect(
            lambda checked, entry_id=int(entry.id): self._apply_follow_up(entry_id, checked)
        )
        menu.addAction(follow_action)

        disposition_menu = menu.addMenu("Disposition")
        for label in ("Open", "Closed"):
            disp_action = QAction(label, self)
            disp_action.setCheckable(True)
            disp_action.setChecked(entry.disposition == label)
            disp_action.triggered.connect(
                lambda _checked, entry_id=int(entry.id), text=label: self._apply_disposition(entry_id, text)
            )
            disposition_menu.addAction(disp_action)

        menu.addSeparator()
        task_action = QAction("Create Follow-up Task", self)
        task_action.triggered.connect(lambda entry_id=int(entry.id): self._create_follow_up_task(entry_id))
        menu.addAction(task_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _on_entry_message_focus_changed(self, focused: bool) -> None:
        for shortcut in self._priority_shortcuts:
            shortcut.setEnabled(not focused)

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

    # ------------------------------------------------------------------
    # Context actions
    # ------------------------------------------------------------------
    def _apply_status_update(self, entry_id: int, value: bool) -> None:
        try:
            updated = self.service.mark_status_update(entry_id, value)
        except Exception as exc:
            QMessageBox.warning(self, "Status Update", str(exc))
            return
        self.statusBar().showMessage("Status flag updated", 1500)
        self._refresh_entries(select_id=updated.id)

    def _apply_follow_up(self, entry_id: int, value: bool) -> None:
        try:
            updated = self.service.mark_follow_up(entry_id, value)
        except Exception as exc:
            QMessageBox.warning(self, "Follow-up", str(exc))
            return
        self.statusBar().showMessage("Follow-up updated", 1500)
        self._refresh_entries(select_id=updated.id)

    def _apply_disposition(self, entry_id: int, disposition: str) -> None:
        try:
            updated = self.service.mark_disposition(entry_id, disposition)
        except Exception as exc:
            QMessageBox.warning(self, "Disposition", str(exc))
            return
        self.statusBar().showMessage(f"Disposition set to {disposition}", 1500)
        self._refresh_entries(select_id=updated.id)


__all__ = ["CommunicationsLogWindow"]
