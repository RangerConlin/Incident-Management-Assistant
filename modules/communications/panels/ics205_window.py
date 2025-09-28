from __future__ import annotations

"""Standalone ICS-205 window (PySide6 Widgets only)."""

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
    QListView,
    QLineEdit,
    QLabel,
    QTableView,
    QToolBar,
    QStatusBar,
    QGroupBox,
    QVBoxLayout as QVBoxLayoutWidget,
    QMenu,
    QAbstractScrollArea,
    QSizePolicy,
)

from utils.state import AppState
from ..controller import ICS205Controller

from ..views.preview_dialog import PreviewDialog
from ..views.new_channel_dialog import NewChannelDialog
from ..views.import_ics217_dialog import ImportICS217Dialog
from ..views.edit_channel_dialog import EditChannelDialog


class ICS205Window(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("Communications Plan (ICS-205)")

        layout = QVBoxLayout(self)

        incident = AppState.get_active_incident()
        if incident is None:
            msg = QLabel("Select or create an incident to edit ICS-205.")
            layout.addWidget(msg, alignment=Qt.AlignCenter)
            self.setEnabled(False)
            return

        self.controller = None  # type: ignore[assignment]

        # Toolbar -----------------------------------------------------------
        toolbar = QToolBar()
        act_new = QAction("New Channel", self)
        self._act_edit = QAction("Edit", self)
        act_import = QAction("Import from ICS-217", self)
        act_dup = QAction("Duplicate", self)
        act_del = QAction("Delete", self)
        act_up = QAction("Move Up", self)
        act_down = QAction("Move Down", self)
        act_validate = QAction("Validate Plan", self)
        act_generate = QAction("Generate ICS-205", self)
        act_save = QAction("Save", self)
        act_close = QAction("Close", self)

        for a in (
            act_new,
            self._act_edit,
            act_import,
            act_dup,
            act_del,
            act_up,
            act_down,
            act_validate,
            act_generate,
            act_save,
            act_close,
        ):
            toolbar.addAction(a)
            if a in (act_del, act_down, act_generate):
                toolbar.addSeparator()
        layout.addWidget(toolbar)

        # Splitter: left master / right plan --------------------------------
        self.split = QSplitter(Qt.Horizontal)

        # Left panel (master list)
        self.left_box = QGroupBox("Master Catalog")
        left_v = QVBoxLayoutWidget(self.left_box)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search master catalog…")
        self.master_list = QListView()
        left_v.addWidget(self.search)
        left_v.addWidget(self.master_list)

        # Right panel (plan grid + column menu)
        self.right_box = QGroupBox("Active Communications Plan")
        right_v = QVBoxLayoutWidget(self.right_box)
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        # Use a modal dialog for edits instead of inline editing
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.table.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        right_v.addWidget(self.table)

        # Column visibility menu
        self.col_menu = QMenu("Columns", self)
        self.col_actions: List[QAction] = []
        toolbar.addAction(self.col_menu.menuAction())

        self.split.addWidget(self.left_box)
        self.split.addWidget(self.right_box)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        layout.addWidget(self.split)

        # Status bar --------------------------------------------------------
        self.status = QStatusBar()
        self.status.showMessage("")
        layout.addWidget(self.status)

        # Wire signals ------------------------------------------------------
        act_new.triggered.connect(self._open_new_channel)
        act_import.triggered.connect(self._open_import_dialog)
        self._act_edit.triggered.connect(self._open_edit_dialog)
        act_dup.triggered.connect(self._duplicate_selected)
        act_del.triggered.connect(self._delete_selected)
        act_up.triggered.connect(lambda: self._move_selected("up"))
        act_down.triggered.connect(lambda: self._move_selected("down"))
        act_validate.triggered.connect(self._validate)
        act_generate.triggered.connect(self._preview)
        act_save.triggered.connect(self._save)
        act_close.triggered.connect(self.close)

        # Defer model wiring to the next event loop turn
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._late_init)

    def _late_init(self):
        # Instantiate controller and attach models
        self.controller = ICS205Controller(self)
        self.master_list.setModel(self.controller.masterModel)
        self.table.setModel(self.controller.planModel)

        # Populate column visibility menu now that we have a model
        self.col_menu.clear()
        self.col_actions.clear()
        for i in range(self.controller.planModel.columnCount()):
            title = self.controller.planModel.headerData(i, Qt.Horizontal, Qt.DisplayRole) or f"Col {i}"
            act = QAction(str(title), self, checkable=True)
            act.setChecked(True)
            act.toggled.connect(lambda checked, col=i: self.table.setColumnHidden(col, not checked))
            self.col_actions.append(act)
            self.col_menu.addAction(act)

        # Now that controller exists, wire dynamic signals
        self.search.textChanged.connect(lambda t: self.controller.setFilter("search", t))
        self.master_list.doubleClicked.connect(self._add_selected_master)
        # Open editor on double-click
        self.table.doubleClicked.connect(lambda _idx: self._open_edit_dialog())
        try:
            self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_action_states())
        except Exception:
            pass

        # Initial state -----------------------------------------------------
        self._refresh_table()
        self._update_action_states()
        # Fit content after model attaches
        self._fit_to_content()

    # Helpers ---------------------------------------------------------------
    def _current_row_index(self) -> int:
        idx = self.table.currentIndex()
        return idx.row() if idx.isValid() else -1

    def _refresh_table(self):
        self.controller.refreshPlan()
        self.table.resizeColumnsToContents()
        # Adjust outer window to content to avoid large blank areas
        self._fit_to_content()

    def _fit_to_content(self):
        try:
            header = self.table.horizontalHeader()
            cols = self.controller.planModel.columnCount() if self.controller else 0
            total_cols = 0
            for c in range(cols):
                if not self.table.isColumnHidden(c):
                    total_cols += header.sectionSize(c)
            # Slightly widen beyond strict content
            right_w = max(total_cols + 140, 560)
            left_w = max(self.left_box.sizeHint().width(), 280)
            handle_w = self.split.handleWidth() if hasattr(self, 'split') else 6
            desired_w = left_w + handle_w + right_w + 32

            rows = self.controller.planModel.rowCount() if self.controller else 0
            row_h = self.table.sizeHintForRow(0) if rows else self.table.fontMetrics().height() + 10
            header_h = header.height()
            frame = int(self.table.frameWidth()) * 2
            table_h = header_h + row_h * max(rows, 1) + frame
            vertical_chrome = 120
            desired_h = table_h + vertical_chrome

            screen = self.windowHandle().screen() if self.windowHandle() else QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                max_w = int(geo.width() * 0.95)
                max_h = int(geo.height() * 0.8)
                w = min(desired_w, max_w)
                h = min(desired_h, max_h)
                self.resize(w, h)
        except Exception:
            pass

    def _update_action_states(self):
        has_sel = self._current_row_index() >= 0
        self._act_edit.setEnabled(has_sel)

    # Actions ---------------------------------------------------------------
    def _add_selected_master(self):
        idx = self.master_list.currentIndex()
        if not idx.isValid():
            return
        master_row = self.controller.masterModel.get(idx.row())
        self.controller.incident_repo.add_from_master(master_row, {})
        self._refresh_table()

    def _open_new_channel(self):
        dlg = NewChannelDialog(self.controller.incident_repo, self)
        if dlg.exec():
            data = dlg.get_channel_data()
            # Treat as master-like row for add_from_master
            master_like = {
                "id": None,
                "name": data.get("channel"),
                "function": data.get("function"),
                "rx_freq": data.get("rx_freq"),
                "tx_freq": data.get("tx_freq"),
                "rx_tone": data.get("rx_tone"),
                "tx_tone": data.get("tx_tone"),
                "system": data.get("system"),
                "mode": data.get("mode"),
                "notes": data.get("remarks"),
                "line_a": 0,
                "line_c": 0,
            }
            defaults = {
                "assignment_division": data.get("assignment_division"),
                "assignment_team": data.get("assignment_team"),
                "priority": data.get("priority", "Normal"),
                "include_on_205": 1 if data.get("include_on_205") else 0,
                "encryption": data.get("encryption", "None"),
                "remarks": data.get("remarks"),
            }
            self.controller.incident_repo.add_from_master(master_like, defaults)
            self._refresh_table()

    def _open_edit_dialog(self):
        i = self._current_row_index()
        rows = self.controller.planModel._rows
        if not (0 <= i < len(rows)):
            return
        r = rows[i]
        dlg = EditChannelDialog(r, self)
        if dlg.exec():
            patch = dlg.get_patch()
            if patch:
                row_id = int(r.get("id"))
                self.controller.incident_repo.update_row(row_id, patch)
                self._refresh_table()
                self.status.showMessage("Saved", 2000)

    def _open_import_dialog(self):
        dlg = ImportICS217Dialog(self.controller.master_repo, self)
        if dlg.exec():
            selected = dlg.get_selected_rows()
            defaults = dlg.get_defaults()
            for row in selected:
                self.controller.incident_repo.add_from_master(row, defaults)
            self._refresh_table()

    def _duplicate_selected(self):
        i = self._current_row_index()
        rows = self.controller.planModel._rows
        if 0 <= i < len(rows):
            r = rows[i]
            master_like = {
                "id": r.get("master_id"),
                "name": r.get("channel"),
                "function": r.get("function"),
                "rx_freq": r.get("rx_freq"),
                "tx_freq": r.get("tx_freq"),
                "rx_tone": r.get("rx_tone"),
                "tx_tone": r.get("tx_tone"),
                "system": r.get("system"),
                "mode": r.get("mode"),
                "notes": r.get("remarks"),
                "line_a": r.get("line_a", 0),
                "line_c": r.get("line_c", 0),
            }
            defaults = {
                "assignment_division": r.get("assignment_division"),
                "assignment_team": r.get("assignment_team"),
                "priority": r.get("priority", "Normal"),
                "include_on_205": r.get("include_on_205", 1),
                "encryption": r.get("encryption", "None"),
                "remarks": r.get("remarks"),
                "sort_index": int(r.get("sort_index", 1000)) + 1,
            }
            self.controller.incident_repo.add_from_master(master_like, defaults)
            self._refresh_table()

    def _delete_selected(self):
        i = self._current_row_index()
        if i < 0:
            return
        row_id = self.controller.planModel._rows[i]["id"]
        self.controller.incident_repo.delete_row(int(row_id))
        self._refresh_table()

    def _move_selected(self, direction: str):
        i = self._current_row_index()
        if i < 0:
            return
        row_id = self.controller.planModel._rows[i]["id"]
        self.controller.incident_repo.reorder(int(row_id), direction)
        self._refresh_table()

    def _validate(self):
        self.controller.runValidation()
        self.status.showMessage(self.controller.statusLine)

    def _preview(self):
        rows = self.controller.getPreviewRows()
        dlg = PreviewDialog(rows, self)
        dlg.exec()

    def _save(self):
        # No inline editor; nothing to do here beyond a status ping
        self.status.showMessage("Up to date", 1500)

    # Center the window on first show to avoid off-screen placement
    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_centered_once"):
            self._centered_once = True
            # Compute compact size and center
            screen = self.windowHandle().screen() if self.windowHandle() else QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.table.resizeColumnsToContents()
                self._fit_to_content()
                self.move(geo.center() - self.rect().center())


__all__ = ["ICS205Window"]
