"""Combined dockable window — channel-filtered log + quick entry form."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..models import CommsLogQuery
from ..services import CommsLogService
from .log_table import CommsLogTableView
from .quick_entry import QuickEntryWidget
from .add_clue_dialog import AddClueDialog
from utils.api_client import api_client


class LogEntryWindow(QMainWindow):
    """Dockable window: channel-filtered log (collapsible) + quick entry form."""

    def __init__(self, service: CommsLogService, parent=None,
                 *, incident_id: Optional[str] = None):
        super().__init__(parent)
        self.service = service
        self._incident_id: Optional[str] = incident_id
        self._channels: List[Dict] = []
        self._current_query = CommsLogQuery()
        self._log_visible = True
        self._entry_visible = False
        self._build_ui()
        self._load_initial()
        self._refresh()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("Log & Entry")

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Header bar ----
        header_bar = QWidget()
        header_bar.setStyleSheet("background:#1a237e;")
        header_bar.setFixedHeight(42)
        hrow = QHBoxLayout(header_bar)
        hrow.setContentsMargins(12, 0, 8, 0)
        hrow.setSpacing(8)

        title = QLabel("Communications Log & Entry")
        title.setStyleSheet("font-size:13px; font-weight:700; color:#fff;")
        hrow.addWidget(title)
        hrow.addStretch()

        hrow.addWidget(QLabel("<span style='color:#9fa8da; font-size:11px;'>Channel:</span>"))
        self._channel_filter = QComboBox()
        self._channel_filter.setMinimumWidth(180)
        self._channel_filter.setStyleSheet(
            "QComboBox { background:#283593; color:#fff; border:1px solid #3949ab;"
            " border-radius:3px; padding:2px 6px; } "
            "QComboBox::drop-down { border:none; } "
            "QComboBox QAbstractItemView { background:#1a237e; color:#fff; }"
        )
        self._channel_filter.addItem("All Channels", None)
        self._channel_filter.currentIndexChanged.connect(self._on_channel_filter_changed)
        hrow.addWidget(self._channel_filter)

        self._entry_toggle_btn = QPushButton("New Entry ▾")
        self._entry_toggle_btn.setFixedHeight(28)
        self._entry_toggle_btn.setStyleSheet(
            "QPushButton { background:#3949ab; color:#fff; border-radius:3px;"
            " font-size:11px; font-weight:600; padding:0 10px; border:none; }"
            "QPushButton:hover { background:#5c6bc0; }"
        )
        self._entry_toggle_btn.clicked.connect(self._toggle_entry)
        hrow.addWidget(self._entry_toggle_btn)

        self._clue_btn = QPushButton("🔍 Add Clue")
        self._clue_btn.setFixedHeight(28)
        self._clue_btn.setStyleSheet(
            "QPushButton { background:#1b5e20; color:#a5d6a7; border:1px solid #2e7d32;"
            " border-radius:3px; font-size:11px; font-weight:600; padding:0 10px; }"
            "QPushButton:hover { background:#2e7d32; color:#fff; }"
        )
        self._clue_btn.clicked.connect(self._on_add_clue)
        hrow.addWidget(self._clue_btn)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip("Refresh log")
        refresh_btn.setStyleSheet(
            "QPushButton { background:#3949ab; color:#fff; border-radius:3px;"
            " font-size:14px; border:none; }"
            "QPushButton:hover { background:#5c6bc0; }"
        )
        refresh_btn.clicked.connect(self._refresh)
        hrow.addWidget(refresh_btn)
        outer.addWidget(header_bar)

        # ---- Log section (hidden by default) ----
        self._log_section = QWidget()
        log_layout = QVBoxLayout(self._log_section)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        self.table_view = CommsLogTableView()
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_context_menu)
        self.table_view.selectionModel().currentChanged.connect(self._on_selection_changed)
        self.table_view.setMinimumHeight(160)
        log_layout.addWidget(self.table_view)

        # Edit / Delete row
        action_bar = QWidget()
        action_bar.setStyleSheet("background:#1e1e2e; border-top:1px solid #37474f;")
        arow = QHBoxLayout(action_bar)
        arow.setContentsMargins(8, 4, 8, 4)
        arow.setSpacing(6)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setEnabled(False)
        self._edit_btn.setFixedHeight(26)
        self._edit_btn.setStyleSheet(
            "QPushButton { background:#283593; color:#fff; border-radius:3px;"
            " padding:0 14px; font-weight:600; font-size:11px; }"
            "QPushButton:disabled { background:#2d2d2d; color:#555; }"
        )
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setFixedHeight(26)
        self._delete_btn.setStyleSheet(
            "QPushButton { background:#b71c1c; color:#fff; border-radius:3px;"
            " padding:0 14px; font-weight:600; font-size:11px; }"
            "QPushButton:disabled { background:#2d2d2d; color:#555; }"
        )
        self._edit_btn.clicked.connect(self._on_edit)
        self._delete_btn.clicked.connect(self._on_delete)
        arow.addWidget(self._edit_btn)
        arow.addWidget(self._delete_btn)
        arow.addStretch()
        self._sel_label = QLabel("")
        self._sel_label.setStyleSheet("font-size:11px; color:#546e7a;")
        arow.addWidget(self._sel_label)
        log_layout.addWidget(action_bar)

        self._log_section.setVisible(True)
        outer.addWidget(self._log_section)

        # ---- Divider ----
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color:#37474f;")
        outer.addWidget(divider)

        # ---- Entry section ----
        self._entry_section = QWidget()
        entry_section_layout = QVBoxLayout(self._entry_section)
        entry_section_layout.setContentsMargins(0, 0, 0, 0)
        entry_section_layout.setSpacing(0)
        self.entry_widget = QuickEntryWidget()
        self.entry_widget.submitted.connect(self._on_entry_submitted)
        entry_section_layout.addWidget(self.entry_widget)
        self._entry_section.setVisible(False)
        outer.addWidget(self._entry_section)

        # ---- Status bar ----
        sb = QStatusBar()
        sb.setStyleSheet("font-size:11px; color:#546e7a;")
        self.setStatusBar(sb)

        self.setCentralWidget(central)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.entry_widget.focus_message)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.entry_widget._on_submit)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_initial(self) -> None:
        channels = self.service.list_channels()
        self._channels = list(channels)

        self._channel_filter.blockSignals(True)
        self._channel_filter.clear()
        self._channel_filter.addItem("All Channels", None)
        for ch in self._channels:
            label = ch.get("channel_name") or ch.get("channel") or ""
            self._channel_filter.addItem(label, ch.get("id"))
        self._channel_filter.blockSignals(False)

        self.entry_widget.set_channels(channels)

        # Load teams for sender/receiver combos
        if self._incident_id:
            self._load_teams()

    def _load_teams(self) -> None:
        if not self._incident_id:
            return
        try:
            teams = api_client.get(f"/api/incidents/{self._incident_id}/operations/teams") or []
        except Exception:
            teams = []
        self.entry_widget.populate_teams(teams)

    def _refresh(self) -> None:
        entries = self.service.list_entries(self._current_query)
        self.table_view.set_entries(entries)
        self.statusBar().showMessage(f"{len(entries)} entries")
        self._update_action_buttons()

    def _on_channel_filter_changed(self) -> None:
        channel_id = self._channel_filter.currentData()
        self._refresh()
        if channel_id is not None:
            self.entry_widget.set_channel(channel_id)

    def _on_entry_submitted(self, payload: dict) -> None:
        try:
            self.service.create_entry(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Entry Error", str(exc))
            return
        self.statusBar().showMessage("Entry saved", 2000)
        self._refresh()

    # ------------------------------------------------------------------
    # Entry toggle
    # ------------------------------------------------------------------

    def _toggle_entry(self) -> None:
        self._entry_visible = not self._entry_visible
        self._entry_section.setVisible(self._entry_visible)
        self._entry_toggle_btn.setText("Hide Entry ▴" if self._entry_visible else "New Entry ▾")

    # ------------------------------------------------------------------
    # Table actions
    # ------------------------------------------------------------------

    def _on_selection_changed(self, current, previous) -> None:
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        entry = self.table_view.selected_entry()
        has = entry is not None
        self._edit_btn.setEnabled(has)
        self._delete_btn.setEnabled(has)
        if entry:
            ts = (entry.ts_local or entry.ts_utc or "")[:16].replace("T", " ")
            self._sel_label.setText(f"{ts}  {entry.from_unit or ''}")
        else:
            self._sel_label.setText("")

    def _on_edit(self) -> None:
        entry = self.table_view.selected_entry()
        if not entry:
            return
        self.entry_widget.from_field.lineEdit().setText(entry.from_unit or "")
        self.entry_widget.to_field.lineEdit().setText(entry.to_unit or "")
        self.entry_widget.insert_message_text(entry.message or "", replace=True)
        self.entry_widget.priority_toggle.set_priority(entry.priority)
        if entry.resource_id is not None:
            self.entry_widget.set_channel(entry.resource_id)
        self.entry_widget.focus_message()

    def _on_delete(self) -> None:
        entry = self.table_view.selected_entry()
        if not entry or entry.id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Entry", "Delete this log entry? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.service.delete_entry(int(entry.id))
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))
            return
        self.statusBar().showMessage("Entry deleted", 2000)
        self._refresh()

    def _on_add_clue(self) -> None:
        AddClueDialog(self, incident_id=self._incident_id).exec()

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        entry = self.table_view.entry_at(index.row())
        if not entry or entry.id is None:
            return
        menu = QMenu(self.table_view)
        menu.addAction("Edit Entry", self._on_edit)
        menu.addAction("Delete Entry", self._on_delete)
        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def set_incident_id(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._load_teams()


__all__ = ["LogEntryWindow"]
