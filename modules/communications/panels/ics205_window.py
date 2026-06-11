from __future__ import annotations

"""ICS-205 Communications Plan editor window."""

from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
    QFrame,
    QStyledItemDelegate,
)
from PySide6.QtCore import QModelIndex

from PySide6.QtWidgets import QComboBox

from utils.state import AppState
from ..controller import ICS205Controller, PLAN_COLUMNS, COMBO_COLUMN_OPTIONS
from ..views.preview_dialog import PreviewDialog
from ..views.new_channel_dialog import NewChannelDialog
from ..views.import_ics217_dialog import ImportICS217Dialog
from ..views.edit_channel_dialog import EditChannelDialog

_NON_EDITABLE_KEYS = {"function", "mode", "priority", "encryption"}

# Map column index → (options, editable)
_COMBO_COL_INDEX: dict[int, tuple[list[str], bool]] = {
    i: (COMBO_COLUMN_OPTIONS[key], key not in _NON_EDITABLE_KEYS)
    for i, (key, _) in enumerate(PLAN_COLUMNS)
    if key in COMBO_COLUMN_OPTIONS
}


class _PlanDelegate(QStyledItemDelegate):
    """Provides inline combo boxes for fixed-option columns."""

    def createEditor(self, parent, option, index):
        entry = _COMBO_COL_INDEX.get(index.column())
        if entry is not None:
            options, editable = entry
            cb = QComboBox(parent)
            cb.addItems(options)
            cb.setEditable(editable)
            cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            cb.setMinimumContentsLength(max(len(o) for o in options))
            cb.view().setMinimumWidth(
                cb.fontMetrics().horizontalAdvance(max(options, key=len)) + 32
            )
            return cb
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            val = index.data(Qt.DisplayRole) or ""
            i = editor.findText(str(val), Qt.MatchFixedString)
            if i >= 0:
                editor.setCurrentIndex(i)
            else:
                editor.setCurrentText(str(val))
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.EditRole)
        else:
            super().setModelData(editor, model, index)


def _btn(label: str, tooltip: str = "") -> QPushButton:
    b = QPushButton(label)
    b.setFixedHeight(28)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def _separator() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFrameShadow(QFrame.Sunken)
    f.setFixedWidth(10)
    return f


class ICS205Window(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("Communications Plan — ICS-205")

        root = QVBoxLayout(self)
        root.setSpacing(6)

        incident = AppState.get_active_incident()
        if incident is None:
            root.addWidget(
                QLabel("Select or create an incident to edit the ICS-205."),
                alignment=Qt.AlignCenter,
            )
            self.setEnabled(False)
            return

        self.controller: ICS205Controller = None  # type: ignore[assignment]

        # ── Action bar ────────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(4)

        self.btn_new = _btn("+ New Channel", "Create a new channel")
        self.btn_edit = _btn("Edit", "Edit the selected channel  [Double-click]")
        self.btn_dup = _btn("Duplicate", "Duplicate the selected row")
        self.btn_del = _btn("Delete", "Remove the selected row")

        self.btn_up = _btn("▲", "Move up")
        self.btn_up.setFixedWidth(32)
        self.btn_down = _btn("▼", "Move down")
        self.btn_down.setFixedWidth(32)

        self.btn_import = _btn("Import ICS-217", "Import channels from an ICS-217 master")
        self.btn_validate = _btn("Validate", "Check the plan for conflicts and warnings")
        self.btn_generate = _btn("Generate ICS-205 ▸", "Preview and generate the PDF form")

        # Column visibility menu attached to a small button
        self.col_menu = QMenu("Columns", self)
        self.btn_cols = QPushButton("Columns ▾")
        self.btn_cols.setFixedHeight(28)
        self.btn_cols.setMenu(self.col_menu)

        for w in (
            self.btn_new, self.btn_edit, self.btn_dup, self.btn_del,
            _separator(),
            self.btn_up, self.btn_down,
            _separator(),
            self.btn_import,
            _separator(),
            self.btn_validate, self.btn_generate,
            _separator(),
            self.btn_cols,
        ):
            if isinstance(w, QFrame):
                bar.addWidget(w)
            else:
                bar.addWidget(w)

        bar.addStretch()
        root.addLayout(bar)

        # ── Splitter: library (left) / plan table (right) ─────────────────────
        self.split = QSplitter(Qt.Horizontal)

        # Left — Channel Library
        lib_box = QGroupBox("Channel Library")
        lib_v = QVBoxLayout(lib_box)
        lib_v.setSpacing(4)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search library…")
        self.search.setClearButtonEnabled(True)

        self.master_list = QListView()
        self.master_list.setToolTip("Double-click a channel to add it to the plan")

        hint = QLabel("Double-click to add to plan")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: gray; font-size: 11px;")

        lib_v.addWidget(self.search)
        lib_v.addWidget(self.master_list, 1)
        lib_v.addWidget(hint)

        # Right — Active Plan
        plan_box = QGroupBox("Active Communications Plan")
        plan_v = QVBoxLayout(plan_box)
        plan_v.setSpacing(0)

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(
            QTableView.DoubleClicked | QTableView.SelectedClicked
        )
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.table.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegate(_PlanDelegate(self.table))

        plan_v.addWidget(self.table)

        self.split.addWidget(lib_box)
        self.split.addWidget(plan_box)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        root.addWidget(self.split, 1)

        # ── Status bar ────────────────────────────────────────────────────────
        self.status = QStatusBar()
        root.addWidget(self.status)

        # ── Wire signals ──────────────────────────────────────────────────────
        self.btn_new.clicked.connect(self._open_new_channel)
        self.btn_edit.clicked.connect(self._open_edit_dialog)
        self.btn_dup.clicked.connect(self._duplicate_selected)
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_up.clicked.connect(lambda: self._move_selected("up"))
        self.btn_down.clicked.connect(lambda: self._move_selected("down"))
        self.btn_import.clicked.connect(self._open_import_dialog)
        self.btn_validate.clicked.connect(self._validate)
        self.btn_generate.clicked.connect(self._preview)

        QTimer.singleShot(0, self._late_init)

    # ── Late init ─────────────────────────────────────────────────────────────

    def _late_init(self):
        self.controller = ICS205Controller(self)
        self.master_list.setModel(self.controller.masterModel)
        self.table.setModel(self.controller.planModel)

        # Column visibility menu
        self.col_menu.clear()
        self._col_actions: List[QAction] = []
        for i in range(self.controller.planModel.columnCount()):
            title = self.controller.planModel.headerData(i, Qt.Horizontal, Qt.DisplayRole) or f"Col {i}"
            act = QAction(str(title), self, checkable=True)
            act.setChecked(True)
            act.toggled.connect(lambda checked, col=i: self.table.setColumnHidden(col, not checked))
            self._col_actions.append(act)
            self.col_menu.addAction(act)

        self.search.textChanged.connect(lambda t: self.controller.setFilter("search", t))
        self.master_list.doubleClicked.connect(self._add_selected_master)
        # Double-click triggers inline cell editor (via delegate); Edit button opens full dialog.
        try:
            self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_button_states())
        except Exception:
            pass

        self._refresh_table()
        self._update_button_states()
        self._fit_to_content()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _current_row_index(self) -> int:
        idx = self.table.currentIndex()
        return idx.row() if idx.isValid() else -1

    def _refresh_table(self):
        self.controller.refreshPlan()
        self.table.resizeColumnsToContents()
        self._fit_to_content()

    def _fit_to_content(self):
        """Resize to the 1500×600 default, clamped to available screen."""
        try:
            screen = self.windowHandle().screen() if self.windowHandle() else QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                w = min(1500, int(geo.width() * 0.98))
                h = min(600, int(geo.height() * 0.95))
                self.resize(w, h)
        except Exception:
            pass

    def _update_button_states(self):
        has_sel = self._current_row_index() >= 0
        for btn in (self.btn_edit, self.btn_dup, self.btn_del, self.btn_up, self.btn_down):
            btn.setEnabled(has_sel)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_selected_master(self):
        idx = self.master_list.currentIndex()
        if not idx.isValid():
            return
        master_row = self.controller.masterModel.get(idx.row())
        self.controller.incident_repo.add_from_master(master_row, {})
        self._refresh_table()
        self.status.showMessage("Channel added from library.", 2000)

    def _open_new_channel(self):
        dlg = NewChannelDialog(self.controller.incident_repo, self)
        if dlg.exec():
            data = dlg.get_channel_data()
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
                "priority": data.get("priority", "Primary"),
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
                self.controller.incident_repo.update_row(int(r.get("id")), patch)
                self._refresh_table()
                self.status.showMessage("Saved.", 2000)

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
        if not (0 <= i < len(rows)):
            return
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
            "priority": r.get("priority", "Primary"),
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
        self.status.showMessage("Row deleted.", 2000)

    def _move_selected(self, direction: str):
        i = self._current_row_index()
        if i < 0:
            return
        row_id = self.controller.planModel._rows[i]["id"]
        self.controller.incident_repo.reorder(int(row_id), direction)
        self._refresh_table()
        # Reselect moved row
        new_i = max(0, i - 1) if direction == "up" else min(
            self.controller.planModel.rowCount() - 1, i + 1
        )
        self.table.selectRow(new_i)

    def _validate(self):
        self.controller.runValidation()
        self.status.showMessage(self.controller.statusLine, 5000)

    def _preview(self):
        rows = self.controller.getPreviewRows()
        dlg = PreviewDialog(rows, self)
        dlg.exec()

    # ── Show / center ─────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_centered_once"):
            self._centered_once = True
            screen = self.windowHandle().screen() if self.windowHandle() else QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.table.resizeColumnsToContents()
                self._fit_to_content()
                self.move(geo.center() - self.rect().center())


__all__ = ["ICS205Window"]
