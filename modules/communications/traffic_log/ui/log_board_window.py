from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QMenu,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ..models import CommsLogQuery
from ..services import CommsLogService
from .log_table import CommsLogTableView
from notifications.models.notification import Notification
from notifications.services import get_notifier
from .quick_entry import QuickEntryWidget
from .log_filters import LogFilterPanel


class CommunicationsLogBoardPanel(QWidget):
    """Dockable, table-focused log view with a New Entry action."""

    def __init__(self, service: CommsLogService, parent=None):
        super().__init__(parent)
        self.service = service
        self._current_query = CommsLogQuery()
        self._build_ui()
        self._load_initial_data()
        self._refresh_entries()

    def _build_ui(self) -> None:
        self.setObjectName("communicationsLogBoard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toolbar = QToolBar("Comms Log", self)
        toolbar.setMovable(False)
        layout.addWidget(toolbar)

        action_new = QAction("New Entry", self)
        action_new.triggered.connect(self._open_quick_entry_dialog)
        toolbar.addAction(action_new)

        # Filters dropdown embedding the existing LogFilterPanel
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

        self.table_view = CommsLogTableView(self)
        layout.addWidget(self.table_view, 1)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)

        self._status_bar = QStatusBar(self)
        layout.addWidget(self._status_bar)

        # Wire signals
        self.filter_panel.filtersChanged.connect(self._on_filters_changed)
        self.filter_panel.presetSaveRequested.connect(self._on_save_preset)
        self.filter_panel.presetDeleteRequested.connect(self._on_delete_preset)

    def _refresh_entries(self) -> None:
        entries = self.service.list_entries(self._current_query)
        self.table_view.set_entries(entries)
        self.statusBar().showMessage(f"{len(entries)} entries")

    def _load_initial_data(self) -> None:
        # Populate filters panel with channels and presets
        channels = self.service.list_channels()
        self.filter_panel.populate_channels(channels)
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)

    def _open_quick_entry_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("New Communications Entry")
        container = QWidget(dialog)
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)
        quick = QuickEntryWidget(container)
        quick.submitted.connect(lambda _payload: dialog.accept())
        # Wire submission to service
        def on_submit(payload: dict) -> None:
            try:
                self.service.create_entry(payload)
            finally:
                self._refresh_entries()
        quick.submitted.connect(on_submit)
        v.addWidget(quick)
        dialog.setLayout(v)
        dialog.setModal(True)
        dialog.exec()

    # Provide a statusBar-like accessor to mirror QMainWindow API used elsewhere
    def statusBar(self) -> QStatusBar:
        return self._status_bar

    def _on_filters_changed(self, query: CommsLogQuery) -> None:
        self._current_query = query
        self._refresh_entries()

    def _on_save_preset(self, name: str, filters: dict) -> None:
        preset = self.service.save_filter_preset(name, filters)
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)
        self.statusBar().showMessage(f"Preset '{preset.name}' saved", 2000)

    def _on_delete_preset(self, preset_id: int) -> None:
        try:
            self.service.delete_filter_preset(preset_id)
        except Exception as exc:
            # Keep it simple: show message in status bar
            self.statusBar().showMessage(f"Preset error: {exc}", 3000)
            return
        presets = self.service.list_filter_presets()
        self.filter_panel.populate_presets(presets)

    def _on_table_context_menu(self, pos) -> None:
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        entry = self.table_view.entry_at(index.row())
        if not entry or entry.id is None:
            return
        menu = QMenu(self.table_view)

        alert_action = QAction("Send Alert Notification", self)
        alert_action.triggered.connect(lambda entry_id=int(entry.id): self._send_notification(entry_id, "warning"))
        menu.addAction(alert_action)

        emergency_action = QAction("Send Emergency Notification", self)
        emergency_action.triggered.connect(lambda entry_id=int(entry.id): self._send_notification(entry_id, "error"))
        menu.addAction(emergency_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _send_notification(self, entry_id: int, severity: str) -> None:
        try:
            entry = self.service.get_entry(entry_id)
        except Exception as exc:
            self.statusBar().showMessage(f"Notification error: {exc}", 3000)
            return
        if not entry:
            return
        title = "Comms Alert" if severity != "error" else "Comms Emergency"
        parts = []
        if entry.resource_label:
            parts.append(entry.resource_label)
        who = "".join(
            [
                f"From {entry.from_unit}" if entry.from_unit else "",
                f" to {entry.to_unit}" if entry.to_unit else "",
            ]
        ).strip()
        if who:
            parts.append(who)
        if entry.message:
            parts.append(entry.message)
        msg = " — ".join([p for p in parts if p]) or "Log entry notification"
        notifier = get_notifier()
        notifier.notify(
            Notification(
                title=title,
                message=msg,
                severity="warning" if severity != "error" else "error",
                source="Communications Log",
                entity_type="comms_entry",
                entity_id=str(entry_id),
            )
        )
        self.statusBar().showMessage("Notification sent", 2000)


__all__ = ["CommunicationsLogBoardPanel"]
