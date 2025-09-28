from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from functools import partial
from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal, QEvent, QRegularExpression
from PySide6.QtGui import QStandardItem, QStandardItemModel, QColor, QPalette, QRegularExpressionValidator, QDoubleValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QTabWidget,
    QScrollArea,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QStyledItemDelegate,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QMessageBox,
    QInputDialog,
)


def _to_variant(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_to_variant(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_variant(v) for k, v in obj.items()}
    return obj


def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return ""
    s = str(ts)
    if "." in s:
        tz_idx = max(s.find("Z"), s.find("+", s.find(".")))
        if tz_idx > 0:
            s = s[: s.find(".")] + s[tz_idx:]
        else:
            s = s[: s.find(".")]
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%m/%d/%Y %H:%M:%S")
    except Exception:
        return str(ts)


class _YesNoDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):  # type: ignore[override]
        cb = QComboBox(parent)
        cb.addItems(["No", "Yes"])
        return cb

    def setEditorData(self, editor, index):  # type: ignore[override]
        v = index.data(Qt.EditRole)
        yes = v in (True, 1, "1", "Yes", "YES", "True", "true")
        editor.setCurrentIndex(1 if yes else 0)

    def setModelData(self, editor, model, index):  # type: ignore[override]
        yes = editor.currentIndex() == 1
        model.setData(index, 1 if yes else 0, Qt.EditRole)
        model.setData(index, "Yes" if yes else "No", Qt.DisplayRole)


class _ButtonDelegate(QStyledItemDelegate):
    """Renders a push button in a cell and emits a clicked signal when pressed."""

    clicked = Signal(object)  # emits QModelIndex

    def paint(self, painter, option, index):  # type: ignore[override]
        btn_opt = QStyleOptionButton()
        btn_opt.rect = option.rect
        btn_opt.state = QStyle.State_Enabled
        btn_opt.text = str(index.data(Qt.DisplayRole) or "214+")
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.CE_PushButton, btn_opt, painter)
        else:
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):  # type: ignore[override]
        try:
            if event.type() in (QEvent.MouseButtonRelease,):
                if option.rect.contains(event.pos()):
                    self.clicked.emit(index)
                    return True
        except Exception:
            pass
        return False


class TaskDetailWindow(QWidget):
    """QWidget-based Task Detail window with embedded Narrative tab."""

    def __init__(self, task_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task_id = int(task_id)
        # Title is updated after header load; keep minimal placeholder
        self.setWindowTitle("Task Detail")
        # Default width adjusted (+40% from 600 -> 840)
        self.resize(840, 720)

        root = QVBoxLayout(self)
        try:
            self.setAutoFillBackground(True)
        except Exception:
            pass

        # --- Lookups and Top Controls ---
        try:
            from modules.operations.taskings.data.lookups import (
                CATEGORIES,
                PRIORITIES,
                TASK_STATUSES as TASK_STATES,
                TASK_TYPES_BY_CATEGORY,
            )
        except Exception:
            CATEGORIES = ["<New Task>"]
            PRIORITIES = ["Low", "Medium", "High", "Critical"]
            TASK_STATES = ["Draft", "Planned", "In Progress", "Completed", "Cancelled"]
            TASK_TYPES_BY_CATEGORY = {"<New Task>": ["(select category first)"]}
        self._lookups = {
            "categories": list(CATEGORIES),
            "priorities": list(PRIORITIES),
            "statuses": list(TASK_STATES),
            "types_by_cat": dict(TASK_TYPES_BY_CATEGORY),
        }

        # Slightly more saturated backgrounds per status
        self._status_bg_colors = {
            "draft": "#e9ecef",        # light gray -> a touch deeper
            "planned": "#ce93d8",      # match task status purple
            "assigned": "#bfe1ff",     # very light blue -> medium-light blue
            "in progress": "#a8e0ea",  # light cyan -> more saturated teal/cyan
            "complete": "#bfe6c3",     # pale green -> richer green
            "completed": "#bfe6c3",
            "cancelled": "#f5b7b1",    # light red -> warmer red
        }

        self._loading_header = False
        self._header_field_cache: Dict[str, str] = {}

        # Top controls in a grid: Category, Type, Priority, Status, Task ID
        top_container = QWidget(self)
        top_grid = QGridLayout(top_container)
        try:
            top_grid.setContentsMargins(0, 0, 0, 0)
            top_grid.setHorizontalSpacing(8)
            top_grid.setVerticalSpacing(4)
        except Exception:
            pass

        self._cat = QComboBox(self);
        self._cat.addItems(self._lookups["categories"])  # Category
        self._typ = QComboBox(self)  # Type (filtered)
        self._refresh_task_type_options(self._cat.currentText())
        try:
            self._cat.currentTextChanged.connect(self._on_category_changed)
        except Exception:
            pass
        try:
            self._typ.currentTextChanged.connect(self._on_task_type_changed)
        except Exception:
            pass
        self._prio = QComboBox(self);
        self._prio.addItems(self._lookups["priorities"])  # Priority
        try:
            self._prio.currentTextChanged.connect(self._on_priority_changed)
        except Exception:
            pass
        self._stat = QComboBox(self);
        self._stat.addItems(self._lookups["statuses"])  # Status
        try:
            self._stat.currentTextChanged.connect(self._on_status_changed)
        except Exception:
            pass
        self._task_id_edit = QLineEdit(self);
        self._task_id_edit.setPlaceholderText("Task ID")
        try:
            self._task_id_edit.editingFinished.connect(partial(self._on_header_line_edit, 'task_id', self._task_id_edit))
        except Exception:
            pass
        for r, (lab, w) in enumerate([
            ("Category", self._cat),
            ("Type", self._typ),
            ("Priority", self._prio),
            ("Status", self._stat),
            ("Task ID", self._task_id_edit),
        ]):
            top_grid.addWidget(QLabel(lab), 0, r)
            top_grid.addWidget(w, 1, r)
            try:
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                if hasattr(w, 'setMinimumHeight'):
                    w.setMinimumHeight(28)
            except Exception:
                pass
        root.addWidget(top_container)
        try:
            self._update_category_type_display()
        except Exception:
            pass
        try:
            self._apply_status_background(self._stat.currentText())
        except Exception:
            pass

        # Primary Team (read-only) 2x2 grid, above Title/Location/Assignment
        primary_container = QWidget(self)
        primary_v = QVBoxLayout(primary_container)
        try:
            primary_v.setContentsMargins(0, 0, 0, 0)
            primary_v.setSpacing(6)
        except Exception:
            pass
        hdr_row = QHBoxLayout()
        _pt_label = QLabel("Primary Team");
        try:
            _pt_label.setStyleSheet("font-weight: 600;")
        except Exception:
            pass
        hdr_row.addWidget(_pt_label)
        hdr_row.addStretch(1)
        _tc_label = QLabel("Team Contact")
        try:
            _tc_label.setStyleSheet("font-weight: 600;")
        except Exception:
            pass
        hdr_row.addWidget(_tc_label)
        primary_v.addLayout(hdr_row)
        grid = QGridLayout()
        try:
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(4)
        except Exception:
            pass
        # Display-only labels (no text boxes)
        self._primary_team_name_lbl = QLabel("")
        self._primary_team_leader_lbl = QLabel("")
        self._primary_team_phone_lbl = QLabel("")
        grid.addWidget(self._primary_team_name_lbl, 0, 0)
        grid.addWidget(QWidget(self), 0, 1)  # placeholder to form 2x2 with three fields
        grid.addWidget(self._primary_team_leader_lbl, 1, 0)
        grid.addWidget(self._primary_team_phone_lbl, 1, 1)
        primary_v.addLayout(grid)
        root.addWidget(primary_container)

        # Title/Location/Assignment stacked vertically + Save/Cancel
        stack = QVBoxLayout()
        self._title_edit = QLineEdit(self); self._title_edit.setPlaceholderText("Title")
        self._location_edit = QLineEdit(self); self._location_edit.setPlaceholderText("Location")
        # Removed redundant Category/Type read-only display between Location and Assignment
        self._category_type_display = None  # kept for compatibility with update helpers
        self._assignment_edit = QLineEdit(self); self._assignment_edit.setPlaceholderText("Assignment")
        for edit, field in ((self._title_edit, 'title'), (self._location_edit, 'location'), (self._assignment_edit, 'assignment')):
            try:
                edit.editingFinished.connect(partial(self._on_header_line_edit, field, edit))
            except Exception:
                pass
        for lab, w in [("Title", self._title_edit), ("Location", self._location_edit), ("Assignment", self._assignment_edit)]:
            row = QVBoxLayout()
            _lbl = QLabel(lab)
            try:
                _lbl.setStyleSheet("font-weight: 600;")
            except Exception:
                pass
            row.addWidget(_lbl)
            row.addWidget(w)
            stack.addLayout(row)
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save"); self._save_btn.clicked.connect(self._save_header)
        self._cancel_btn = QPushButton("Cancel"); self._cancel_btn.clicked.connect(self._load_header)
        btn_row.addStretch(1)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._cancel_btn)
        stack.addLayout(btn_row)
        root.addLayout(stack)

        # Header summary removed per request

        # Narrative Quick Entry (always visible, above tabs)
        nar_quick_top = QHBoxLayout()
        try:
            nar_quick_top.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._nar_entry_top = QTextEdit(self)
        try:
            self._nar_entry_top.setPlaceholderText("Type narrative… (Enter to add)")
        except Exception:
            pass
        # Make it ~3 lines tall
        try:
            fm = self._nar_entry_top.fontMetrics()
            self._nar_entry_top.setFixedHeight(max(56, int(fm.lineSpacing() * 3 + 12)))
        except Exception:
            self._nar_entry_top.setFixedHeight(72)
        # Submit on Ctrl+Enter as QTextEdit is multi-line
        try:
            from PySide6.QtGui import QKeySequence
            self._nar_entry_top.keyPressEvent = (lambda orig: (lambda e: (self.add_narrative() if (e.modifiers() & Qt.ControlModifier and e.key() in (Qt.Key_Return, Qt.Key_Enter)) else orig(e))))(self._nar_entry_top.keyPressEvent)
        except Exception:
            pass
        self._nar_crit_top = QCheckBox("Critical", self)
        add_btn_top = QPushButton("Add")
        add_btn_top.clicked.connect(self.add_narrative)
        nar_quick_top.addWidget(self._nar_entry_top, 1)
        nar_quick_top.addWidget(self._nar_crit_top)
        nar_quick_top.addWidget(add_btn_top)
        root.addLayout(nar_quick_top)

        # Tabs
        tabs = QTabWidget(self)
        root.addWidget(tabs, 1)

        # Narrative tab
        self._nar_headers_base = ["ID", "Date/Time (UTC)", "Entry", "Entered By", "Team", "Critical", "214+"]
        self._nar_model = QStandardItemModel(0, len(self._nar_headers_base), self)
        self._nar_model.setHorizontalHeaderLabels(self._nar_headers_base)
        nar_content = QWidget(self)
        nar_layout = QVBoxLayout(nar_content)
        try:
            nar_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        quick = QHBoxLayout()
        try:
            quick.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._nar_entry = QLineEdit(nar_content)
        try:
            self._nar_entry.setVisible(False)
        except Exception:
            pass
        self._nar_entry.setPlaceholderText("Type narrative… (Enter to add)")
        self._nar_entry.returnPressed.connect(self.add_narrative)
        self._nar_crit = QComboBox(nar_content)
        try:
            self._nar_crit.setVisible(False)
        except Exception:
            pass
        self._nar_crit.addItems(["No", "Yes"])
        add_btn = QPushButton("Add", nar_content)
        try:
            add_btn.setVisible(False)
        except Exception:
            pass
        add_btn.clicked.connect(self.add_narrative)
        quick.addWidget(self._nar_entry, 1)
        quick.addWidget(QLabel("Critical:"))
        quick.addWidget(self._nar_crit)
        quick.addWidget(add_btn)

        self._nar_table = QTableView(self)
        self._nar_table.setModel(self._nar_model)
        self._nar_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._nar_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self._nar_table.setAlternatingRowColors(True)
        self._nar_table.setColumnHidden(0, True)
        self._nar_table.setSortingEnabled(True)
        hh: QHeaderView = self._nar_table.horizontalHeader()
        # Default: interactive columns; make Entry column stretch to fill remaining width
        try:
            hh.setStretchLastSection(False)
            hh.setSectionResizeMode(QHeaderView.Interactive)
            hh.setSectionResizeMode(2, QHeaderView.Stretch)  # Entry
            hh.setSortIndicatorShown(True)
            # Add visual dividers between header sections to make resize handles obvious
            try:
                hh.setSectionsClickable(True)
                hh.setHighlightSections(True)
            except Exception:
                pass
            try:
                hh.setStyleSheet(
                    "QHeaderView::section { border-right: 1px solid #b0b0b0; padding-right: 4px; } "
                    "QHeaderView::section:last { border-right: none; }"
                )
            except Exception:
                pass
        except Exception:
            pass
        self._nar_table.setItemDelegateForColumn(5, _YesNoDelegate(self._nar_table))
        # Render a push-button in the last column ("214+") and handle clicks
        try:
            self._nar_btn_delegate = _ButtonDelegate(self._nar_table)
            self._nar_table.setItemDelegateForColumn(6, self._nar_btn_delegate)
            self._nar_btn_delegate.clicked.connect(self._on_nar_button_clicked)
        except Exception:
            pass
        try:
            self._nar_model.dataChanged.connect(self._on_narrative_data_changed)
        except Exception:
            pass

        # Moved quick narrative entry to top section; hide it in the tab
        # nar_layout.addLayout(quick)
        nar_layout.addWidget(self._nar_table, 1)
        nar_scroll = QScrollArea(self)
        nar_scroll.setWidgetResizable(True)
        nar_scroll.setWidget(nar_content)
        tabs.addTab(nar_scroll, "Narrative")

        # Planning tab (Objectives linkage)
        plan_content = QWidget(self)
        plan_layout = QVBoxLayout(plan_content)
        try:
            plan_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        plan_row = QHBoxLayout()
        try:
            plan_row.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._plan_obj_cb = QComboBox(plan_content)
        self._plan_obj_cb.setEditable(False)
        self._plan_obj_cb.currentIndexChanged.connect(lambda _i: self._on_plan_obj_changed())
        self._plan_strat_cb = QComboBox(plan_content)
        self._plan_strat_cb.setEditable(False)
        self._plan_refresh_btn = QPushButton("Refresh", plan_content)
        self._plan_refresh_btn.clicked.connect(self._load_planning)
        self._plan_link_btn = QPushButton("Link Task", plan_content)
        self._plan_link_btn.clicked.connect(self._link_task_to_strategy)
        plan_row.addWidget(QLabel("Objective:"))
        plan_row.addWidget(self._plan_obj_cb, 2)
        plan_row.addWidget(QLabel("Strategy:"))
        plan_row.addWidget(self._plan_strat_cb, 2)
        plan_row.addWidget(self._plan_refresh_btn)
        plan_row.addWidget(self._plan_link_btn)
        plan_layout.addLayout(plan_row)

        self._plan_headers = ["LinkId", "Objective", "Strategy", "Remove"]
        self._plan_links_model = QStandardItemModel(0, len(self._plan_headers), self)
        self._plan_links_model.setHorizontalHeaderLabels(self._plan_headers)
        self._plan_links_table = QTableView(self)
        self._plan_links_table.setModel(self._plan_links_model)
        self._plan_links_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._plan_links_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._plan_links_table.setAlternatingRowColors(True)
        self._plan_links_table.setSortingEnabled(True)
        self._plan_links_table.setColumnHidden(0, True)
        try:
            ph: QHeaderView = self._plan_links_table.horizontalHeader()
            ph.setStretchLastSection(False)
            ph.setSectionResizeMode(QHeaderView.Interactive)
            ph.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            ph.setSectionResizeMode(2, QHeaderView.Stretch)
            ph.setSortIndicatorShown(True)
        except Exception:
            pass
        try:
            self._plan_btn_delegate = _ButtonDelegate(self._plan_links_table)
            self._plan_links_table.setItemDelegateForColumn(3, self._plan_btn_delegate)
            self._plan_btn_delegate.clicked.connect(self._on_plan_remove_clicked)
        except Exception:
            pass
        plan_layout.addWidget(self._plan_links_table, 1)
        # Defer adding the Planning tab until the very end so it appears on the far right
        self._planning_content = plan_content
        # Load data when the window is constructed
        try:
            self._load_planning()
        except Exception:
            pass

        # Teams tab
        teams_content = QWidget(self)
        teams_layout = QVBoxLayout(teams_content)
        try:
            teams_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        tbar = QHBoxLayout()
        self._btn_team_add = QPushButton("Add Team")
        self._btn_team_edit = QPushButton("Edit Team")
        self._btn_team_status = QPushButton("Change Status")
        self._btn_team_primary = QPushButton("Set Primary")
        self._btn_team_add.clicked.connect(self._teams_add)
        self._btn_team_edit.clicked.connect(self._teams_edit)
        self._btn_team_status.clicked.connect(self._teams_change_status)
        self._btn_team_primary.clicked.connect(self._teams_set_primary)
        for b in [self._btn_team_add, self._btn_team_edit, self._btn_team_status, self._btn_team_primary]:
            tbar.addWidget(b)
        # Dev-only hard delete button: visible when DEV_MODE (main.py:7) or uiDebugTools is true
        _dev_enabled = False
        try:
            from main import DEV_MODE as _DEV
            _dev_enabled = bool(_DEV)
        except Exception:
            _dev_enabled = False
        if not _dev_enabled:
            try:
                from utils.settingsmanager import SettingsManager
                _dev_enabled = bool(SettingsManager().get('uiDebugTools', False))
            except Exception:
                _dev_enabled = False
        if _dev_enabled:
            try:
                self._btn_team_dev_delete = QPushButton("DEV: DELETE TEAM")
                self._btn_team_dev_delete.clicked.connect(self._teams_dev_delete)
                tbar.addWidget(self._btn_team_dev_delete)
            except Exception:
                pass
        tbar.addStretch(1)
        teams_layout.addLayout(tbar)
        self._teams_headers_base = [
            "ID",
            "Primary",
            "Sortie",
            "Team",
            "Leader",
            "Phone",
            "Status",
            "Assigned",
            "Briefed",
            "Enroute",
            "Arrival",
            "Discovery",
            "Complete",
        ]
        self._teams_model = QStandardItemModel(0, len(self._teams_headers_base), self)
        self._teams_model.setHorizontalHeaderLabels(list(self._teams_headers_base)) 
        self._teams_table = QTableView(self)
        self._teams_table.setModel(self._teams_model)
        self._teams_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._teams_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._teams_table.setAlternatingRowColors(True)
        self._teams_table.setSortingEnabled(True)
        self._teams_table.setColumnHidden(0, True)
        th: QHeaderView = self._teams_table.horizontalHeader()
        try:
            th.setStretchLastSection(False)
            # Resizable columns with initial default widths
            th.setSectionResizeMode(QHeaderView.Interactive)
            th.setSortIndicatorShown(True)
            # Add header dividers to make resize handles obvious
            try:
                th.setSectionsClickable(True)
                th.setHighlightSections(True)
            except Exception:
                pass
            try:
                th.setStyleSheet(
                    "QHeaderView::section { border-right: 1px solid #b0b0b0; padding-right: 4px; } "
                    "QHeaderView::section:last { border-right: none; }"
                )
            except Exception:
                pass
        except Exception:
            pass
        # Apply default column widths; table remains resizable with window
        try:
            default_sizes = [40, 50, 150, 120, 100, 100, 80, 80, 80, 80, 80, 80]
            for i, w in enumerate(default_sizes, start=1):
                if i < self._teams_model.columnCount():
                    self._teams_table.setColumnWidth(i, int(w))
        except Exception:
            pass
        teams_layout.addWidget(self._teams_table, 1)
        teams_scroll = QScrollArea(self)
        teams_scroll.setWidgetResizable(True)
        teams_scroll.setWidget(teams_content)
        tabs.addTab(teams_scroll, "Teams")

        # Personnel tab
        pers_content = QWidget(self)
        pers_layout = QVBoxLayout(pers_content)
        try:
            pers_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._pers_headers_base = ["Active", "Name", "ID", "Rank", "Role", "Organization", "Phone", "Team"]
        self._pers_model = QStandardItemModel(0, len(self._pers_headers_base), self)
        self._pers_model.setHorizontalHeaderLabels(list(self._pers_headers_base)) 
        self._pers_table = QTableView(self)
        self._pers_table.setModel(self._pers_model)
        self._pers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._pers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._pers_table.setAlternatingRowColors(True)
        self._pers_table.setSortingEnabled(True)
        thp: QHeaderView = self._pers_table.horizontalHeader()
        try:
            thp.setStretchLastSection(False)
            # Resizable columns with initial defaults
            thp.setSectionResizeMode(QHeaderView.Interactive)
            try:
                thp.setSectionResizeMode(1, QHeaderView.Stretch)  # Make Name stretch nicely
            except Exception:
                pass
            thp.setSortIndicatorShown(True)
            # Header dividers for obvious resize handles
            try:
                thp.setSectionsClickable(True)
                thp.setHighlightSections(True)
            except Exception:
                pass
            try:
                thp.setStyleSheet(
                    "QHeaderView::section { border-right: 1px solid #b0b0b0; padding-right: 4px; } " +
                    "QHeaderView::section:last { border-right: none; }"
                )
            except Exception:
                pass
            # Personnel: keep static header labels (no width suffixes)
        except Exception:
            pass
        # Apply default column widths; table remains resizable with window
        try:
            default_sizes = [50, 250, 100, 100, 100, 100, 150, 100]
            for i, w in enumerate(default_sizes, start=0):
                if i < self._pers_model.columnCount():
                    self._pers_table.setColumnWidth(i, int(w))
        except Exception:
            pass
        pers_layout.addWidget(self._pers_table, 1)
        pers_scroll = QScrollArea(self)
        pers_scroll.setWidgetResizable(True)
        pers_scroll.setWidget(pers_content)
        tabs.addTab(pers_scroll, "Personnel")

        # Other tabs (placeholders, kept minimal to avoid scope growth)
        tabs.addTab(QLabel("Teams — coming soon"), "Teams")
        tabs.addTab(QLabel("Personnel — coming soon"), "Personnel")
        # Vehicles tab
        veh_content = QWidget(self)
        veh_layout = QVBoxLayout(veh_content)
        try:
            veh_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        # Vehicles (ground)
        self._veh_headers_base = ["Active", "ID", "License Plate", "Type", "Organization"]
        self._veh_model = QStandardItemModel(0, len(self._veh_headers_base), self)
        self._veh_model.setHorizontalHeaderLabels(list(self._veh_headers_base))
        self._veh_table = QTableView(self)
        self._veh_table.setModel(self._veh_model)
        self._veh_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._veh_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._veh_table.setAlternatingRowColors(True)
        self._veh_table.setSortingEnabled(True)
        thv: QHeaderView = self._veh_table.horizontalHeader()
        try:
            thv.setStretchLastSection(False)
            thv.setSectionResizeMode(QHeaderView.Interactive)
            thv.setSortIndicatorShown(True)
            try:
                thv.setSectionsClickable(True)
                thv.setHighlightSections(True)
            except Exception:
                pass
            try:
                thv.setStyleSheet(
                    "QHeaderView::section { border-right: 1px solid #b0b0b0; padding-right: 4px; } "
                    + "QHeaderView::section:last { border-right: none; }"
                )
            except Exception:
                pass
        except Exception:
            pass
        # Default widths and detach from window (fixed table width), but allow column resize
        try:
            veh_defaults = [60, 80, 140, 120, 160]
            for i, w in enumerate(veh_defaults):
                if i < self._veh_model.columnCount():
                    self._veh_table.setColumnWidth(i, int(w))
            def _veh_apply_fixed_width():
                try:
                    total = sum(self._veh_table.columnWidth(c) for c in range(self._veh_model.columnCount()))
                    vh = self._veh_table.verticalHeader().width() if self._veh_table.verticalHeader() else 0
                    frame = int(self._veh_table.frameWidth()) * 2
                    vsb_w = self._veh_table.verticalScrollBar().sizeHint().width() if self._veh_table.verticalScrollBar() else 0
                    self._veh_table.setFixedWidth(int(total + vh + frame + vsb_w))
                    self._veh_table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
                except Exception:
                    pass
            _veh_apply_fixed_width()
            try:
                thv.sectionResized.connect(lambda *_: _veh_apply_fixed_width())
            except Exception:
                pass
            # Keep static header labels for Vehicles (no width suffixes)
        except Exception:
            pass
        veh_layout.addWidget(self._veh_table)
        # Aircraft
        self._air_label = QLabel("Aircraft")
        veh_layout.addWidget(self._air_label)
        self._air_headers_base = ["Active", "Callsign", "Tail Number", "Type", "Organization"]
        self._air_model = QStandardItemModel(0, len(self._air_headers_base), self)
        self._air_model.setHorizontalHeaderLabels(list(self._air_headers_base))
        self._air_table = QTableView(self)
        self._air_table.setModel(self._air_model)
        self._air_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._air_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._air_table.setAlternatingRowColors(True)
        self._air_table.setSortingEnabled(True)
        tha: QHeaderView = self._air_table.horizontalHeader()
        try:
            tha.setStretchLastSection(False)
            tha.setSectionResizeMode(QHeaderView.Interactive)
            tha.setSortIndicatorShown(True)
            try:
                tha.setSectionsClickable(True)
                tha.setHighlightSections(True)
            except Exception:
                pass
            try:
                tha.setStyleSheet(
                    "QHeaderView::section { border-right: 1px solid #b0b0b0; padding-right: 4px; } "
                    + "QHeaderView::section:last { border-right: none; }"
                )
            except Exception:
                pass
        except Exception:
            pass
        # Default widths and detach aircraft table similarly
        try:
            air_defaults = [60, 120, 120, 120, 160]
            for i, w in enumerate(air_defaults):
                if i < self._air_model.columnCount():
                    self._air_table.setColumnWidth(i, int(w))
            def _air_apply_fixed_width():
                try:
                    total = sum(self._air_table.columnWidth(c) for c in range(self._air_model.columnCount()))
                    vh = self._air_table.verticalHeader().width() if self._air_table.verticalHeader() else 0
                    frame = int(self._air_table.frameWidth()) * 2
                    vsb_w = self._air_table.verticalScrollBar().sizeHint().width() if self._air_table.verticalScrollBar() else 0
                    self._air_table.setFixedWidth(int(total + vh + frame + vsb_w))
                    self._air_table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
                except Exception:
                    pass
            _air_apply_fixed_width()
            try:
                tha.sectionResized.connect(lambda *_: _air_apply_fixed_width())
            except Exception:
                pass
            # Keep static header labels for Aircraft (no width suffixes)
        except Exception:
            pass
        veh_layout.addWidget(self._air_table)
        veh_scroll = QScrollArea(self)
        veh_scroll.setWidgetResizable(True)
        veh_scroll.setWidget(veh_content)
        tabs.addTab(veh_scroll, "Vehicles")
        # Assignment Details tab (Ground/Air info to support CAPF 109, SAR 104, ICS 204)
        assign_widget = self._build_assignment_details_tab()
        tabs.addTab(assign_widget, "Assignment Details")

        # Communications tab (ICS 205 linkage)
        comms_container = QWidget(self)
        comms_v = QVBoxLayout(comms_container)
        try:
            comms_v.setContentsMargins(6, 6, 6, 6)
            comms_v.setSpacing(6)
        except Exception:
            pass
        # Toolbar row: Add/Remove
        comms_toolbar = QHBoxLayout()
        self._comms_add_btn = QPushButton("Add Channel", self)
        self._comms_del_btn = QPushButton("Remove Selected", self)
        comms_toolbar.addWidget(self._comms_add_btn)
        comms_toolbar.addWidget(self._comms_del_btn)
        comms_toolbar.addStretch(1)
        comms_v.addLayout(comms_toolbar)

        # Model and table
        self._comms_headers = [
            "Channel Name",
            "Zone",
            "Channel Number",
            "Function",
            "RX Frequency",
            "RX Tone/NAC",
            "TX Frequency",
            "TX Tone/NAC",
            "Mode (A/D/M)",
            "Remarks",
        ]
        self._comms_model = QStandardItemModel(0, len(self._comms_headers), self)
        self._comms_model.setHorizontalHeaderLabels(list(self._comms_headers))

        self._comms_table = QTableView(self)
        self._comms_table.setModel(self._comms_model)
        self._comms_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._comms_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self._comms_table.setAlternatingRowColors(True)
        self._comms_table.setSortingEnabled(False)
        thc: QHeaderView = self._comms_table.horizontalHeader()
        try:
            thc.setStretchLastSection(True)
            thc.setSectionResizeMode(QHeaderView.Interactive)
            thc.setSortIndicatorShown(False)
            try:
                thc.setSectionsClickable(True)
                thc.setHighlightSections(True)
            except Exception:
                pass
        except Exception:
            pass

        # Delegates for editable columns
        try:
            from utils.constants import RADIO_TASK_FUNCTIONS as _RADIO_TASK_FUNCTIONS
        except Exception:
            _RADIO_TASK_FUNCTIONS = ["PRIMARY", "SECONDARY", "COMMAND", "TACTICAL", "AIR/GROUND", "EMERGENCY"]

        # Local delegates with callbacks to repository updates
        from PySide6.QtWidgets import QComboBox as _QComboBox
        from PySide6.QtWidgets import QStyledItemDelegate as _QStyledItemDelegate
        from PySide6.QtCore import Qt as _Qt

        class _CommsChannelDelegate(_QStyledItemDelegate):
            def __init__(self, parent_w: QWidget):
                super().__init__(parent_w)
                self._parent_w = parent_w

            def _channels(self) -> List[Dict[str, Any]]:
                try:
                    from modules.operations.taskings.repository import list_incident_channels
                    return list_incident_channels() or []
                except Exception:
                    return []

            def createEditor(self, parent, option, index):  # type: ignore[override]
                cb = _QComboBox(parent)
                for ch in self._channels():
                    label = str(ch.get("channel") or f"Ch-{ch.get('id')}")
                    cb.addItem(label, ch.get("id"))
                return cb

            def setEditorData(self, editor, index):  # type: ignore[override]
                # Current incident_channel_id stored in UserRole+1 on column 0 item
                try:
                    model = index.model()
                    row = index.row()
                    it = model.item(row, 0)
                    current_id = it.data(_Qt.UserRole + 1)
                    for i in range(editor.count()):
                        if editor.itemData(i) == current_id:
                            editor.setCurrentIndex(i)
                            break
                except Exception:
                    pass

            def setModelData(self, editor, model, index):  # type: ignore[override]
                try:
                    selected_id = editor.currentData()
                    # Persist selection via repository
                    it = model.item(index.row(), 0)
                    row_id = it.data(_Qt.UserRole)
                    from modules.operations.taskings.repository import update_task_comm
                    if row_id is not None:
                        update_task_comm(int(row_id), incident_channel_id=int(selected_id) if selected_id is not None else None)
                    # Trigger reload to refresh read-only columns
                    self._parent_w.load_comms()
                except Exception:
                    pass

        class _CommsFunctionDelegate(_QStyledItemDelegate):
            def createEditor(self, parent, option, index):  # type: ignore[override]
                cb = _QComboBox(parent)
                try:
                    cb.addItems(list(_RADIO_TASK_FUNCTIONS))
                except Exception:
                    cb.addItems(["PRIMARY", "SECONDARY", "COMMAND", "TACTICAL"]) 
                return cb

            def setEditorData(self, editor, index):  # type: ignore[override]
                txt = str(index.data(_Qt.DisplayRole) or "").strip().lower()
                for i in range(editor.count()):
                    if str(editor.itemText(i)).strip().lower() == txt:
                        editor.setCurrentIndex(i)
                        break

            def setModelData(self, editor, model, index):  # type: ignore[override]
                try:
                    value = str(editor.currentText()).strip()
                    # Persist via repository
                    it = model.item(index.row(), 0)
                    row_id = it.data(_Qt.UserRole)
                    from modules.operations.taskings.repository import update_task_comm
                    if row_id is not None:
                        update_task_comm(int(row_id), function=value)
                    # Update display
                    model.setData(index, value, _Qt.DisplayRole)
                except Exception:
                    pass

        # Install delegates
        try:
            self._comms_table.setItemDelegateForColumn(0, _CommsChannelDelegate(self))
            self._comms_table.setItemDelegateForColumn(3, _CommsFunctionDelegate(self))
        except Exception:
            pass

        # Wire add/remove actions
        def _add_comm_row():
            new_id = None
            try:
                from modules.operations.taskings.repository import add_task_comm
                new_id = add_task_comm(int(self._task_id), None, None, None)
            except Exception as e:
                try:
                    QMessageBox.warning(self, "Add Channel", f"Could not add row: {e}")
                except Exception:
                    pass
            self.load_comms()
            # Select the newly added row and start editing Channel Name
            try:
                if new_id is not None:
                    target_row = -1
                    for r in range(self._comms_model.rowCount()):
                        it0 = self._comms_model.item(r, 0)
                        if int(it0.data(Qt.UserRole) or 0) == int(new_id):
                            target_row = r
                            break
                    if target_row >= 0:
                        idx = self._comms_model.index(target_row, 0)
                        self._comms_table.setCurrentIndex(idx)
                        try:
                            self._comms_table.scrollTo(idx)
                        except Exception:
                            pass
                        self._comms_table.edit(idx)
            except Exception:
                pass

        def _del_comm_row():
            try:
                idx = self._comms_table.currentIndex()
                if not idx.isValid():
                    try:
                        QMessageBox.information(self, "Remove Channel", "Select a row to remove.")
                    except Exception:
                        pass
                    return
                it = self._comms_model.item(idx.row(), 0)
                row_id = it.data(Qt.UserRole)
                if row_id is None:
                    return
                from modules.operations.taskings.repository import remove_task_comm
                remove_task_comm(int(row_id))
            except Exception as e:
                try:
                    QMessageBox.warning(self, "Remove Channel", f"Could not remove row: {e}")
                except Exception:
                    pass
            self.load_comms()

        try:
            self._comms_add_btn.clicked.connect(_add_comm_row)
            self._comms_del_btn.clicked.connect(_del_comm_row)
        except Exception:
            pass

        comms_v.addWidget(self._comms_table)
        tabs.addTab(comms_container, "Communications")

        # Debriefing tab
        deb_content = QWidget(self)
        deb_v = QVBoxLayout(deb_content)
        try:
            deb_v.setContentsMargins(6, 6, 6, 6)
            deb_v.setSpacing(6)
        except Exception:
            pass
        deb_toolbar = QHBoxLayout()
        self._deb_add_btn = QPushButton("Add Debrief", self)
        self._deb_refresh_btn = QPushButton("Refresh", self)
        self._deb_submit_btn = QPushButton("Submit", self)
        self._deb_mark_rev_btn = QPushButton("Mark Reviewed", self)
        self._deb_archive_btn = QPushButton("Archive", self)
        self._deb_delete_btn = QPushButton("Delete", self)
        for b in [self._deb_add_btn, self._deb_refresh_btn, self._deb_submit_btn, self._deb_mark_rev_btn, self._deb_archive_btn, self._deb_delete_btn]:
            deb_toolbar.addWidget(b)
        deb_toolbar.addStretch(1)
        deb_v.addLayout(deb_toolbar)

        # Info label to show current task and count
        self._deb_info = QLabel("", self)
        try:
            self._deb_info.setStyleSheet("color: #666; font-size: 12px;")
        except Exception:
            pass
        deb_v.addWidget(self._deb_info)

        # Debriefs table
        self._deb_headers = [
            "ID",
            "Sortie",
            "Debriefer",
            "Types",
            "Status",
            "Flag",
            "Updated",
        ]
        self._deb_model = QStandardItemModel(0, len(self._deb_headers), self)
        self._deb_model.setHorizontalHeaderLabels(list(self._deb_headers))
        self._deb_table = QTableView(self)
        self._deb_table.setModel(self._deb_model)
        self._deb_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._deb_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._deb_table.setAlternatingRowColors(True)
        self._deb_table.setSortingEnabled(True)
        try:
            self._deb_table.horizontalHeader().setStretchLastSection(True)
            self._deb_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        except Exception:
            pass
        deb_v.addWidget(self._deb_table, 2)

        # Editor container (hidden until selection)
        self._deb_editor = QWidget(self)
        self._deb_editor.setVisible(False)
        self._deb_editor_v = QVBoxLayout(self._deb_editor)
        try:
            self._deb_editor_v.setContentsMargins(6, 6, 6, 6)
            self._deb_editor_v.setSpacing(6)
        except Exception:
            pass
        deb_v.addWidget(self._deb_editor, 3)

        tabs.addTab(deb_content, "Debriefing")
        tabs.addTab(QLabel("Log — coming soon"), "Log")
        # Attachments/Forms tab
        att_content = QWidget(self)
        att_v = QVBoxLayout(att_content)
        try:
            att_v.setContentsMargins(6, 6, 6, 6)
            att_v.setSpacing(6)
        except Exception:
            pass
        att_toolbar = QHBoxLayout()
        self._att_upload_btn = QPushButton("Upload File", self)
        self._att_open_btn = QPushButton("Open", self)
        self._att_annotate_btn = QPushButton("Annotate", self)
        self._att_delete_btn = QPushButton("Delete", self)
        self._att_generate_btn = QPushButton("Generate Forms...", self)
        self._att_refresh_btn = QPushButton("Refresh", self)
        for b in [self._att_upload_btn, self._att_open_btn, self._att_annotate_btn, self._att_delete_btn, self._att_generate_btn, self._att_refresh_btn]:
            att_toolbar.addWidget(b)
        att_toolbar.addStretch(1)
        att_v.addLayout(att_toolbar)
        # Table
        self._att_headers = ["Filename", "Type", "Uploaded By", "Timestamp", "Size", "Versions", "ID"]
        self._att_model = QStandardItemModel(0, len(self._att_headers), self)
        self._att_model.setHorizontalHeaderLabels(list(self._att_headers))
        self._att_table = QTableView(self)
        self._att_table.setModel(self._att_model)
        self._att_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._att_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._att_table.setAlternatingRowColors(True)
        self._att_table.setSortingEnabled(True)
        try:
            hh = self._att_table.horizontalHeader()
            hh.setStretchLastSection(False)
            hh.setSectionResizeMode(QHeaderView.Interactive)
            self._att_table.setColumnHidden(6, True)  # hide ID
            # Reasonable default widths
            widths = [280, 90, 120, 180, 80, 80]
            for i, w in enumerate(widths):
                self._att_table.setColumnWidth(i, int(w))
        except Exception:
            pass
        att_v.addWidget(self._att_table, 1)
        tabs.addTab(att_content, "Attachments/Forms")
        # Insert Log tab (ICS-214, Task Log, Team Log) and remove placeholder if present
        try:
            log_container = QWidget(self)
            log_layout = QVBoxLayout(log_container)
            log_layout.setContentsMargins(0, 0, 0, 0)
            self._log_tabs = QTabWidget(log_container)
            log_layout.addWidget(self._log_tabs)
            # ICS-214 (team-specific)
            ics214 = QWidget(self); ics_layout = QVBoxLayout(ics214); ics_layout.setContentsMargins(0, 0, 0, 0)
            ics_bar = QHBoxLayout()
            # Toolbar actions only; ICS-214 stream is always scoped to this task
            self._btn_214_refresh = QPushButton("Refresh")
            self._btn_214_export = QPushButton("Export 214")
            self._btn_214_edit = QPushButton("Edit")
            self._btn_214_delete = QPushButton("Delete")
            for b in (self._btn_214_refresh, self._btn_214_export, self._btn_214_edit, self._btn_214_delete): ics_bar.addWidget(b)
            ics_bar.addStretch(1); ics_layout.addLayout(ics_bar)
            self._tbl_214 = QTableView(self)
            self._model_214 = QStandardItemModel(0, 3, self)
            self._model_214.setHorizontalHeaderLabels(["Timestamp", "Entry", "Entered By"])
            self._tbl_214.setModel(self._model_214); self._tbl_214.setSortingEnabled(True)
            ics_layout.addWidget(self._tbl_214)
            self._log_tabs.addTab(ics214, "ICS-214")
            # Task Log
            tlog = QWidget(self); tlog_layout = QVBoxLayout(tlog); tlog_bar = QHBoxLayout()
            self._tlog_search = QLineEdit(); self._tlog_search.setPlaceholderText("Search keyword…")
            self._tlog_field = QLineEdit(); self._tlog_field.setPlaceholderText("Field filter…")
            self._tlog_from = QLineEdit(); self._tlog_from.setPlaceholderText("From (YYYY-MM-DD)")
            self._tlog_to = QLineEdit(); self._tlog_to.setPlaceholderText("To (YYYY-MM-DD)")
            self._btn_tlog_refresh = QPushButton("Refresh"); self._btn_tlog_export = QPushButton("Export CSV")
            for w in (self._tlog_search, self._tlog_field, self._tlog_from, self._tlog_to, self._btn_tlog_refresh, self._btn_tlog_export): tlog_bar.addWidget(w)
            tlog_bar.addStretch(1); tlog_layout.addLayout(tlog_bar)
            self._tbl_tlog = QTableView(self)
            self._model_tlog = QStandardItemModel(0, 5, self)
            self._model_tlog.setHorizontalHeaderLabels(["Timestamp", "Field Changed", "Old Value", "New Value", "Changed By"])
            self._tbl_tlog.setModel(self._model_tlog); self._tbl_tlog.setSortingEnabled(True)
            tlog_layout.addWidget(self._tbl_tlog)
            self._log_tabs.addTab(tlog, "Task Log")
            # Team Log
            teamlog = QWidget(self); teamlog_layout = QVBoxLayout(teamlog)
            self._tbl_teamlog = QTableView(self)
            self._model_teamlog = QStandardItemModel(0, 3, self)
            self._model_teamlog.setHorizontalHeaderLabels(["Timestamp", "Team", "Status Changed To"])
            self._tbl_teamlog.setModel(self._model_teamlog); self._tbl_teamlog.setSortingEnabled(True)
            teamlog_layout.addWidget(self._tbl_teamlog)
            self._log_tabs.addTab(teamlog, "Team Log")
            # Default to ICS-214 sub-tab
            try:
                self._log_tabs.setCurrentIndex(0)
            except Exception:
                pass
            # Actions
            self._btn_tlog_refresh.clicked.connect(self._load_task_log)
            self._btn_tlog_export.clicked.connect(self._export_task_log)
            self._tlog_search.returnPressed.connect(self._load_task_log)
            self._tlog_field.returnPressed.connect(self._load_task_log)
            self._tlog_from.returnPressed.connect(self._load_task_log)
            self._tlog_to.returnPressed.connect(self._load_task_log)
            self._btn_214_refresh.clicked.connect(self._load_ics214)
            self._btn_214_export.clicked.connect(self._export_ics214)
            self._btn_214_delete.clicked.connect(self._delete_ics214_entry)
            self._btn_214_edit.clicked.connect(self._edit_ics214_entry)
            tabs.addTab(log_container, "Log")
            # Remove any prior placeholder Log tab
            try:
                for i in range(tabs.count()-1, -1, -1):
                    try:
                        if str(tabs.tabText(i)).strip().lower().startswith("log"):
                            if isinstance(tabs.widget(i), QLabel):
                                tabs.removeTab(i)
                    except Exception:
                        continue
            except Exception:
                pass
            # Initial load
            self._load_ics214(); self._load_task_log(); self._load_team_log()
        except Exception:
            pass
        # Wire attachment actions
        self._att_upload_btn.clicked.connect(self._att_upload)
        self._att_open_btn.clicked.connect(self._att_open)
        self._att_annotate_btn.clicked.connect(self._att_annotate)
        self._att_delete_btn.clicked.connect(self._att_delete)
        self._att_generate_btn.clicked.connect(self._att_generate)
        self._att_refresh_btn.clicked.connect(self.load_attachments)
        # Ensure no leftover placeholder Planning tabs remain (from older builds)
        try:
            i = 0
            while i < tabs.count():
                try:
                    if str(tabs.tabText(i)).strip().lower().startswith("planning"):
                        if isinstance(tabs.widget(i), QLabel):
                            tabs.removeTab(i)
                            continue
                except Exception:
                    pass
                i += 1
        except Exception:
            pass
        # Finally add the functional Planning tab at the far right
        try:
            if getattr(self, "_planning_content", None) is not None:
                tabs.addTab(self._planning_content, "Planning")
        except Exception:
            pass

        # Remove duplicate placeholder tabs for Teams/Personnel if present
        try:
            i = 0
            while i < tabs.count():
                w = tabs.widget(i)
                name = tabs.tabText(i)
                if isinstance(w, QLabel) and name in ("Teams", "Personnel"):
                    tabs.removeTab(i)
                    continue
                i += 1
        except Exception:
            pass

        # Initial data load
        self._load_header()
        self.load_narrative()
        try:
            self.load_vehicles()
        except Exception:
            pass
        try:
            self.load_assignment()
        except Exception:
            pass
        try:
            self.load_teams()
        except Exception:
            pass
        try:
            self.load_personnel()
        except Exception:
            pass
        try:
            self.load_comms()
        except Exception:
            pass
        try:
            self._wire_debrief_tab()
            self.load_debriefs()
        except Exception:
            pass
        try:
            from utils.app_signals import app_signals
            app_signals.teamStatusChanged.connect(self._on_team_updates)
            app_signals.teamAssetsChanged.connect(self._on_team_updates)
        except Exception:
            pass
        try:
            self.load_vehicles()
        except Exception:
            pass
        # Auto-refresh vehicles when team status/assets change
        try:
            from utils.app_signals import app_signals
            app_signals.teamStatusChanged.connect(self._on_team_updates)
            app_signals.teamAssetsChanged.connect(self._on_team_updates)
        except Exception:
            pass

    def _status_background_color(self, status: str | None) -> str:
        key = str(status or "").strip().lower()
        return self._status_bg_colors.get(key, "#ffffff")

    def _apply_status_background(self, status: str | None) -> None:
        try:
            color = QColor(self._status_background_color(status))
            pal = self.palette()
            pal.setColor(QPalette.Window, color)
            self.setPalette(pal)
            try:
                self.setAutoFillBackground(True)
            except Exception:
                pass
            try:
                self.update()
            except Exception:
                pass
        except Exception:
            pass

    def _normalize_header_value(self, field: str, value: Any) -> str:
        text = '' if value is None else str(value).strip()
        if field == 'task_type' and text.lower().startswith('(select'):
            return ''
        return text

    def _category_type_text(self) -> str:
        try:
            category = self._cat.currentText() if hasattr(self, '_cat') else ''
        except Exception:
            category = ''
        try:
            task_type = self._typ.currentText() if hasattr(self, '_typ') else ''
        except Exception:
            task_type = ''
        category = str(category or '').strip()
        task_type = str(task_type or '').strip()
        if task_type.lower().startswith('(select'):
            task_type = ''
        parts = [p for p in (category, task_type) if p]
        return ' / '.join(parts)

    def _update_category_type_display(self) -> None:
        widget = getattr(self, '_category_type_display', None)
        if widget is None:
            return
        try:
            widget.setText(self._category_type_text())
        except Exception:
            pass

    def _update_window_title(self) -> None:
        try:
            cat = (self._header_field_cache.get('category') or '').strip()
        except Exception:
            cat = ''
        try:
            typ = (self._header_field_cache.get('task_type') or '').strip()
        except Exception:
            typ = ''
        try:
            tid = (self._header_field_cache.get('task_id') or str(self._task_id)).strip()
        except Exception:
            tid = str(self._task_id)
        try:
            assign = (self._header_field_cache.get('assignment') or '').strip()
        except Exception:
            assign = ''
        try:
            primary = self._primary_team_name_lbl.text().strip() if hasattr(self, '_primary_team_name_lbl') and self._primary_team_name_lbl is not None else ''
        except Exception:
            primary = ''
        bracket = '[' + ' / '.join([p for p in (cat, typ) if p]) + ']'
        if bracket == '[]':
            bracket = '[Task]'
        parts = [bracket, tid]
        if assign:
            parts.append(assign)
        if primary:
            parts.append(primary)
        self.setWindowTitle(' - '.join(parts))

    def _persist_header_fields(self, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        norm: Dict[str, str] = {}
        for key, val in updates.items():
            try:
                norm[key] = self._normalize_header_value(key, val)
            except Exception:
                norm[key] = '' if val is None else str(val)
        changed = {k: v for k, v in norm.items() if self._header_field_cache.get(k, '') != v}
        if not changed:
            return
        try:
            from modules.operations.taskings.repository import update_task_header
            update_task_header(int(self._task_id), dict(changed))
            self._header_field_cache.update(changed)
            try:
                from utils.app_signals import app_signals
                app_signals.taskHeaderChanged.emit(int(self._task_id), dict(changed))
            except Exception:
                pass
            try:
                # Update window title when header fields affecting it change
                if any(k in changed for k in ('category', 'task_type', 'task_id', 'assignment')):
                    self._update_window_title()
            except Exception:
                pass
        except Exception:
            pass

    def _on_status_changed(self, status: str) -> None:
        try:
            self._apply_status_background(status)
        except Exception:
            pass
        if getattr(self, '_loading_header', False):
            return
        self._persist_header_fields({'status': status})

    def _on_task_type_changed(self, value: str) -> None:
        if getattr(self, '_loading_header', False):
            return
        self._persist_header_fields({'task_type': value})
        try:
            self._update_category_type_display()
        except Exception:
            pass

    def _on_priority_changed(self, value: str) -> None:
        if getattr(self, '_loading_header', False):
            return
        self._persist_header_fields({'priority': value})

    def _on_header_line_edit(self, field: str, widget: QLineEdit) -> None:
        if getattr(self, '_loading_header', False):
            return
        if widget is None:
            return
        self._persist_header_fields({field: widget.text()})

    def _task_types_for_category(self, category: str | None) -> List[str]:
        try:
            look = dict(self._lookups.get("types_by_cat") or {})
        except Exception:
            look = {}
        key = str(category) if category is not None else ""
        types = look.get(key)
        if types is None:
            types = look.get("<New Task>") or []
        return [str(t) for t in types]

    def _set_combo_value(self, combo: QComboBox, value: str, *, allow_append: bool = True) -> None:
        if combo is None:
            return
        try:
            combo.blockSignals(True)
            target = str(value or "")
            idx = combo.findText(target, Qt.MatchFixedString) if target else -1
            if idx < 0 and target and allow_append:
                combo.addItem(target)
                idx = combo.count() - 1
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif combo.count():
                combo.setCurrentIndex(0)
        except Exception:
            pass
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass

    def _refresh_task_type_options(self, category: str | None, selected: str | None = None, *, keep_current_if_valid: bool = False) -> None:
        combo = getattr(self, "_typ", None)
        if combo is None:
            return
        try:
            combo.blockSignals(True)
            options = self._task_types_for_category(category)
            options = [str(o) for o in options if str(o)]
            if options:
                first = options[0].strip().lower()
                if not first.startswith("(select"):
                    options.insert(0, "(select type)")
            else:
                options = ["(select type)"]
            current = combo.currentText()
            target = selected if selected is not None else (current if keep_current_if_valid else "")
            combo.clear()
            seen = set()
            for opt in options:
                if opt not in seen:
                    combo.addItem(opt)
                    seen.add(opt)
            if target:
                idx = combo.findText(target, Qt.MatchFixedString)
                if idx < 0:
                    combo.addItem(target)
                    idx = combo.count() - 1
            else:
                idx = -1
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif combo.count():
                combo.setCurrentIndex(0)
        except Exception:
            pass
        finally:
            try:
                combo.blockSignals(False)
            except Exception:
                pass
        try:
            self._update_category_type_display()
        except Exception:
            pass

    def _on_category_changed(self, category: str) -> None:
        try:
            self._refresh_task_type_options(category, selected=None)
        except Exception:
            pass
        if getattr(self, '_loading_header', False):
            return
        updates = {'category': category}
        try:
            updates['task_type'] = self._typ.currentText() if hasattr(self, '_typ') else ''
        except Exception:
            updates['task_type'] = ''
        self._persist_header_fields(updates)
        try:
            self._update_category_type_display()
        except Exception:
            pass

    # --- Data Bridges ---
    def _ib(self):
        from bridge.incident_bridge import IncidentBridge

        return IncidentBridge()

    def _on_team_updates(self, *_args) -> None:
        try:
            self.load_vehicles()
        except Exception:
            pass

    def _repo_detail(self) -> Dict[str, Any] | None:
        try:
            from modules.operations.taskings.repository import get_task_detail

            return _to_variant(get_task_detail(self._task_id))  # type: ignore[no-any-return]
        except Exception:
            return None

    def _primary_team_name(self, detail: Dict[str, Any] | None) -> str:
        try:
            teams = (detail or {}).get("teams") or []
            if not teams:
                return ""
            for t in teams:
                if t.get("primary"):
                    return str(t.get("team_name") or "")
            return str(teams[0].get("team_name") or "")
        except Exception:
            return ""

    # --- Attachments ---
    def load_attachments(self) -> None:
        try:
            from modules.operations.taskings.attachments import list_attachments
            rows = list_attachments(int(self._task_id))
        except Exception:
            rows = []
        try:
            self._att_model.setRowCount(0)
        except Exception:
            return
        for r in rows:
            items = []
            items.append(QStandardItem(str(r.get("filename") or "")))
            items.append(QStandardItem(str(r.get("type") or "")))
            items.append(QStandardItem(str(r.get("uploaded_by") or "")))
            items.append(QStandardItem(str(_fmt_ts(r.get("timestamp") or ""))))
            try:
                sizeb = int(r.get("size_bytes") or 0)
                size_txt = f"{max(1, sizeb//1024)} KB" if sizeb else ""
            except Exception:
                size_txt = ""
            items.append(QStandardItem(size_txt))
            items.append(QStandardItem(str(r.get("versions") or 1)))
            id_item = QStandardItem(str(r.get("id") or ""))
            items.append(id_item)
            self._att_model.appendRow(items)

    def _selected_attachment_id(self) -> int | None:
        try:
            sel = self._att_table.selectionModel().selectedRows()
            if not sel:
                return None
            row = sel[0].row()
            idx = self._att_model.index(row, 6)
            val = self._att_model.data(idx)
            return int(val) if val is not None and str(val).strip() != "" else None
        except Exception:
            return None

    def _att_upload(self) -> None:
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, "Select file to upload")
            if not path:
                return
            try:
                from utils.state import AppState
                uid = AppState.get_active_user_id()
            except Exception:
                uid = None
            from modules.operations.taskings.attachments import upload_attachment
            res = upload_attachment(int(self._task_id), str(path), uid)
            if res.get("warning"):
                try:
                    QMessageBox.information(self, "File Size Warning", str(res.get("warning")))
                except Exception:
                    pass
            self.load_attachments()
        except Exception as e:
            try:
                QMessageBox.warning(self, "Upload Failed", f"Could not upload file: {e}")
            except Exception:
                pass

    def _att_open(self) -> None:
        aid = self._selected_attachment_id()
        if not aid:
            return
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            from modules.operations.taskings.attachments import get_attachment_file
            p = get_attachment_file(int(self._task_id), int(aid), None)
            if p:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
        except Exception:
            pass

    def _att_annotate(self) -> None:
        aid = self._selected_attachment_id()
        if not aid:
            return
        try:
            text, ok = QInputDialog.getText(self, "Add Annotation", "Note:")
        except Exception:
            ok = False
            text = ""
        if not ok or not str(text or "").strip():
            return
        try:
            try:
                from utils.state import AppState
                uid = AppState.get_active_user_id()
            except Exception:
                uid = None
            from modules.operations.taskings.attachments import annotate_attachment
            annotate_attachment(int(self._task_id), int(aid), str(text), uid)
        except Exception:
            pass

    def _att_generate(self) -> None:
        try:
            # Modal dialog to choose forms and team association
            from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QCheckBox, QComboBox
            dlg = QDialog(self)
            dlg.setWindowTitle("Generate Forms")
            v = QVBoxLayout(dlg)
            row1 = QHBoxLayout();
            cb204 = QCheckBox("ICS 204", dlg); cb204.setChecked(True)
            cb109 = QCheckBox("CAPF 109", dlg)
            cb104 = QCheckBox("SAR 104", dlg)
            for w in (cb204, cb109, cb104): row1.addWidget(w)
            v.addLayout(row1)
            from modules.operations.taskings.repository import list_task_teams, export_assignment_forms
            teams = []
            try:
                teams = list_task_teams(int(self._task_id))
            except Exception:
                teams = []
            team_row = QHBoxLayout(); team_row.addWidget(QLabel("Associate with team:", dlg))
            team_combo = QComboBox(dlg)
            team_combo.addItem("(none)")
            team_ids: list[int] = []
            for t in (teams or []):
                try:
                    label = f"{getattr(t,'team_name', '')} ({getattr(t,'sortie_number','')})".strip()
                    team_combo.addItem(label or "Team")
                    team_ids.append(int(getattr(t,'id',0)))
                except Exception:
                    continue
            team_row.addWidget(team_combo)
            v.addLayout(team_row)
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
            v.addWidget(btns)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            if dlg.exec() != QDialog.Accepted:
                return
            forms = []
            if cb204.isChecked(): forms.append("ICS 204")
            if cb109.isChecked(): forms.append("CAPF 109")
            if cb104.isChecked(): forms.append("SAR 104")
            # export and attach
            sel_index = team_combo.currentIndex()
            team_dict = None
            if sel_index > 0:
                team_id = team_ids[sel_index-1]
                for t in (teams or []):
                    try:
                        if int(getattr(t,'id',0)) == int(team_id):
                            from dataclasses import asdict, is_dataclass
                            team_dict = asdict(t) if is_dataclass(t) else dict(t)
                            break
                    except Exception:
                        pass
            exports = export_assignment_forms(int(self._task_id), forms, team_dict)
            files = [r.get("file_path") for r in exports if isinstance(r, dict) and r.get("file_path")]
            from modules.operations.taskings.attachments import attach_files
            res = attach_files(int(self._task_id), [str(p) for p in files], associated_team=team_dict)
            self.load_attachments()
        except Exception:
            pass

    def _att_delete(self) -> None:
        aid = self._selected_attachment_id()
        if not aid:
            return
        try:
            from modules.operations.taskings.attachments import delete_attachment
            if delete_attachment(int(self._task_id), int(aid)):
                self.load_attachments()
        except Exception:
            pass

    # --- Header ---
    def _load_header(self) -> None:
        self._loading_header = True
        try:
            d = self._repo_detail()
            try:
                t = (d or {}).get("task") or {}
                tid = t.get("task_id") or self._task_id
                title = t.get("title") or ""
                # Populate editable header fields
                try:
                    if hasattr(self, '_task_id_edit'):
                        self._task_id_edit.setText(str(tid))
                    if hasattr(self, '_title_edit'):
                        self._title_edit.setText(str(title))
                    if hasattr(self, '_location_edit'):
                        self._location_edit.setText(str(t.get('location') or ''))
                    if hasattr(self, '_assignment_edit'):
                        self._assignment_edit.setText(str(t.get('assignment') or ''))
                except Exception:
                    pass
                try:
                    cat_val = str(t.get('category') or '')
                    type_val = str(t.get('task_type') or '')
                    prio_val = str(t.get('priority') or '')
                    status_val = str(t.get('status') or '')
                    cat_target = cat_val
                    if hasattr(self, '_cat'):
                        if not cat_target:
                            try:
                                cat_target = (self._lookups.get('categories') or [''])[0]
                            except Exception:
                                cat_target = ''
                        self._set_combo_value(self._cat, cat_target)
                    if hasattr(self, '_typ'):
                        self._refresh_task_type_options(cat_target, selected=type_val or None)
                    if hasattr(self, '_prio'):
                        self._set_combo_value(self._prio, prio_val or '')
                    if hasattr(self, '_stat'):
                        self._set_combo_value(self._stat, status_val or '')
                    current_status = status_val
                    try:
                        if hasattr(self, '_stat'):
                            current_status = self._stat.currentText()
                        self._apply_status_background(current_status)
                    except Exception:
                        pass
                    try:
                        self._header_field_cache.update({
                            'task_id': self._normalize_header_value('task_id', tid),
                            'title': self._normalize_header_value('title', title),
                            'location': self._normalize_header_value('location', t.get('location')),
                            'assignment': self._normalize_header_value('assignment', t.get('assignment')),
                            'category': self._normalize_header_value('category', self._cat.currentText() if hasattr(self, '_cat') else cat_target),
                            'task_type': self._normalize_header_value('task_type', self._typ.currentText() if hasattr(self, '_typ') else type_val),
                            'priority': self._normalize_header_value('priority', self._prio.currentText() if hasattr(self, '_prio') else prio_val),
                            'status': self._normalize_header_value('status', current_status),
                        })
                        try:
                            self._update_category_type_display()
                        except Exception:
                            pass
                    except Exception:
                        pass
                except Exception:
                    pass
                # Populate display-only primary team fields
                try:
                    teams = (d or {}).get('teams') or []
                    primary = None
                    for tt in teams:
                        if (tt or {}).get('primary'):
                            primary = tt
                            break
                    if primary is None and teams:
                        primary = teams[0]
                    if primary is None:
                        name = leader = phone = ''
                    else:
                        name = str(primary.get('team_name') or '')
                        leader = str(primary.get('team_leader') or '')
                        phone = str(primary.get('team_leader_phone') or '')
                    if hasattr(self, '_primary_team_name_lbl'):
                        self._primary_team_name_lbl.setText(name)
                    if hasattr(self, '_primary_team_leader_lbl'):
                        self._primary_team_leader_lbl.setText(leader)
                    if hasattr(self, '_primary_team_phone_lbl'):
                        self._primary_team_phone_lbl.setText(phone)
                except Exception:
                    pass
                try:
                    # Update title now that header and primary have been set
                    self._update_window_title()
                except Exception:
                    pass
            except Exception:
                pass
        finally:
            self._loading_header = False

    # --- Narrative Ops ---
    def load_narrative(self) -> None:
        try:
            rows: List[Dict[str, Any]] = self._ib().listTaskNarrative(self._task_id, "", False, "") or []
        except Exception:
            rows = []
        self._nar_model.removeRows(0, self._nar_model.rowCount())
        for r in rows:
            rid = int(r.get("id") or 0)
            ts = _fmt_ts(r.get("timestamp"))
            entry = str(r.get("narrative") or "")
            by = str(r.get("entered_by") or "")
            team = str(r.get("team_num") or "")
            crit = 1 if (r.get("critical") in (1, "1", True, "true", "True")) else 0
            items = [
                QStandardItem(str(rid)),
                QStandardItem(ts),
                QStandardItem(entry),
                QStandardItem(by),
                QStandardItem(team),
                QStandardItem("Yes" if crit else "No"),
            ]
            items[0].setData(rid, Qt.EditRole)
            # Ensure display shows Yes/No and edit role carries 1/0
            items[5].setData("Yes" if crit else "No", Qt.DisplayRole)
            items[5].setData(int(crit), Qt.EditRole)
            items[5].setEditable(True)
            # Add per-row ICS-214 action column
            act = QStandardItem("214+")
            act.setEditable(False)
            items.append(act)
            self._nar_model.appendRow(items)
            try:
                self._apply_row_critical_highlight(self._nar_model.rowCount() - 1)
            except Exception:
                pass
        # Default widths
        self._nar_table.setColumnWidth(1, 120)  # Date/Time (UTC)
        self._nar_table.setColumnWidth(3, 120)  # Entered By
        self._nar_table.setColumnWidth(4, 120)  # Team
        self._nar_table.setColumnWidth(5, 50)   # Critical
        try:
            self._nar_table.setColumnWidth(6, 50) # Action ("214+")
        except Exception:
            pass
        # Header labels remain static (no width suffixes)
        try:
            # Default sort by time desc
            self._nar_table.sortByColumn(1, Qt.DescendingOrder)
        except Exception:
            pass

    def add_narrative(self) -> None:
        # Prefer the always-visible top entry widgets if present
        entry_widget = getattr(self, '_nar_entry_top', None) or getattr(self, '_nar_entry', None)
        crit_widget = getattr(self, '_nar_crit_top', None) or getattr(self, '_nar_crit', None)
        if entry_widget is None or crit_widget is None:
            return
        try:
            text = entry_widget.toPlainText().strip()
        except Exception:
            try:
                text = entry_widget.text().strip()
            except Exception:
                text = ""
        if not text:
            return
        payload = {
            "taskid": self._task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "narrative": text,
            "entered_by": "",
            "team_num": "",
            "critical": 1 if (getattr(crit_widget, 'isChecked', lambda: False)() or getattr(crit_widget, 'currentIndex', lambda: 0)() == 1) else 0,
        }
        try:
            ib = self._ib()
            ib.createTaskNarrative(payload)
            try:
                entry_widget.clear()
            except Exception:
                pass
            try:
                if hasattr(crit_widget, 'setChecked'):
                    crit_widget.setChecked(False)
                elif hasattr(crit_widget, 'setCurrentIndex'):
                    crit_widget.setCurrentIndex(0)
            except Exception:
                pass
            self.load_narrative()
        except Exception:
            # Ignore failures silently for now
            pass

    def _add_top_entry_to_ics214(self) -> None:
        try:
            entry_widget = getattr(self, '_nar_entry_top', None)
            crit_widget = getattr(self, '_nar_crit_top', None)
            if entry_widget is None:
                return
            try:
                text = entry_widget.toPlainText().strip()
            except Exception:
                text = getattr(entry_widget, 'text', lambda: "")().strip()
            if not text:
                return
            crit = False
            try:
                if hasattr(crit_widget, 'isChecked'):
                    crit = bool(crit_widget.isChecked())
                elif hasattr(crit_widget, 'currentIndex'):
                    crit = (crit_widget.currentIndex() == 1)
            except Exception:
                crit = False
            inc, sid = self._get_ops_214_stream()
            ok = False
            if inc and sid:
                try:
                    from modules.ics214 import services
                    from modules.ics214.schemas import EntryCreate
                    from utils.state import AppState
                    uid = AppState.get_active_user_id()
                    services.add_entry(str(inc), str(sid), EntryCreate(text=text, critical_flag=bool(crit), actor_user_id=str(uid) if uid is not None else None))
                    ok = True
                    self._load_ics214()
                except Exception:
                    ok = False
            try:
                from PySide6.QtWidgets import QMessageBox
                if ok:
                    QMessageBox.information(self, "ICS-214", "Added entry to Team log.")
                else:
                    QMessageBox.warning(self, "ICS-214", "Unable to add to ICS-214. Ensure a team is selected and an active incident is set.")
            except Exception:
                pass
        except Exception:
            pass

    def _on_nar_table_clicked(self, index) -> None:
        try:
            if not index.isValid():
                return
            # Action column index is last ("214+")
            if index.column() != (self._nar_model.columnCount() - 1):
                return
            r = index.row()
            text = str(self._nar_model.item(r, 2).text() or "")
            crit_txt = str(self._nar_model.item(r, 5).text() or "No")
            crit = crit_txt.strip().lower() in ("yes", "1", "true")
            inc, sid = self._get_ops_214_stream()
            ok = False
            if inc and sid:
                try:
                    from modules.ics214 import services
                    from modules.ics214.schemas import EntryCreate
                    from utils.state import AppState
                    uid = AppState.get_active_user_id()
                    services.add_entry(str(inc), str(sid), EntryCreate(text=text, critical_flag=bool(crit), actor_user_id=str(uid) if uid is not None else None))
                    ok = True
                    self._load_ics214()
                except Exception:
                    ok = False
            try:
                from PySide6.QtWidgets import QMessageBox
                if ok:
                    QMessageBox.information(self, "ICS-214", "Added entry to Team log.")
                else:
                    QMessageBox.warning(self, "ICS-214", "Unable to add to ICS-214. Ensure a team is selected and an active incident is set.")
            except Exception:
                pass
        except Exception:
            pass

    def _on_nar_button_clicked(self, index) -> None:
        # Same behavior as table-click handler but triggered by button delegate
        self._on_nar_table_clicked(index)

    # --- Log Tab Ops --------------------------------------------------------
    def _load_task_log(self) -> None:
        try:
            from modules.operations.taskings.repository import list_audit_logs
            rows = list_audit_logs(
                int(self._task_id),
                search=str(self._tlog_search.text() or ""),
                date_from=str(self._tlog_from.text() or "") or None,
                date_to=str(self._tlog_to.text() or "") or None,
                field_filter=str(self._tlog_field.text() or ""),
                limit=500,
            )
        except Exception:
            rows = []
        try:
            self._model_tlog.removeRows(0, self._model_tlog.rowCount())
        except Exception:
            pass
        import json
        for r in rows:
            raw_ts = str(r.get("ts_utc") or r.get("timestamp") or "")
            ts = _fmt_ts(raw_ts)
            field = r.get("field_changed") or r.get("action") or ""
            old = r.get("old_value") or ""
            new = r.get("new_value") or ""
            by = r.get("changed_by_display") or r.get("user_id") or ""
            # Fallback: parse JSON detail if structured columns are absent
            if (not r.get("field_changed")) and r.get("detail"):
                try:
                    d = json.loads(r.get("detail") or "{}")
                    field = field or d.get("field") or d.get("field_changed") or field
                    old = old or d.get("old") or d.get("old_value") or old
                    new = new or d.get("new") or d.get("new_value") or new
                except Exception:
                    pass
            self._model_tlog.appendRow([QStandardItem(str(ts)), QStandardItem(str(field)), QStandardItem(str(old)), QStandardItem(str(new)), QStandardItem(str(by))])

    def _export_task_log(self) -> None:
        try:
            from modules.operations.taskings.repository import export_audit_csv
            p = export_audit_csv(
                int(self._task_id),
                search=str(self._tlog_search.text() or ""),
                date_from=str(self._tlog_from.text() or "") or None,
                date_to=str(self._tlog_to.text() or "") or None,
                field_filter=str(self._tlog_field.text() or ""),
            )
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Task Log Export", f"Saved CSV to:\n{p}")
        except Exception:
            pass

    def _load_team_log(self) -> None:
        try:
            from modules.operations.taskings.repository import list_team_status_log
            rows = list_team_status_log(int(self._task_id))
        except Exception:
            rows = []
        try:
            self._model_teamlog.removeRows(0, self._model_teamlog.rowCount())
        except Exception:
            pass
        for r in rows:
            self._model_teamlog.appendRow([QStandardItem(_fmt_ts(str(r.get("timestamp") or ""))), QStandardItem(str(r.get("team") or "")), QStandardItem(str(r.get("status") or ""))])

    def _get_ops_214_stream(self):
        try:
            from utils import incident_context
            from modules.ics214 import services
            from modules.ics214.schemas import StreamCreate
            inc = incident_context.get_active_incident_id()
            if not inc:
                return None, None
            # Use task id to scope the ICS-214 stream
            task_id = int(self._task_id)
            streams = services.list_streams(inc)
            stream = None
            for s in streams:
                try:
                    sec = getattr(s, 'section', None) or ''
                    name = getattr(s, 'name', '')
                    if (f'"ref": "task:{int(task_id)}"' in str(sec)) or (name.strip() == f"Task {int(task_id)}"):
                        stream = s
                        break
                except Exception:
                    continue
            if stream is None:
                section = '{"category": "task", "ref": "task:%d", "label": "Task %d"}' % (int(task_id), int(task_id))
                stream = services.create_stream(StreamCreate(incident_id=str(inc), name=f"Task {int(task_id)}", section=section, kind="task"))
            return inc, getattr(stream, "id", None)
        except Exception:
            return None, None

    def _load_ics214(self) -> None:
        inc, sid = self._get_ops_214_stream()
        if not inc or not sid:
            try:
                self._model_214.removeRows(0, self._model_214.rowCount())
            except Exception:
                pass
            return
        try:
            from modules.ics214 import services
            rows = services.list_entries(inc, sid) or []
        except Exception:
            rows = []
        try:
            self._model_214.removeRows(0, self._model_214.rowCount())
        except Exception:
            pass
        for r in rows:
            it_ts = QStandardItem(_fmt_ts(str(r.get("timestamp_utc") or "")))
            it_entry = QStandardItem(str(r.get("text") or ""))
            it_by = QStandardItem(str(r.get("actor_user_id") or ""))
            try:
                it_ts.setData(str(r.get("id") or ""), Qt.UserRole)
            except Exception:
                pass
            self._model_214.appendRow([it_ts, it_entry, it_by])

    def _export_ics214(self) -> None:
        try:
            inc, sid = self._get_ops_214_stream()
            if not inc or not sid:
                return
            from modules.ics214 import services
            from modules.ics214.schemas import ExportRequest
            pdf = services.export_stream(inc, sid, ExportRequest())
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "ICS-214 Export", f"Exported to: {pdf.file_path}")
        except Exception:
            pass

    def _selected_214_entry_id(self) -> str | None:
        try:
            idxs = self._tbl_214.selectionModel().selectedRows()
            if not idxs:
                return None
            ridx = idxs[0]
            return str(self._model_214.item(ridx.row(), 0).data(Qt.UserRole) or "") or None
        except Exception:
            return None

    def _delete_ics214_entry(self) -> None:
        try:
            inc, _sid = self._get_ops_214_stream()
            entry_id = self._selected_214_entry_id()
            if not inc or not entry_id:
                return
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.warning(self, "Delete 214 Entry", "Delete selected entry?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            from modules.ics214 import services
            services.delete_entry(inc, entry_id)
            self._load_ics214()
        except Exception:
            pass

    def _edit_ics214_entry(self) -> None:
        try:
            inc, _sid = self._get_ops_214_stream()
            entry_id = self._selected_214_entry_id()
            if not inc or not entry_id:
                return
            try:
                r = self._tbl_214.selectionModel().selectedRows()[0].row()
                current = str(self._model_214.item(r, 1).text() or "")
            except Exception:
                current = ""
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton
            dlg = QDialog(self); dlg.setWindowTitle("Edit 214 Entry")
            lay = QVBoxLayout(dlg)
            te = QTextEdit(dlg); te.setPlainText(current); lay.addWidget(te)
            btns = QHBoxLayout(); ok = QPushButton("Save"); cancel = QPushButton("Cancel"); btns.addStretch(1); btns.addWidget(ok); btns.addWidget(cancel); lay.addLayout(btns)
            ok.clicked.connect(dlg.accept); cancel.clicked.connect(dlg.reject)
            if dlg.exec_():
                new_txt = te.toPlainText().strip()
                if new_txt:
                    from modules.ics214 import services
                    from modules.ics214.schemas import EntryUpdate
                    services.update_entry(inc, entry_id, EntryUpdate(text=new_txt))
                    self._load_ics214()
        except Exception:
            pass

    def _is_row_critical(self, row: int) -> bool:
        try:
            idx = self._nar_model.index(row, 5)
            val = self._nar_model.data(idx, Qt.EditRole)
            if isinstance(val, (int, bool)):
                return bool(val)
            txt = str(self._nar_model.data(idx, Qt.DisplayRole) or "")
            return txt.strip().lower() in ("yes", "1", "true")
        except Exception:
            return False

    def _apply_row_critical_highlight(self, row: int) -> None:
        try:
            is_crit = self._is_row_critical(row)
            color = QColor(Qt.red).lighter(160) if is_crit else None
            # Block signals to avoid recursive dataChanged emissions
            try:
                self._nar_model.blockSignals(True)
            except Exception:
                pass
            try:
                for c in range(self._nar_model.columnCount()):
                    it = self._nar_model.item(row, c)
                    if it is None:
                        continue
                    it.setData(color, Qt.BackgroundRole)
            finally:
                try:
                    self._nar_model.blockSignals(False)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_narrative_data_changed(self, topLeft, bottomRight, roles=None) -> None:
        try:
            start_row = int(topLeft.row())
            end_row = int(bottomRight.row())
            start_col = int(topLeft.column())
            end_col = int(bottomRight.column())
        except Exception:
            return
        # Only react to edits that include the Critical column (index 5)
        if 5 < start_col or 5 > end_col:
            return
        # If roles are provided and do not include Edit/Display roles, ignore to avoid loops
        try:
            if roles and all(r not in (Qt.EditRole, Qt.DisplayRole) for r in roles):
                return
        except Exception:
            return
        for r in range(start_row, end_row + 1):
            self._apply_row_critical_highlight(r)

    # --- Save/Load Header Ops ---
    def _save_header(self) -> None:
        try:
            from modules.operations.taskings.repository import update_task_header
            typ_val = self._typ.currentText().strip() if hasattr(self, '_typ') else ''
            if typ_val in ('(select type)', '(select category first)'):
                typ_val = ''
            payload = {
                'task_id': self._task_id_edit.text().strip() if hasattr(self, '_task_id_edit') else str(self._task_id),
                'title': self._title_edit.text().strip() if hasattr(self, '_title_edit') else '',
                'location': self._location_edit.text().strip() if hasattr(self, '_location_edit') else '',
                'assignment': self._assignment_edit.text().strip() if hasattr(self, '_assignment_edit') else '',
                'category': self._cat.currentText().strip() if hasattr(self, '_cat') else '',
                'task_type': typ_val,
                'priority': self._prio.currentText().strip() if hasattr(self, '_prio') else '',
                'status': self._stat.currentText().strip() if hasattr(self, '_stat') else '',
            }
            update_task_header(int(self._task_id), payload)
            try:
                self._load_header()
            except Exception:
                pass
        except Exception:
            pass

    # --- Vehicles Ops ---
    def load_vehicles(self) -> None:
        try:
            from modules.operations.taskings.repository import list_task_vehicles, list_task_aircraft
            vrows = list_task_vehicles(int(self._task_id)) or []
            arows = list_task_aircraft(int(self._task_id)) or []
        except Exception:
            vrows = []
            arows = []
        # Vehicles table
        try:
            self._veh_model.removeRows(0, self._veh_model.rowCount())
            for v in vrows:
                active = bool(v.get('active'))
                it_active = QStandardItem("")
                it_active.setCheckable(True)
                it_active.setCheckState(Qt.Checked if active else Qt.Unchecked)
                it_active.setEditable(False)
                items = [
                    it_active,
                    QStandardItem(str(v.get('id') or '')),
                    QStandardItem(str(v.get('license_plate') or '')),
                    QStandardItem(str(v.get('type') or '')),
                    QStandardItem(str(v.get('organization') or '')),
                ]
                self._veh_model.appendRow(items)
        except Exception:
            pass
        # Aircraft table
        try:
            self._air_model.removeRows(0, self._air_model.rowCount())
            for a in arows:
                active = bool(a.get('active'))
                it_active = QStandardItem("")
                it_active.setCheckable(True)
                it_active.setCheckState(Qt.Checked if active else Qt.Unchecked)
                it_active.setEditable(False)
                items = [
                    it_active,
                    QStandardItem(str(a.get('callsign') or '')),
                    QStandardItem(str(a.get('tail_number') or '')),
                    QStandardItem(str(a.get('type') or '')),
                    QStandardItem(str(a.get('organization') or '')),
                ]
                self._air_model.appendRow(items)
        except Exception:
            pass
        # Show/Hide aircraft section if empty
        try:
            has_air = self._air_model.rowCount() > 0
            self._air_label.setVisible(has_air)
            self._air_table.setVisible(has_air)
        except Exception:
            pass

    # --- Communications Ops ---
    def load_comms(self) -> None:
        try:
            from modules.operations.taskings.repository import list_task_comms
            rows = list_task_comms(int(self._task_id)) or []
        except Exception:
            rows = []
        try:
            self._comms_model.removeRows(0, self._comms_model.rowCount())
        except Exception:
            pass

        def _fmt_freq(v: Any) -> str:
            try:
                if v is None or v == "":
                    return ""
                f = float(v)
                s = ("{:.4f}".format(f)).rstrip("0").rstrip(".")
                return s
            except Exception:
                return str(v or "")

        for r in rows:
            try:
                rid = int(r.get("id") or 0)
            except Exception:
                rid = 0
            ch_item = QStandardItem(str(r.get("channel_name") or ""))
            ch_item.setEditable(True)
            ch_item.setData(rid, Qt.UserRole)
            ch_item.setData(r.get("incident_channel_id"), Qt.UserRole + 1)

            zone_item = QStandardItem(str(r.get("zone") or "")); zone_item.setEditable(False)
            num = r.get("channel_number")
            num_item = QStandardItem(str(num if num is not None else "")); num_item.setEditable(False)
            func_item = QStandardItem(str(r.get("function") or "")); func_item.setEditable(True)
            rx_item = QStandardItem(_fmt_freq(r.get("rx_frequency"))); rx_item.setEditable(False)
            rxt_item = QStandardItem(str(r.get("rx_tone") or "")); rxt_item.setEditable(False)
            tx_item = QStandardItem(_fmt_freq(r.get("tx_frequency"))); tx_item.setEditable(False)
            txt_item = QStandardItem(str(r.get("tx_tone") or "")); txt_item.setEditable(False)
            mode_item = QStandardItem(str(r.get("mode") or "")); mode_item.setEditable(False)
            rem_item = QStandardItem(str(r.get("remarks") or "")); rem_item.setEditable(False)

            self._comms_model.appendRow([
                ch_item,
                zone_item,
                num_item,
                func_item,
                rx_item,
                rxt_item,
                tx_item,
                txt_item,
                mode_item,
                rem_item,
            ])

        # Widths
        try:
            defaults = [180, 100, 110, 130, 110, 110, 110, 110, 80, 240]
            for i, w in enumerate(defaults):
                if i < self._comms_model.columnCount():
                    self._comms_table.setColumnWidth(i, int(w))
        except Exception:
            pass

    # --- Teams Ops ---
    def load_teams(self) -> None:
        try:
            from modules.operations.taskings.repository import list_task_teams
            rows = list_task_teams(int(self._task_id)) or []
            try:
                rows = [_to_variant(r) for r in rows]
            except Exception:
                pass
        except Exception:
            rows = []
        self._teams_model.removeRows(0, self._teams_model.rowCount())
        def _ts2(v):
            s = _fmt_ts(v)
            if not s:
                return ""
            if " " in s:
                d, tm = s.split(" ", 1)
                return f"{d}\n{tm}"
            return s
        for t in rows:
            rid = int((t.get('id') or 0))
            primary = bool(t.get('primary') or False)
            team_name = str(t.get('team_name') or '')
            leader = str(t.get('team_leader') or '')
            phone = str(t.get('team_leader_phone') or '')
            status = str(t.get('status') or '')
            sortie = str(t.get('sortie_number') or '')
            row = [
                QStandardItem(str(rid)),
                QStandardItem('Yes' if primary else 'No'),
                QStandardItem(sortie),
                QStandardItem(team_name),
                QStandardItem(leader),
                QStandardItem(phone),
                QStandardItem(status),
                QStandardItem(_ts2(t.get('assigned_ts'))),
                QStandardItem(_ts2(t.get('briefed_ts'))),
                QStandardItem(_ts2(t.get('enroute_ts'))),
                QStandardItem(_ts2(t.get('arrival_ts'))),
                QStandardItem(_ts2(t.get('discovery_ts'))),
                QStandardItem(_ts2(t.get('complete_ts'))),
            ]
            row[0].setData(rid, Qt.EditRole)
            for idx in range(7, 13):
                row[idx].setData(int(Qt.AlignHCenter | Qt.AlignVCenter), Qt.TextAlignmentRole)
            self._teams_model.appendRow(row)
        try:
            vh = self._teams_table.verticalHeader()
            for r in range(self._teams_model.rowCount()):
                vh.resizeSection(r, 44)
        except Exception:
            pass

    def _selected_team_row(self) -> int:
        try:
            idxs = self._teams_table.selectionModel().selectedRows()
            return idxs[0].row() if idxs else -1
        except Exception:
            return -1

    def _teams_add(self) -> None:
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout as QVLay, QHBoxLayout as QHLay, QListWidget, QPushButton as PB
            from modules.operations.taskings.repository import list_all_teams, add_task_team
            teams = list_all_teams() or []
            dlg = QDialog(self); dlg.setWindowTitle('Add Team to Task')
            lay = QVLay(dlg); lw = QListWidget(dlg)
            for t in teams:
                lw.addItem(f"{t.get('team_id')} — {t.get('team_name')}  •  {t.get('team_leader')}")
            lay.addWidget(lw)
            btns = QHLay(); ok = PB('Add'); cancel = PB('Cancel')
            btns.addStretch(1); btns.addWidget(ok); btns.addWidget(cancel); lay.addLayout(btns)
            def _ok():
                try:
                    i = lw.currentRow()
                    if i >= 0:
                        tid = int(teams[i].get('team_id'))
                        add_task_team(int(self._task_id), int(tid), None, False)
                        dlg.accept()
                except Exception:
                    dlg.reject()
            ok.clicked.connect(_ok); cancel.clicked.connect(dlg.reject)
            if dlg.exec_():
                self.load_teams()
        except Exception:
            pass

    def _teams_edit(self) -> None:
        try:
            r = self._selected_team_row()
            if r < 0:
                return
            from modules.operations.taskings.repository import list_task_teams
            rows = list_task_teams(int(self._task_id)) or []
            team_id = None
            try:
                team_id = int(rows[r].team_id)
            except Exception:
                try:
                    team_id = int((_to_variant(rows[r]) or {}).get('team_id'))
                except Exception:
                    team_id = None
            if team_id is None:
                return
            from modules.operations.teams.windows import open_team_detail_window
            open_team_detail_window(int(team_id))
        except Exception:
            pass

    def _teams_change_status(self) -> None:
        try:
            r = self._selected_team_row()
            if r < 0:
                return
            try:
                from modules.operations.taskings.data.lookups import team_statuses_for_category
                options = team_statuses_for_category(self._cat.currentText())
            except Exception:
                options = ['Assigned','Briefed','En Route','On Scene','Complete','RTB']
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox as CB, QPushButton as PB
            dlg = QDialog(self); dlg.setWindowTitle('Change Team Status')
            lay = QVBoxLayout(dlg)
            cb = CB(dlg); cb.addItems(options); lay.addWidget(cb)
            btns = QHBoxLayout(); ok = PB('OK'); cancel = PB('Cancel'); btns.addStretch(1); btns.addWidget(ok); btns.addWidget(cancel); lay.addLayout(btns)
            def _ok():
                try:
                    sel = cb.currentText()
                    from modules.operations.taskings.repository import list_task_teams
                    rows = list_task_teams(int(self._task_id)) or []
                    team_id = None
                    try:
                        team_id = int(rows[r].team_id)
                    except Exception:
                        try:
                            team_id = int((_to_variant(rows[r]) or {}).get('team_id'))
                        except Exception:
                            team_id = None
                    if team_id is None:
                        dlg.reject(); return
                    from modules.operations.data.repository import set_team_status
                    set_team_status(int(team_id), sel)
                    dlg.accept()
                except Exception:
                    dlg.reject()
            ok.clicked.connect(_ok); cancel.clicked.connect(dlg.reject)
            if dlg.exec_():
                self.load_teams()
        except Exception:
            pass

    def _teams_set_primary(self) -> None:
        try:
            r = self._selected_team_row()
            if r < 0:
                return
            from modules.operations.taskings.repository import list_task_teams, set_primary_team
            rows = list_task_teams(int(self._task_id)) or []
            tt_id = None
            try:
                tt_id = int(rows[r].id)
            except Exception:
                try:
                    tt_id = int((_to_variant(rows[r]) or {}).get('id'))
                except Exception:
                    tt_id = None
            if tt_id is None:
                return
            set_primary_team(int(self._task_id), int(tt_id))
            self.load_teams()
            # Also refresh header/primary display and window title
            try:
                self._load_header()
            except Exception:
                pass
        except Exception:
            pass

    # --- Planning / Objectives linkage ---------------------------------
    def _load_planning(self) -> None:
        """Populate objectives, strategies and current links for this task."""
        try:
            from modules._infra.repository import with_incident_session
            from modules.command.models.objectives import ObjectiveRepository, ObjectiveFilters
            from utils import incident_context
            incident_id = incident_context.get_active_incident_id()
            if not incident_id:
                return
            with with_incident_session(str(incident_id)) as session:
                repo = ObjectiveRepository(session, str(incident_id))
                # Load objectives into combo (store id in UserRole)
                objectives = repo.list_objectives(ObjectiveFilters())
                self._plan_obj_cb.blockSignals(True)
                self._plan_obj_cb.clear()
                for o in objectives:
                    self._plan_obj_cb.addItem(f"{o.code} — {o.text}", o.id)
                self._plan_obj_cb.blockSignals(False)
                # Build strategies for selected objective
                self._on_plan_obj_changed(repo)
                # Load existing links for this task
                links = repo.list_links_for_task(int(self._task_id))
        except Exception:
            links = []
        try:
            self._plan_links_model.removeRows(0, self._plan_links_model.rowCount())
        except Exception:
            pass
        for link in links:
            it_id = QStandardItem(str(link.link_id))
            it_obj = QStandardItem(f"{link.objective_code} — {link.objective_text}")
            it_strat = QStandardItem(str(link.strategy_text))
            it_rm = QStandardItem("Remove")
            try:
                it_rm.setData(int(link.link_id), Qt.UserRole)
            except Exception:
                pass
            self._plan_links_model.appendRow([it_id, it_obj, it_strat, it_rm])

    def _on_plan_obj_changed(self, repo=None) -> None:
        try:
            if repo is None:
                from modules._infra.repository import with_incident_session
                from modules.command.models.objectives import ObjectiveRepository
                from utils import incident_context
                incident_id = incident_context.get_active_incident_id()
                if not incident_id:
                    return
                with with_incident_session(str(incident_id)) as session:
                    repo = ObjectiveRepository(session, str(incident_id))
            obj_id = int(self._plan_obj_cb.currentData()) if self._plan_obj_cb.count() else None
            self._plan_strat_cb.clear()
            if obj_id is None:
                return
            strategies = repo.list_strategies(int(obj_id))
            for s in strategies:
                self._plan_strat_cb.addItem(s.text, s.id)
        except Exception:
            pass

    def _link_task_to_strategy(self) -> None:
        try:
            from modules._infra.repository import with_incident_session
            from modules.command.models.objectives import ObjectiveRepository
            from utils import incident_context
            incident_id = incident_context.get_active_incident_id()
            if not incident_id:
                return
            obj_id = int(self._plan_obj_cb.currentData()) if self._plan_obj_cb.count() else None
            strat_id = int(self._plan_strat_cb.currentData()) if self._plan_strat_cb.count() else None
            if obj_id is None or strat_id is None:
                return
            with with_incident_session(str(incident_id)) as session:
                repo = ObjectiveRepository(session, str(incident_id))
                repo.link_task(int(obj_id), int(strat_id), int(self._task_id))
            self._load_planning()
        except Exception as e:
            try:
                QMessageBox.warning(self, "Planning", f"Failed to link: {e}")
            except Exception:
                pass

    def _on_plan_remove_clicked(self, index):
        try:
            link_id = index.data(Qt.UserRole)
            if link_id is None:
                # Try first column hidden id
                link_id = int(self._plan_links_model.item(index.row(), 0).text())
            from modules._infra.repository import with_incident_session
            from modules.command.models.objectives import ObjectiveRepository
            from utils import incident_context
            incident_id = incident_context.get_active_incident_id()
            if not incident_id:
                return
            with with_incident_session(str(incident_id)) as session:
                repo = ObjectiveRepository(session, str(incident_id))
                repo.unlink_task(int(link_id))
            self._load_planning()
        except Exception:
            pass

    # --- Personnel Ops ---
    def load_personnel(self) -> None:
        try:
            from modules.operations.taskings.repository import list_task_personnel
            rows = list_task_personnel(int(self._task_id)) or []
        except Exception:
            rows = []
        self._pers_model.removeRows(0, self._pers_model.rowCount())
        for p in rows:
            active = bool(p.get('active'))
            it_active = QStandardItem('')
            it_active.setCheckable(True)
            it_active.setCheckState(Qt.Checked if active else Qt.Unchecked)
            it_active.setEditable(False)
            self._pers_model.appendRow([
                it_active,
                QStandardItem(str(p.get('name') or '')),
                QStandardItem(str(p.get('id') or '')),
                QStandardItem(str(p.get('rank') or '')),
                QStandardItem(str(p.get('role') or '')),
                QStandardItem(str(p.get('organization') or '')),
                QStandardItem(str(p.get('phone') or '')),
                QStandardItem(str(p.get('team_name') or '')),
            ])

    # --- Assignment Details (Ground/Air) ---
    def _build_assignment_details_tab(self) -> QWidget:
        container = QWidget(self)
        lay = QVBoxLayout(container)
        try:
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)
        except Exception:
            pass

        # Action buttons
        btns = QHBoxLayout()
        # Export selector + button
        self._assign_export_select = QComboBox()
        try:
            self._assign_export_select.addItems(["ICS 204", "CAPF 109", "SAR 104"])
        except Exception:
            pass
        btns.addWidget(self._assign_export_select)
        self._assign_export_btn = QPushButton("Export")
        self._assign_export_btn.clicked.connect(self.export_assignment_forms)
        btns.addWidget(self._assign_export_btn)
        self._assign_open_export_btn = QPushButton("Open Export Folder")
        self._assign_open_export_btn.clicked.connect(self.open_export_folder)
        btns.addWidget(self._assign_open_export_btn)
        btns.addStretch(1)
        self._assign_save_btn = QPushButton("Save")
        self._assign_revert_btn = QPushButton("Revert")
        self._assign_save_btn.clicked.connect(self.save_assignment)
        self._assign_revert_btn.clicked.connect(self.load_assignment)
        btns.addWidget(self._assign_save_btn)
        btns.addWidget(self._assign_revert_btn)
        lay.addLayout(btns)

        # Subtabs
        sub = QTabWidget(container)
        lay.addWidget(sub, 1)

        self._assign_w: Dict[str, QWidget] = {}

        # Ground Information (scrollable)
        g_content = QWidget(sub)
        gl = QVBoxLayout(g_content)
        try:
            gl.setContentsMargins(8, 8, 8, 8)
            gl.setSpacing(8)
        except Exception:
            pass
        # Previous/Present efforts
        prev = QTextEdit(g_content); prev.setPlaceholderText("Previous Search Efforts in Area")
        pres = QTextEdit(g_content); pres.setPlaceholderText("Present Search Efforts in Area")
        self._assign_w['g_prev'] = prev
        self._assign_w['g_pres'] = pres
        gl.addWidget(QLabel("Previous and Present Search Efforts in Area"))
        gl.addWidget(prev)
        gl.addWidget(pres)
        # Time/Size
        row_ts = QHBoxLayout();
        g_time = QLineEdit(g_content); g_time.setPlaceholderText("Time Allocated")
        g_size = QLineEdit(g_content); g_size.setPlaceholderText("Size of Assignment")
        self._assign_w['g_time'] = g_time
        self._assign_w['g_size'] = g_size
        row_ts.addWidget(g_time)
        row_ts.addWidget(g_size)
        gl.addLayout(row_ts)
        # Expected POD (Responsive/Unresponsive/Clues)
        gl.addWidget(QLabel("Expected POD"))
        pod_row1 = QHBoxLayout()
        def _mk_pod(label: str, key: str) -> QComboBox:
            pod_cb = QComboBox(g_content)
            pod_cb.addItems(["High", "Medium", "Low"])
            self._assign_w[key] = pod_cb
            w = QWidget(g_content); w_l = QHBoxLayout(w); w_l.setContentsMargins(0,0,0,0); w_l.addWidget(QLabel(label)); w_l.addWidget(pod_cb); return w
        pod_row1.addWidget(_mk_pod("Responsive Subj", 'g_pod_resp'))
        pod_row1.addWidget(_mk_pod("Unresponsive Subj", 'g_pod_unresp'))
        pod_row1.addWidget(_mk_pod("Clues", 'g_pod_clues'))
        gl.addLayout(pod_row1)
        # Drop off / Pickup
        drop = QTextEdit(g_content); drop.setPlaceholderText("Drop off instructions")
        pick = QTextEdit(g_content); pick.setPlaceholderText("Pickup instructions")
        self._assign_w['g_drop'] = drop
        self._assign_w['g_pick'] = pick
        gl.addWidget(drop)
        gl.addWidget(pick)
        g_scroll = QScrollArea(sub)
        g_scroll.setWidgetResizable(True)
        g_scroll.setWidget(g_content)
        sub.addTab(g_scroll, "Ground Information")

        # Air Information (scrollable)
        a_content = QWidget(sub)
        al = QVBoxLayout(a_content)
        try:
            al.setContentsMargins(8, 8, 8, 8)
            al.setSpacing(8)
        except Exception:
            pass
        # Basic fields
        def _add_line(idkey: str, ph: str) -> QLineEdit:
            ed = QLineEdit(a_content); ed.setPlaceholderText(ph); self._assign_w[idkey] = ed; al.addWidget(ed); return ed
        def _add_text(idkey: str, ph: str) -> QTextEdit:
            ed = QTextEdit(a_content); ed.setPlaceholderText(ph); self._assign_w[idkey] = ed; al.addWidget(ed); return ed
        _add_line('a_aoo', "WMIRS Area of Operations")
        row_airports = QHBoxLayout();
        a_dep = QLineEdit(a_content); a_dep.setPlaceholderText("Dep. Airport"); self._assign_w['a_dep'] = a_dep
        a_dest = QLineEdit(a_content); a_dest.setPlaceholderText("Dest. Airport"); self._assign_w['a_dest'] = a_dest
        row_airports.addWidget(a_dep); row_airports.addWidget(a_dest); al.addLayout(row_airports)
        row_times = QHBoxLayout();
        a_etd = QLineEdit(a_content); a_etd.setPlaceholderText("ETD (HH:MM[:SS])"); self._assign_w['a_etd'] = a_etd
        a_ete = QLineEdit(a_content); a_ete.setPlaceholderText("ETE (HH:MM[:SS])"); self._assign_w['a_ete'] = a_ete
        row_times.addWidget(a_etd); row_times.addWidget(a_ete); al.addLayout(row_times)
        _add_text('a_other_ac', "Other Aircraft in Area (Location & Callsign)")
        _add_text('a_gt_in_area', "Ground Teams in Area (Location & Callsign)")
        _add_text('a_obj', "Sortie Objectives")
        _add_text('a_deliv', "Sortie Deliverables")
        _add_text('a_actions', "Actions To Be Taken on Objectives & Deliverables")
        _add_line('a_route', "Route of Flight")
        row_altspd = QHBoxLayout();
        a_alt = QLineEdit(a_content); a_alt.setPlaceholderText("Altitude Assignment & Restrictions"); self._assign_w['a_alt'] = a_alt
        a_speed = QLineEdit(a_content); a_speed.setPlaceholderText("Airspeed Expected & Restrictions"); self._assign_w['a_speed'] = a_speed
        row_altspd.addWidget(a_alt); row_altspd.addWidget(a_speed); al.addLayout(row_altspd)
        row_sepem = QHBoxLayout();
        a_sep = QLineEdit(a_content); a_sep.setPlaceholderText("Aircraft Separation (Adjoining Areas)"); self._assign_w['a_sep'] = a_sep
        a_emerg = QLineEdit(a_content); a_emerg.setPlaceholderText("Emergency/Alternate Fields"); self._assign_w['a_emerg'] = a_emerg
        row_sepem.addWidget(a_sep); row_sepem.addWidget(a_emerg); al.addLayout(row_sepem)
        _add_line('a_mlats', "Military Low Altitude Training Routes")
        _add_text('a_haz', "Hazards to Flight")
        al.addWidget(QLabel("Sortie Search Plan"))
        row_sp1 = QHBoxLayout();
        a_sp_pattern = QLineEdit(a_content); a_sp_pattern.setPlaceholderText("Search Pattern"); self._assign_w['a_sp_pattern'] = a_sp_pattern
        a_sp_vis = QLineEdit(a_content); a_sp_vis.setPlaceholderText("Search Visibility (NM)"); self._assign_w['a_sp_vis'] = a_sp_vis
        a_sp_alt = QLineEdit(a_content); a_sp_alt.setPlaceholderText("Search Altitude (AGL)"); self._assign_w['a_sp_alt'] = a_sp_alt
        row_sp1.addWidget(a_sp_pattern); row_sp1.addWidget(a_sp_vis); row_sp1.addWidget(a_sp_alt); al.addLayout(row_sp1)
        row_sp2 = QHBoxLayout();
        a_sp_speed = QLineEdit(a_content); a_sp_speed.setPlaceholderText("Search Speed (Knots)"); self._assign_w['a_sp_speed'] = a_sp_speed
        a_sp_track = QLineEdit(a_content); a_sp_track.setPlaceholderText("Track Spacing (NM)"); self._assign_w['a_sp_track'] = a_sp_track
        row_sp2.addWidget(a_sp_speed); row_sp2.addWidget(a_sp_track); al.addLayout(row_sp2)
        row_sp3 = QHBoxLayout();
        a_sp_terrain = QComboBox(a_content); a_sp_terrain.addItems(["Flat","Rolling Hills","Rugged Hills","Mountainous"]); self._assign_w['a_sp_terrain'] = a_sp_terrain
        a_sp_cover = QComboBox(a_content); a_sp_cover.addItems(["Open","Moderate","Heavy","Light Snow","Heavy Snow"]); self._assign_w['a_sp_cover'] = a_sp_cover
        a_sp_turb = QComboBox(a_content); a_sp_turb.addItems(["Light","Moderate","Heavy"]); self._assign_w['a_sp_turb'] = a_sp_turb
        row_sp3.addWidget(QLabel("Terrain")); row_sp3.addWidget(a_sp_terrain)
        row_sp3.addWidget(QLabel("Cover")); row_sp3.addWidget(a_sp_cover)
        row_sp3.addWidget(QLabel("Turbulence")); row_sp3.addWidget(a_sp_turb)
        al.addLayout(row_sp3)
        row_sp4 = QHBoxLayout();
        a_sp_pod = QLineEdit(a_content); a_sp_pod.setPlaceholderText("Probability of Detection (0–100)"); self._assign_w['a_sp_pod'] = a_sp_pod
        a_sp_tts = QLineEdit(a_content); a_sp_tts.setPlaceholderText("Time to Search Area (hrs)"); self._assign_w['a_sp_tts'] = a_sp_tts
        a_sp_ts = QLineEdit(a_content); a_sp_ts.setPlaceholderText("Time Started Search (HH:MM[:SS])"); self._assign_w['a_sp_ts'] = a_sp_ts
        row_sp4.addWidget(a_sp_pod); row_sp4.addWidget(a_sp_tts); row_sp4.addWidget(a_sp_ts); al.addLayout(row_sp4)
        row_sp5 = QHBoxLayout();
        a_sp_te = QLineEdit(a_content); a_sp_te.setPlaceholderText("Time Ended Search (HH:MM[:SS])"); self._assign_w['a_sp_te'] = a_sp_te
        a_sp_tisa = QLineEdit(a_content); a_sp_tisa.setPlaceholderText("Time in Search Area (hrs)"); self._assign_w['a_sp_tisa'] = a_sp_tisa
        a_sp_tfsa = QLineEdit(a_content); a_sp_tfsa.setPlaceholderText("Time From Search Area (hrs)"); self._assign_w['a_sp_tfsa'] = a_sp_tfsa
        row_sp5.addWidget(a_sp_te); row_sp5.addWidget(a_sp_tisa); row_sp5.addWidget(a_sp_tfsa); al.addLayout(row_sp5)
        _add_line('a_sp_total', "Total Sortie Time (hrs)")
        a_scroll = QScrollArea(sub)
        a_scroll.setWidgetResizable(True)
        a_scroll.setWidget(a_content)
        sub.addTab(a_scroll, "Air Information")

        # Validators and tooltips
        try:
            time_re = QRegularExpression(r"^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$")
            tval = QRegularExpressionValidator(time_re)
            for key in ('a_etd','a_ete','a_sp_ts','a_sp_te'):
                w = self._assign_w.get(key)
                if isinstance(w, QLineEdit):
                    w.setValidator(tval)
                    w.setToolTip('Format: HH:MM or HH:MM:SS (24-hour)')
            def _dv(minv=0.0, maxv=None, dec=3):
                v = QDoubleValidator()
                v.setBottom(float(minv))
                if maxv is not None:
                    v.setTop(float(maxv))
                v.setDecimals(int(dec))
                v.setNotation(QDoubleValidator.StandardNotation)
                return v
            for key in ('a_sp_vis','a_sp_alt','a_sp_speed','a_sp_track','a_sp_tts','a_sp_tisa','a_sp_tfsa','a_sp_total'):
                w = self._assign_w.get(key)
                if isinstance(w, QLineEdit):
                    w.setValidator(_dv(0.0, None, 3))
            wpod = self._assign_w.get('a_sp_pod')
            if isinstance(wpod, QLineEdit):
                wpod.setValidator(_dv(0.0, 100.0, 2))
                wpod.setToolTip('Probability of detection: 0–100')
        except Exception:
            pass

        # Live validation styling
        try:
            self._wire_assignment_validation_styles()
        except Exception:
            pass

        # Default to Ground tab
        try:
            sub.setCurrentIndex(0)
        except Exception:
            pass

        return container

    def load_assignment(self) -> None:
        try:
            from modules.operations.taskings.repository import get_task_assignment
            data = get_task_assignment(int(self._task_id)) or {}
        except Exception:
            data = {}
        self._bind_assignment_data(data)

    def save_assignment(self) -> None:
        if not self._validate_assignment_form():
            return
        data = self._collect_assignment_data()
        try:
            from modules.operations.taskings.repository import save_task_assignment
            save_task_assignment(int(self._task_id), data)
            # refresh to bind normalized data
            self.load_assignment()
        except Exception:
            pass

    def _validate_assignment_form(self) -> bool:
        try:
            invalids = []
            # Check any field with a validator for acceptability when non-empty
            for key, w in (self._assign_w or {}).items():
                try:
                    if isinstance(w, QLineEdit) and w.validator() is not None:
                        txt = w.text().strip()
                        if txt and not w.hasAcceptableInput():
                            invalids.append((key, txt))
                except Exception:
                    continue
            if invalids:
                try:
                    msg = "Please correct the highlighted fields (invalid format)."
                    # Focus the first one
                    k0, _ = invalids[0]
                    w0 = self._assign_w.get(k0)
                    if w0:
                        w0.setFocus()
                    QMessageBox.warning(self, "Invalid Input", msg)
                except Exception:
                    pass
                return False
        except Exception:
            return True
        return True

    def _wire_assignment_validation_styles(self) -> None:
        if getattr(self, '_assign_validation_wired', False):
            # Refresh once to ensure current visuals are correct
            try:
                self._refresh_assignment_validation_styles()
            except Exception:
                pass
            return
        def _on_changed_factory(w: QLineEdit):
            def _on_changed(_txt: str) -> None:
                try:
                    if not isinstance(w, QLineEdit):
                        return
                    txt = w.text().strip()
                    ok = True
                    if w.validator() is not None and txt:
                        ok = w.hasAcceptableInput()
                    self._set_invalid_border(w, not ok)
                except Exception:
                    pass
            return _on_changed
        try:
            for _key, w in (self._assign_w or {}).items():
                if isinstance(w, QLineEdit):
                    # connect if validator present; still add refresh for others
                    try:
                        w.textChanged.connect(_on_changed_factory(w))
                    except Exception:
                        pass
            self._assign_validation_wired = True
            self._refresh_assignment_validation_styles()
        except Exception:
            pass

    def _refresh_assignment_validation_styles(self) -> None:
        try:
            for _key, w in (self._assign_w or {}).items():
                if isinstance(w, QLineEdit):
                    txt = w.text().strip()
                    ok = True
                    try:
                        if w.validator() is not None and txt:
                            ok = w.hasAcceptableInput()
                    except Exception:
                        ok = True
                    self._set_invalid_border(w, not ok)
        except Exception:
            pass

    def _set_invalid_border(self, w: QLineEdit, invalid: bool) -> None:
        try:
            if invalid:
                w.setStyleSheet('QLineEdit { border: 2px solid #d32f2f; border-radius: 3px; }')
            else:
                # Clear to default
                w.setStyleSheet('')
        except Exception:
            pass

    def export_assignment_forms(self) -> None:
        try:
            from modules.operations.taskings.repository import export_assignment_forms
            # Determine which form(s) to export based on dropdown selection
            try:
                sel = None
                if hasattr(self, '_assign_export_select') and self._assign_export_select is not None:
                    sel = str(self._assign_export_select.currentText() or '').strip()
                forms = [sel] if sel else ["ICS 204", "CAPF 109", "SAR 104"]
            except Exception:
                forms = ["ICS 204", "CAPF 109", "SAR 104"]
            result = export_assignment_forms(int(self._task_id), forms) or []
            paths = [str((r or {}).get("file_path") or "") for r in result]
            paths = [p for p in paths if p]
            # Remember last export directory
            try:
                import os
                if paths:
                    self._last_export_dir = os.path.dirname(paths[0])
            except Exception:
                pass
            msg = "Exported:\n" + ("\n".join(paths) if paths else "(no files)")
            try:
                # Offer to open the folder directly
                mb = QMessageBox(self)
                mb.setIcon(QMessageBox.Information)
                mb.setWindowTitle("Assignment Export")
                mb.setText(msg)
                open_btn = None
                if paths:
                    open_btn = mb.addButton("Open Folder", QMessageBox.ActionRole)
                mb.addButton(QMessageBox.Ok)
                mb.exec_()
                if open_btn and mb.clickedButton() == open_btn:
                    self.open_export_folder()
            except Exception:
                QMessageBox.information(self, "Assignment Export", msg)
        except Exception as e:
            try:
                QMessageBox.warning(self, "Assignment Export", f"Export failed: {e}")
            except Exception:
                pass

    def open_export_folder(self) -> None:
        # Use last known export dir, or derive from incident id
        try:
            from pathlib import Path
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            base = None
            try:
                d = getattr(self, '_last_export_dir', None)
                if d:
                    base = Path(d)
            except Exception:
                base = None
            if base is None:
                try:
                    from utils import incident_context
                    incident_id = incident_context.get_active_incident_id() or 'unknown'
                    base = Path('data') / 'exports' / str(incident_id)
                except Exception:
                    base = Path('data') / 'exports'
            base.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(base.resolve())))
        except Exception:
            try:
                QMessageBox.information(self, "Open Folder", "Could not open export folder.")
            except Exception:
                pass

    def _bind_assignment_data(self, data: Dict[str, Any]) -> None:
        g = (data or {}).get('ground') or {}
        a = (data or {}).get('air') or {}
        sp = (a or {}).get('search_plan') or {}
        def _set_txt(key: str, val: Any) -> None:
            w = self._assign_w.get(key)
            try:
                if isinstance(w, QTextEdit):
                    w.setPlainText(str(val or ''))
                elif isinstance(w, QLineEdit):
                    w.setText(str(val or ''))
            except Exception:
                pass
        _set_txt('g_prev', g.get('previous_search_efforts'))
        _set_txt('g_pres', g.get('present_search_efforts'))
        _set_txt('g_time', g.get('time_allocated'))
        _set_txt('g_size', g.get('size_of_assignment'))
        try:
            def _sel(cb_key: str, value: Any):
                cb = self._assign_w.get(cb_key)
                if isinstance(cb, QComboBox):
                    txt = str(value or '').strip().lower()
                    for i in range(cb.count()):
                        if cb.itemText(i).strip().lower() == txt:
                            cb.setCurrentIndex(i); return
                    cb.setCurrentIndex(0)
            pod = g.get('expected_pod') or {}
            _sel('g_pod_resp', (pod or {}).get('responsive'))
            _sel('g_pod_unresp', (pod or {}).get('unresponsive'))
            _sel('g_pod_clues', (pod or {}).get('clues'))
        except Exception:
            pass
        _set_txt('g_drop', g.get('drop_off_instructions'))
        _set_txt('g_pick', g.get('pickup_instructions'))

        _set_txt('a_aoo', a.get('wmirs_aoo'))
        _set_txt('a_dep', a.get('dep_airport'))
        _set_txt('a_dest', a.get('dest_airport'))
        _set_txt('a_etd', a.get('etd'))
        _set_txt('a_ete', a.get('ete'))
        _set_txt('a_other_ac', a.get('other_aircraft'))
        _set_txt('a_gt_in_area', a.get('ground_teams'))
        _set_txt('a_obj', a.get('sortie_objectives'))
        _set_txt('a_deliv', a.get('sortie_deliverables'))
        _set_txt('a_actions', a.get('actions_to_be_taken'))
        _set_txt('a_route', a.get('route_of_flight'))
        _set_txt('a_alt', a.get('altitude'))
        _set_txt('a_speed', a.get('airspeed'))
        _set_txt('a_sep', a.get('aircraft_separation'))
        _set_txt('a_emerg', a.get('emergency_fields'))
        _set_txt('a_mlats', a.get('mlat_routes'))
        _set_txt('a_haz', a.get('hazards'))
        _set_txt('a_sp_pattern', sp.get('pattern'))
        _set_txt('a_sp_vis', sp.get('visibility_nm'))
        _set_txt('a_sp_alt', sp.get('altitude_agl'))
        _set_txt('a_sp_speed', sp.get('speed_kts'))
        _set_txt('a_sp_track', sp.get('track_spacing_nm'))
        try:
            def _sel2(cb_key: str, value: Any):
                cb = self._assign_w.get(cb_key)
                if isinstance(cb, QComboBox):
                    txt = str(value or '').strip().lower()
                    for i in range(cb.count()):
                        if cb.itemText(i).strip().lower() == txt:
                            cb.setCurrentIndex(i); return
                    cb.setCurrentIndex(0)
            _sel2('a_sp_terrain', sp.get('terrain'))
            _sel2('a_sp_cover', sp.get('cover'))
            _sel2('a_sp_turb', sp.get('turbulence'))
        except Exception:
            pass
        _set_txt('a_sp_pod', sp.get('pod'))
        _set_txt('a_sp_tts', sp.get('time_to_search'))
        _set_txt('a_sp_ts', sp.get('time_started'))
        _set_txt('a_sp_te', sp.get('time_ended'))
        _set_txt('a_sp_tisa', sp.get('time_in_area'))
        _set_txt('a_sp_tfsa', sp.get('time_from_area'))
        _set_txt('a_sp_total', sp.get('total_sortie_time'))

    def _collect_assignment_data(self) -> Dict[str, Any]:
        def _gtxt(key: str) -> str:
            w = self._assign_w.get(key)
            try:
                if isinstance(w, QTextEdit):
                    return str(w.toPlainText()).strip()
                if isinstance(w, QLineEdit):
                    return str(w.text()).strip()
            except Exception:
                return ""
            return ""
        def _gsel(key: str) -> str:
            w = self._assign_w.get(key)
            if isinstance(w, QComboBox):
                try:
                    return str(w.currentText()).strip()
                except Exception:
                    return ""
            return ""
        ground = {
            'previous_search_efforts': _gtxt('g_prev'),
            'present_search_efforts': _gtxt('g_pres'),
            'time_allocated': _gtxt('g_time'),
            'size_of_assignment': _gtxt('g_size'),
            'expected_pod': {
                'responsive': _gsel('g_pod_resp'),
                'unresponsive': _gsel('g_pod_unresp'),
                'clues': _gsel('g_pod_clues'),
            },
            'drop_off_instructions': _gtxt('g_drop'),
            'pickup_instructions': _gtxt('g_pick'),
        }
        air = {
            'wmirs_aoo': _gtxt('a_aoo'),
            'dep_airport': _gtxt('a_dep'),
            'dest_airport': _gtxt('a_dest'),
            'etd': _gtxt('a_etd'),
            'ete': _gtxt('a_ete'),
            'other_aircraft': _gtxt('a_other_ac'),
            'ground_teams': _gtxt('a_gt_in_area'),
            'sortie_objectives': _gtxt('a_obj'),
            'sortie_deliverables': _gtxt('a_deliv'),
            'actions_to_be_taken': _gtxt('a_actions'),
            'route_of_flight': _gtxt('a_route'),
            'altitude': _gtxt('a_alt'),
            'airspeed': _gtxt('a_speed'),
            'aircraft_separation': _gtxt('a_sep'),
            'emergency_fields': _gtxt('a_emerg'),
            'mlat_routes': _gtxt('a_mlats'),
            'hazards': _gtxt('a_haz'),
            'search_plan': {
                'pattern': _gtxt('a_sp_pattern'),
                'visibility_nm': _gtxt('a_sp_vis'),
                'altitude_agl': _gtxt('a_sp_alt'),
                'speed_kts': _gtxt('a_sp_speed'),
                'track_spacing_nm': _gtxt('a_sp_track'),
                'terrain': _gsel('a_sp_terrain'),
                'cover': _gsel('a_sp_cover'),
                'turbulence': _gsel('a_sp_turb'),
                'pod': _gtxt('a_sp_pod'),
                'time_to_search': _gtxt('a_sp_tts'),
                'time_started': _gtxt('a_sp_ts'),
                'time_ended': _gtxt('a_sp_te'),
                'time_in_area': _gtxt('a_sp_tisa'),
                'time_from_area': _gtxt('a_sp_tfsa'),
                'total_sortie_time': _gtxt('a_sp_total'),
            },
        }
        return { 'ground': ground, 'air': air }


    # --- Debriefing Ops ---
    def _wire_debrief_tab(self) -> None:
        try:
            self._deb_add_btn.clicked.connect(self._open_add_debrief_dialog)
            self._deb_refresh_btn.clicked.connect(self.load_debriefs)
            self._deb_submit_btn.clicked.connect(self._submit_selected_debrief)
            self._deb_mark_rev_btn.clicked.connect(self._mark_selected_debrief_reviewed)
            self._deb_archive_btn.clicked.connect(self._archive_selected_debrief)
            self._deb_delete_btn.clicked.connect(self._delete_selected_debrief)
            # New flow: open editor on double-click
            try:
                self._deb_table.doubleClicked.connect(self._on_debrief_double_clicked)
            except Exception:
                pass
            self._deb_table.selectionModel().selectionChanged.connect(lambda *_: self._on_debrief_selection_changed())
        except Exception:
            pass

    def _debrief_type_labels(self) -> Dict[str, str]:
        return {
            "ground": "Ground (SAR)",
            "area": "Area Search Supplement",
            "tracking": "Tracking Team Supplement",
            "hasty": "Hasty Search Supplement",
            "air_general": "Air (General)",
            "air_sar": "Air (SAR Worksheet)",
        }

    def _debrief_label_to_key(self, label: str) -> str:
        m = {v: k for k, v in self._debrief_type_labels().items()}
        return m.get(label, label)

    def load_debriefs(self) -> None:
        err_msg = ""
        try:
            from modules.operations.taskings.repository import list_task_debriefs
            rows = list_task_debriefs(int(self._task_id)) or []
        except Exception as e:
            rows = []
            try:
                err_msg = str(e)
            except Exception:
                err_msg = ""
        self._deb_model.removeRows(0, self._deb_model.rowCount())
        labels = self._debrief_type_labels()
        for r in rows:
            rid = int(r.get("id") or 0)
            sortie = str(r.get("sortie_number") or "")
            debriefer = str(r.get("debriefer_id") or "")
            types_keys = list(r.get("types") or [])
            types_disp = ", ".join(labels.get(k, k) for k in types_keys)
            status = str(r.get("status") or "Draft")
            flag = "Yes" if (r.get("flagged_for_review") in (True, 1, "1")) else "No"
            updated = _fmt_ts(r.get("updated_at"))
            row = [
                QStandardItem(str(rid)),
                QStandardItem(sortie),
                QStandardItem(debriefer),
                QStandardItem(types_disp),
                QStandardItem(status),
                QStandardItem(flag),
                QStandardItem(updated),
            ]
            row[0].setData(rid, Qt.EditRole)
            self._deb_model.appendRow(row)
        try:
            self._deb_table.setColumnHidden(0, True)
            self._deb_table.sortByColumn(6, Qt.DescendingOrder)
        except Exception:
            pass
        # Update info label with count
        try:
            count = self._deb_model.rowCount()
            if err_msg:
                self._deb_info.setText(f"Task {int(self._task_id)} — Debriefs: {count} (load error: {err_msg})")
            else:
                self._deb_info.setText(f"Task {int(self._task_id)} — Debriefs: {count}")
        except Exception:
            pass

    def _selected_debrief_row(self) -> int:
        try:
            sel = self._deb_table.selectionModel().selectedRows()
            return sel[0].row() if sel else -1
        except Exception:
            return -1

    def _selected_debrief_id(self) -> int | None:
        r = self._selected_debrief_row()
        if r < 0:
            return None
        try:
            return int(self._deb_model.item(r, 0).data(Qt.EditRole) or 0)
        except Exception:
            return None

    def _on_debrief_selection_changed(self) -> None:
        # No auto-open; editor launches on double-click
        try:
            self._deb_editor.setVisible(False)
        except Exception:
            pass

    def _on_debrief_double_clicked(self, index) -> None:
        try:
            row = index.row()
        except Exception:
            row = self._selected_debrief_row()
        if row is None or row < 0:
            return
        try:
            did = int(self._deb_model.item(row, 0).data(Qt.EditRole) or 0)
        except Exception:
            did = 0
        if did > 0:
            self._open_debrief_dialog(did)

    def _open_add_debrief_dialog(self) -> None:
        try:
            from PySide6.QtWidgets import QDialog, QDialogButtonBox
        except Exception:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Debrief")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        sortie_edit = QLineEdit(dlg); sortie_edit.setPlaceholderText("Sortie Number")
        deb_id_edit = QLineEdit(dlg); deb_id_edit.setPlaceholderText("Debriefer ID")
        form.addRow("Sortie Number", sortie_edit)
        form.addRow("Debriefer ID", deb_id_edit)

        # Types checklist with dependencies
        types_box = QWidget(dlg); types_v = QVBoxLayout(types_box); types_v.setContentsMargins(0,0,0,0)
        cb_ground = QCheckBox("Ground (SAR)", types_box)
        cb_area = QCheckBox("Area Search Supplement", types_box)
        cb_tracking = QCheckBox("Tracking Team Supplement", types_box)
        cb_hasty = QCheckBox("Hasty Search Supplement", types_box)
        cb_air_gen = QCheckBox("Air (General)", types_box)
        cb_air_sar = QCheckBox("Air (SAR Worksheet)", types_box)
        # Initial disable of dependent types
        for c in (cb_area, cb_tracking, cb_hasty):
            c.setEnabled(False)
        cb_air_sar.setEnabled(False)
        def _toggle_ground_children():
            enabled = cb_ground.isChecked()
            for c in (cb_area, cb_tracking, cb_hasty):
                c.setEnabled(enabled)
                if not enabled:
                    c.setChecked(False)
        def _toggle_air_children():
            enabled = cb_air_gen.isChecked()
            cb_air_sar.setEnabled(enabled)
            if not enabled:
                cb_air_sar.setChecked(False)
        cb_ground.toggled.connect(_toggle_ground_children)
        cb_air_gen.toggled.connect(_toggle_air_children)
        for w in (cb_ground, cb_area, cb_tracking, cb_hasty, cb_air_gen, cb_air_sar):
            types_v.addWidget(w)
        form.addRow("Debrief Types", types_box)
        lay.addLayout(form)
        # Custom buttons so dialog only closes on successful create
        btn_row = QHBoxLayout()
        btn_create = QPushButton("Create", dlg)
        try:
            btn_create.setDefault(True)
            btn_create.setAutoDefault(True)
        except Exception:
            pass
        btn_cancel = QPushButton("Cancel", dlg)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_create)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        def _create():
            # Sortie number is optional per request
            sortie = sortie_edit.text().strip()
            debid = deb_id_edit.text().strip()
            sel_types: List[str] = []
            if cb_ground.isChecked(): sel_types.append("ground")
            if cb_area.isChecked(): sel_types.append("area")
            if cb_tracking.isChecked(): sel_types.append("tracking")
            if cb_hasty.isChecked(): sel_types.append("hasty")
            if cb_air_gen.isChecked(): sel_types.append("air_general")
            if cb_air_sar.isChecked(): sel_types.append("air_sar")
            if not sel_types:
                try:
                    QMessageBox.warning(dlg, "Add Debrief", "Select at least one debrief type.")
                except Exception:
                    pass
                return
            try:
                from modules.operations.taskings.repository import create_debrief
                new_id = create_debrief(int(self._task_id), sortie, debid, sel_types)
            except Exception as e:
                try:
                    QMessageBox.warning(dlg, "Add Debrief", f"Could not create debrief: {e}")
                except Exception:
                    pass
                return
            # Success: close and refresh/select
            try:
                dlg.accept()
            except Exception:
                pass
            self.load_debriefs()
            try:
                QMessageBox.information(self, "Debrief", f"Debrief created (ID {new_id}).")
            except Exception:
                pass
            # Select newly created debrief and open editor
            try:
                target_row = -1
                for r in range(self._deb_model.rowCount()):
                    rid = int(self._deb_model.item(r, 0).data(Qt.EditRole) or 0)
                    if rid == int(new_id):
                        target_row = r
                        break
                if target_row < 0:
                    # Fallback: fetch created debrief and append if list is out-of-sync
                    try:
                        from modules.operations.taskings.repository import get_debrief
                        drow = get_debrief(int(new_id)) or {}
                        labels = self._debrief_type_labels()
                        types_disp = ", ".join(labels.get(k, k) for k in list(drow.get("types") or []))
                        items = [
                            QStandardItem(str(int(new_id))),
                            QStandardItem(str(drow.get("sortie_number") or "")),
                            QStandardItem(str(drow.get("debriefer_id") or "")),
                            QStandardItem(types_disp),
                            QStandardItem(str(drow.get("status") or "Draft")),
                            QStandardItem("Yes" if (drow.get("flagged_for_review") in (True, 1, "1")) else "No"),
                            QStandardItem(_fmt_ts(drow.get("updated_at"))),
                        ]
                        items[0].setData(int(new_id), Qt.EditRole)
                        self._deb_model.appendRow(items)
                        target_row = self._deb_model.rowCount() - 1
                    except Exception:
                        pass
                if target_row >= 0:
                    idx = self._deb_model.index(target_row, 1)
                    self._deb_table.setCurrentIndex(idx)
                    try:
                        self._deb_table.scrollTo(idx)
                    except Exception:
                        pass
                # Do not auto-open editor; user can double-click the row
            except Exception:
                pass

        try:
            btn_create.clicked.connect(_create)
            btn_cancel.clicked.connect(dlg.reject)
        except Exception:
            pass
        try:
            dlg.exec()
        except Exception:
            pass

    def _open_debrief_dialog(self, debrief_id: int) -> None:
        try:
            from modules.operations.taskings.repository import get_debrief, update_debrief_header
        except Exception:
            return
        d: Dict[str, Any] = {}
        try:
            d = get_debrief(int(debrief_id)) or {}
        except Exception:
            d = {}
        # Modal container
        try:
            from PySide6.QtWidgets import QDialog, QDialogButtonBox
        except Exception:
            return
        dlg = QDialog(self)
        try:
            dlg.setWindowTitle(f"Debrief Editor — ID {debrief_id}")
            dlg.resize(900, 700)
        except Exception:
            pass
        dlgl = QVBoxLayout(dlg)
        # Header box
        head_box = QWidget(dlg); head_form = QFormLayout(head_box)
        try:
            head_form.setContentsMargins(0,0,0,0)
            head_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        except Exception:
            pass

    def _teams_dev_delete(self) -> None:
        """Dev-only: Permanently delete the selected team record and its assignments."""
        try:
            r = self._selected_team_row()
            if r < 0:
                return
            from modules.operations.taskings.repository import list_task_teams
            rows = list_task_teams(int(self._task_id)) or []
            # Extract team_id and name for confirmation
            team_id = None
            team_name = ""
            try:
                team_id = int(rows[r].team_id)
                team_name = str(rows[r].team_name or "")
            except Exception:
                try:
                    v = (_to_variant(rows[r]) or {})
                    team_id = int(v.get('team_id')) if v.get('team_id') is not None else None
                    team_name = str(v.get('team_name') or "")
                except Exception:
                    team_id = None
            if team_id is None:
                return
            from PySide6.QtWidgets import QMessageBox
            resp = QMessageBox.warning(
                self,
                "Confirm Delete Team",
                f"This will permanently delete team ID {team_id} ({team_name}) and remove all its task assignments.\nThis action cannot be undone.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            from modules.operations.taskings.repository import delete_team
            delete_team(int(team_id))
            # Refresh lists
            self.load_teams()
        except Exception:
            pass
        sortie_edit = QLineEdit(head_box); sortie_edit.setText(str(d.get("sortie_number") or ""))
        deb_edit = QLineEdit(head_box); deb_edit.setText(str(d.get("debriefer_id") or ""))
        status_lbl = QLabel(str(d.get("status") or "Draft"), head_box)
        flag_cb = QCheckBox("Flag for Planning Review", head_box); flag_cb.setChecked(bool(d.get("flagged_for_review") or False))
        types_disp = ", ".join(self._debrief_type_labels().get(k, k) for k in list(d.get("types") or []))
        types_lbl = QLabel(types_disp, head_box)
        head_form.addRow("Sortie Number", sortie_edit)
        head_form.addRow("Debriefer ID", deb_edit)
        head_form.addRow("Types", types_lbl)
        head_form.addRow("Status", status_lbl)
        head_form.addRow("Flag", flag_cb)
        head_btn_row = QHBoxLayout()
        head_save = QPushButton("Save Header", head_box)
        def _save_header():
            patch = {
                "sortie_number": sortie_edit.text().strip(),
                "debriefer_id": deb_edit.text().strip(),
                "flagged_for_review": 1 if flag_cb.isChecked() else 0,
            }
            try:
                update_debrief_header(int(debrief_id), patch)
                self.load_debriefs()
            except Exception as e:
                try:
                    QMessageBox.warning(self, "Debrief", f"Could not save header: {e}")
                except Exception:
                    pass
        head_save.clicked.connect(_save_header)
        head_btn_row.addStretch(1); head_btn_row.addWidget(head_save)
        head_wrap = QVBoxLayout(); head_wrap.addWidget(head_box); head_wrap.addLayout(head_btn_row)
        head_container = QWidget(dlg); head_container.setLayout(head_wrap)
        dlgl.addWidget(head_container)

        # Forms tabs
        forms_tabs = QTabWidget(dlg)

        # Helpers
        def _time_edit(parent: QWidget) -> QLineEdit:
            e = QLineEdit(parent)
            try:
                re = QRegularExpression(r"^(?:[01]?[0-9]|2[0-3]):[0-5][0-9]$")
                e.setValidator(QRegularExpressionValidator(re, e))
                e.setPlaceholderText("HH:MM")
            except Exception:
                pass
            return e

        def _combo(parent: QWidget, items: List[str]) -> QComboBox:
            cb = QComboBox(parent); cb.addItems(list(items))
            return cb

        def _populate(widgets: Dict[str, QWidget], data: Dict[str, Any]):
            self._populate_form_widgets(widgets, data)

        def _gather(widgets: Dict[str, QWidget]) -> Dict[str, Any]:
            return self._gather_form_widgets(widgets)

        def _add_form_tab(title: str, key: str, build_fn):
            w = QWidget(forms_tabs)
            lay = QFormLayout()
            try:
                w.setLayout(lay)
            except Exception:
                pass
            try:
                lay.setLabelAlignment(Qt.AlignLeft)
                lay.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            except Exception:
                pass
            widgets: Dict[str, QWidget] = {}
            build_fn(w, lay, widgets)
            data = ((d.get("forms") or {}).get(key)) or {}
            _populate(widgets, data)
            btn_row = QHBoxLayout()
            save_btn = QPushButton("Save", w)
            def _save_this_form():
                try:
                    from modules.operations.taskings.repository import save_debrief_form, update_debrief_header
                    data_local = _gather(widgets)
                    save_debrief_form(int(debrief_id), str(key), dict(data_local))
                    update_debrief_header(int(debrief_id), {"flagged_for_review": 1})
                    self.load_debriefs()
                    try:
                        QMessageBox.information(self, "Debrief", "Saved.")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        QMessageBox.warning(self, "Debrief", f"Could not save: {e}")
                    except Exception:
                        pass
            save_btn.clicked.connect(_save_this_form)
            btn_row.addStretch(1); btn_row.addWidget(save_btn)
            wrap = QVBoxLayout(); wrap.addWidget(w); wrap.addLayout(btn_row)
            cont = QWidget(forms_tabs); cont.setLayout(wrap)
            from PySide6.QtWidgets import QScrollArea
            scr = QScrollArea(forms_tabs)
            try:
                scr.setWidgetResizable(True)
            except Exception:
                pass
            scr.setWidget(cont)
            forms_tabs.addTab(scr, title)

        # --- Form builders ---
        def _build_ground(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            def _t(key, label):
                te = QTextEdit(parent); te.setPlaceholderText(label)
                te.setFixedHeight(60)
                widgets[key] = te; lay.addRow(label, te)
            _t("assignment_summary", "Assignment Summary")
            _t("efforts", "Describe Search Efforts in Assignment")
            _t("unable", "Describe Portions Unable to Search")
            _t("clues", "Describe Clues/Tracks/Signs or any Interviews")
            _t("hazards", "Describe any Hazards or Problems Encountered")
            _t("suggestions", "Suggestions for Further Search Efforts In or Near Assignment")
            te_in = _time_edit(parent); widgets["time_entered"] = te_in; lay.addRow("Time Entered", te_in)
            te_out = _time_edit(parent); widgets["time_exited"] = te_out; lay.addRow("Time Exited", te_out)
            ts = QLineEdit(parent); ts.setReadOnly(True); widgets["time_spent"] = ts; lay.addRow("Time Spent (hh:mm)", ts)
            def _recalc():
                try:
                    t1 = te_in.text().strip()
                    t2 = te_out.text().strip()
                    if ":" in t1 and ":" in t2:
                        h1, m1 = [int(x) for x in t1.split(":", 1)]
                        h2, m2 = [int(x) for x in t2.split(":", 1)]
                        mins = (h2*60+m2) - (h1*60+m1)
                        if mins < 0:
                            mins += 24*60
                        widgets["time_spent"].setText(f"{mins//60:02d}:{mins%60:02d}")
                except Exception:
                    pass
            try:
                te_in.textChanged.connect(_recalc)
                te_out.textChanged.connect(_recalc)
            except Exception:
                pass
            lay.addRow(QLabel("Conditions"))
            widgets["clouds"] = _combo(parent, ["", "Clear", "Scattered", "Broken", "Overcast"]); lay.addRow("Clouds", widgets["clouds"])
            widgets["precipitation"] = _combo(parent, ["", "None", "Rain", "Scattered", "Snow"]); lay.addRow("Precipitation", widgets["precipitation"])
            widgets["light"] = _combo(parent, ["", "Bright", "Dull", "Near Dark", "Night"]); lay.addRow("Light Conditions", widgets["light"])
            widgets["visibility"] = _combo(parent, ["", "> 10 Miles", "> 5 Miles", "> 1 Mile", "< 1 Mile"]); lay.addRow("Visibility", widgets["visibility"])
            widgets["terrain"] = _combo(parent, ["", "Flat", "Rolling Hills", "Rugged Hills", "Mtns"]); lay.addRow("Terrain", widgets["terrain"])
            widgets["ground_cover"] = _combo(parent, ["", "Open", "Moderate", "Heavy", "Other"]); lay.addRow("Ground Cover", widgets["ground_cover"])
            widgets["wind_speed"] = _combo(parent, ["", "Calm", "< 10 mph", "< 20 mph", "< 30 mph"]); lay.addRow("Wind Speed", widgets["wind_speed"])
            lay.addRow(QLabel("Attachments"))
            for key, lab in [("map","Debriefing Maps"),("brief","Original Briefing Document"),("supp","Supplemental Debriefing Forms"),("interviews","Interview Log"),("other","Other")]:
                cb = QCheckBox(lab, parent); widgets[f"att_{key}"] = cb; lay.addRow("", cb)

        def _build_area(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            for key, lab in [("num_searchers","Number of Searchers"),("time_spent","Time Spent Searching"),("search_speed","Search Speed"),("area_size","Area Size (Actually Searched)"),("spacing","Spacing"),("visibility_distance","Visibility Distance"),("visibility_how","How was Visibility Distance Determined"),("skipped_types","Types of Areas Skipped Over"),("direction_pattern","Describe the Direction and Pattern of your Search"),("comments","Comments for Additional Area Searching of this Assignment")]:
                if key in ("comments","direction_pattern","visibility_distance","visibility_how","skipped_types"):
                    w = QTextEdit(parent); w.setFixedHeight(60)
                else:
                    w = QLineEdit(parent)
                w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)

        def _build_tracking(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            for key, lab in [("likelihood_tracks","Discuss Likelihood of Finding Tracks or Sign on the Trails"),("existing_traps","Describe the Location and Nature of Existing Track Traps"),("erase_traps","Did You Erase Any Track Traps"),("new_traps","Did You Create Any New Track Traps"),("route_tracks","Describe the Route Taken by Any Tracks You Followed"),("why_discontinue","Why Did You Discontinue Following These Tracks")]:
                w = QTextEdit(parent); w.setFixedHeight(60); w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)
            lay.addRow(QLabel("Attachments"))
            widgets["att_individual_sketches"] = QCheckBox("Individual Track Sketches Attached", parent); lay.addRow("", widgets["att_individual_sketches"])
            widgets["att_trap_summary"] = QCheckBox("Track Trap Summary Sketches Attached", parent); lay.addRow("", widgets["att_trap_summary"])

        def _build_hasty(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            for key, lab in [("visibility","Visibility During Search (Day/Dusk/Night/Other)"),("attract","Describe Your Efforts to Attract a Responsive Subject"),("hear","Describe Ability to Hear a Response (Background Noise)"),("trail_cond","Describe the Trail Conditions"),("offtrail_cond","Describe the Off-Trail Conditions"),("map_accuracy","Does the Map Accurately Reflect the Trails"),("features","Did You Locate Features That Would Likely Contain the Subject"),("tracking_cond","How Are the Tracking Conditions"),("hazards_attract","Describe any Hazards or Attractions You Found")]:
                w = QTextEdit(parent); w.setFixedHeight(60); w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)

        def _build_air_general(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            def _add(key, lab):
                w = QTextEdit(parent) if key in ("summary","results","weather","remarks") else QLineEdit(parent)
                if isinstance(w, QTextEdit): w.setFixedHeight(60)
                w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)
            for k, l in [("flight_plan_closed","Flight Plan Closed (Yes/No)"),("atd","ATD"),("ata","ATA"),("hobbs_start","Hobbs Start"),("hobbs_end","Hobbs End"),("hobbs_to_from","Hobbs To/From"),("hobbs_in_area","Hobbs in Area"),("hobbs_total","Hobbs Total"),("tach_start","Tach Start"),("tach_end","Tach End"),("fuel_used_gal","Fuel Used (Gal)"),("oil_used_qt","Oil Used (Qt)"),("fuel_oil_cost","Fuel & Oil Cost"),("receipt_no","Receipt #"),("summary","Summary"),("results","Results/Deliverables"),("weather","Weather Conditions"),("remarks","Remarks")]:
                _add(k, l)
            widgets["sortie_effectiveness"] = _combo(parent, ["", "Successful", "Marginal", "Unsuccessful", "Not Flown", "Not Required"]); lay.addRow("Sortie Effectiveness", widgets["sortie_effectiveness"])
            widgets["reason_not_success"] = _combo(parent, ["", "Weather", "Crew Unavailable", "Aircraft Maintenance", "Customer Cancellation", "Equipment Failure", "Other"]); lay.addRow("Reason (if not successful)", widgets["reason_not_success"])
            lay.addRow(QLabel("Attachments/Documentation"))
            for key, lab in [("capf104a","CAPF 104A SAR"),("capf104b","CAPF 104B Recon Summary"),("ics214","ICS 214 Unit Log"),("receipts","Receipts"),("aif_orm","AIF ORM Matrix")]:
                cb = QCheckBox(lab, parent); widgets[f"att_{key}"] = cb; lay.addRow("", cb)

        def _build_air_sar(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            lay.addRow(QLabel("Search Area"))
            for key, lab in [("name","Name"),("grid","Grid"),("nw","NW Corner (Lat/Long)"),("ne","NE Corner (Lat/Long)"),("sw","SW Corner (Lat/Long)"),("se","SE Corner (Lat/Long)")]:
                widgets[f"area_{key}"] = QLineEdit(parent); widgets[f"area_{key}"].setPlaceholderText(lab); lay.addRow(lab, widgets[f"area_{key}"])
            lay.addRow(QLabel("Sortie Search Actual"))
            for key, lab in [("pattern","Search Pattern"),("visibility_nm","Search Visibility (NM)"),("altitude_agl","Search Altitude (AGL)"),("speed_kts","Search Speed (Knots)"),("track_spacing_nm","Track Spacing (NM)")]:
                widgets[f"act_{key}"] = QLineEdit(parent); widgets[f"act_{key}"].setPlaceholderText(lab); lay.addRow(lab, widgets[f"act_{key}"])
            widgets["act_terrain"] = _combo(parent, ["", "Flat", "Rolling Hills", "Rugged Hills", "Mountainous"]); lay.addRow("Terrain", widgets["act_terrain"])
            widgets["act_cover"] = _combo(parent, ["", "Open", "Moderate", "Heavy", "Light Snow", "Heavy Snow"]); lay.addRow("Cover", widgets["act_cover"])
            widgets["act_turbulence"] = _combo(parent, ["", "Light", "Moderate", "Heavy"]); lay.addRow("Turbulence", widgets["act_turbulence"])
            for key, lab in [("pod","Probability of Detection"),("time_to_search","Time to Search Area"),("time_started","Time Started Search"),("time_ended","Time Ended Search"),("time_in_area","Time in Search Area"),("time_from_area","Time from Search Area"),("total_sortie_time","Total Sortie Time")]:
                widgets[f"act_{key}"] = QLineEdit(parent); widgets[f"act_{key}"].setPlaceholderText(lab); lay.addRow(lab, widgets[f"act_{key}"])
            lay.addRow(QLabel("Crew Remarks and Notes"))
            widgets["remarks_effectiveness"] = _combo(parent, ["", "Excellent", "Good", "Fair", "Poor"]); lay.addRow("Effectiveness", widgets["remarks_effectiveness"])
            widgets["remarks_visibility"] = _combo(parent, ["", "Excellent", "Good", "Fair", "Poor"]); lay.addRow("Visibility", widgets["remarks_visibility"])

        # Build tabs from selected types
        types_keys = list(d.get("types") or [])
        labels = self._debrief_type_labels()
        for key in types_keys:
            title = labels.get(key, key)
            if key == "ground": _add_form_tab(title, key, _build_ground)
            elif key == "area": _add_form_tab(title, key, _build_area)
            elif key == "tracking": _add_form_tab(title, key, _build_tracking)
            elif key == "hasty": _add_form_tab(title, key, _build_hasty)
            elif key == "air_general": _add_form_tab(title, key, _build_air_general)
            elif key == "air_sar": _add_form_tab(title, key, _build_air_sar)

        dlgl.addWidget(forms_tabs, 1)
        footer = QDialogButtonBox(QDialogButtonBox.Close, parent=dlg)
        try:
            footer.rejected.connect(dlg.reject)
            footer.accepted.connect(dlg.accept)
        except Exception:
            pass
        dlgl.addWidget(footer)
        try:
            dlg.exec()
        except Exception:
            pass

    def _open_debrief_editor(self, debrief_id: int) -> None:
        try:
            from modules.operations.taskings.repository import get_debrief, update_debrief_header
        except Exception:
            return
        d = {}
        try:
            d = get_debrief(int(debrief_id)) or {}
        except Exception:
            d = {}
        self._deb_editor.setVisible(True)
        # Clear old editor
        while True:
            item = self._deb_editor_v.takeAt(0)
            if not item:
                break
            w = item.widget()
            if w is not None:
                try:
                    w.deleteLater()
                except Exception:
                    pass
        # Header
        head_box = QWidget(self._deb_editor); head_form = QFormLayout(head_box)
        try:
            head_form.setContentsMargins(0,0,0,0)
        except Exception:
            pass
        sortie_edit = QLineEdit(head_box); sortie_edit.setText(str(d.get("sortie_number") or ""))
        deb_edit = QLineEdit(head_box); deb_edit.setText(str(d.get("debriefer_id") or ""))
        status_lbl = QLabel(str(d.get("status") or "Draft"), head_box)
        flag_cb = QCheckBox("Flag for Planning Review", head_box); flag_cb.setChecked(bool(d.get("flagged_for_review") or False))
        types_disp = ", ".join(self._debrief_type_labels().get(k, k) for k in list(d.get("types") or []))
        types_lbl = QLabel(types_disp, head_box)
        head_form.addRow("Sortie Number", sortie_edit)
        head_form.addRow("Debriefer ID", deb_edit)
        head_form.addRow("Types", types_lbl)
        head_form.addRow("Status", status_lbl)
        head_form.addRow("Flag", flag_cb)
        head_btn_row = QHBoxLayout()
        head_save = QPushButton("Save Header", head_box)
        def _save_header():
            patch = {
                "sortie_number": sortie_edit.text().strip(),
                "debriefer_id": deb_edit.text().strip(),
                "flagged_for_review": 1 if flag_cb.isChecked() else 0,
            }
            try:
                update_debrief_header(int(debrief_id), patch)
                self.load_debriefs()
            except Exception as e:
                try:
                    QMessageBox.warning(self, "Debrief", f"Could not save header: {e}")
                except Exception:
                    pass
        head_save.clicked.connect(_save_header)
        head_btn_row.addStretch(1); head_btn_row.addWidget(head_save)
        head_wrap = QVBoxLayout(); head_wrap.addWidget(head_box); head_wrap.addLayout(head_btn_row)
        head_container = QWidget(self._deb_editor); head_container.setLayout(head_wrap)
        self._deb_editor_v.addWidget(head_container)

        # Forms tabs
        forms_tabs = QTabWidget(self._deb_editor)
        self._deb_form_widgets: Dict[str, Dict[str, QWidget]] = {}

        # --- Form builders ---
        def _add_form_tab(title: str, key: str, build_fn):
            w = QWidget(forms_tabs)
            lay = QFormLayout()
            try:
                w.setLayout(lay)
            except Exception:
                pass
            try:
                lay.setLabelAlignment(Qt.AlignLeft)
            except Exception:
                pass
            widgets: Dict[str, QWidget] = {}
            build_fn(w, lay, widgets)
            self._deb_form_widgets[key] = widgets
            # Populate from stored data
            data = ((d.get("forms") or {}).get(key)) or {}
            self._populate_form_widgets(widgets, data)
            # Save button per form
            btn_row = QHBoxLayout()
            save_btn = QPushButton("Save", w)
            save_btn.clicked.connect(lambda _=None, k=key: self._save_debrief_form(int(debrief_id), k))
            btn_row.addStretch(1); btn_row.addWidget(save_btn)
            wrap = QVBoxLayout(); wrap.addWidget(w); wrap.addLayout(btn_row)
            cont = QWidget(forms_tabs); cont.setLayout(wrap)
            forms_tabs.addTab(cont, title)

        # Helpers
        def _time_edit(parent: QWidget) -> QLineEdit:
            e = QLineEdit(parent)
            try:
                re = QRegularExpression(r"^(?:[01]?[0-9]|2[0-3]):[0-5][0-9]$")
                e.setValidator(QRegularExpressionValidator(re, e))
                e.setPlaceholderText("HH:MM")
            except Exception:
                pass
            return e

        def _combo(parent: QWidget, items: List[str]) -> QComboBox:
            cb = QComboBox(parent); cb.addItems(list(items))
            return cb

        # Ground (SAR)
        def _build_ground(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            def _t(key, label):
                te = QTextEdit(parent); te.setPlaceholderText(label)
                te.setFixedHeight(60)
                widgets[key] = te; lay.addRow(label, te)
            _t("assignment_summary", "Assignment Summary")
            _t("efforts", "Describe Search Efforts in Assignment")
            _t("unable", "Describe Portions Unable to Search")
            _t("clues", "Describe Clues/Tracks/Signs or any Interviews")
            _t("hazards", "Describe any Hazards or Problems Encountered")
            _t("suggestions", "Suggestions for Further Search Efforts In or Near Assignment")
            te_in = _time_edit(parent); widgets["time_entered"] = te_in; lay.addRow("Time Entered", te_in)
            te_out = _time_edit(parent); widgets["time_exited"] = te_out; lay.addRow("Time Exited", te_out)
            ts = QLineEdit(parent); ts.setReadOnly(True); widgets["time_spent"] = ts; lay.addRow("Time Spent (hh:mm)", ts)
            def _recalc():
                try:
                    t1 = te_in.text().strip()
                    t2 = te_out.text().strip()
                    if ":" in t1 and ":" in t2:
                        h1, m1 = [int(x) for x in t1.split(":", 1)]
                        h2, m2 = [int(x) for x in t2.split(":", 1)]
                        mins = (h2*60+m2) - (h1*60+m1)
                        if mins < 0:
                            mins += 24*60
                        widgets["time_spent"].setText(f"{mins//60:02d}:{mins%60:02d}")
                except Exception:
                    pass
            try:
                te_in.textChanged.connect(_recalc)
                te_out.textChanged.connect(_recalc)
            except Exception:
                pass
            # Conditions
            lay.addRow(QLabel("Conditions"))
            widgets["clouds"] = _combo(parent, ["", "Clear", "Scattered", "Broken", "Overcast"]); lay.addRow("Clouds", widgets["clouds"])
            widgets["precipitation"] = _combo(parent, ["", "None", "Rain", "Scattered", "Snow"]); lay.addRow("Precipitation", widgets["precipitation"])
            widgets["light"] = _combo(parent, ["", "Bright", "Dull", "Near Dark", "Night"]); lay.addRow("Light Conditions", widgets["light"])
            widgets["visibility"] = _combo(parent, ["", "> 10 Miles", "> 5 Miles", "> 1 Mile", "< 1 Mile"]); lay.addRow("Visibility", widgets["visibility"])
            widgets["terrain"] = _combo(parent, ["", "Flat", "Rolling Hills", "Rugged Hills", "Mtns"]); lay.addRow("Terrain", widgets["terrain"])
            widgets["ground_cover"] = _combo(parent, ["", "Open", "Moderate", "Heavy", "Other"]); lay.addRow("Ground Cover", widgets["ground_cover"])
            widgets["wind_speed"] = _combo(parent, ["", "Calm", "< 10 mph", "< 20 mph", "< 30 mph"]); lay.addRow("Wind Speed", widgets["wind_speed"])
            # Attachments (booleans)
            lay.addRow(QLabel("Attachments"))
            for key, lab in [
                ("map", "Debriefing Maps"),
                ("brief", "Original Briefing Document"),
                ("supp", "Supplemental Debriefing Forms"),
                ("interviews", "Interview Log"),
                ("other", "Other"),
            ]:
                cb = QCheckBox(lab, parent); widgets[f"att_{key}"] = cb; lay.addRow("", cb)

        # Area Search Supplement
        def _build_area(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            for key, lab in [
                ("num_searchers", "Number of Searchers"),
                ("time_spent", "Time Spent Searching"),
                ("search_speed", "Search Speed"),
                ("area_size", "Area Size (Actually Searched)"),
                ("spacing", "Spacing"),
                ("visibility_distance", "Visibility Distance"),
                ("visibility_how", "How was Visibility Distance Determined"),
                ("skipped_types", "Types of Areas Skipped Over"),
                ("direction_pattern", "Describe the Direction and Pattern of your Search"),
                ("comments", "Comments for Additional Area Searching of this Assignment"),
            ]:
                if key in ("comments", "direction_pattern", "visibility_distance", "visibility_how", "skipped_types"):
                    w = QTextEdit(parent); w.setFixedHeight(60)
                else:
                    w = QLineEdit(parent)
                w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)

        # Tracking Team Supplement
        def _build_tracking(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            for key, lab in [
                ("likelihood_tracks", "Discuss Likelihood of Finding Tracks or Sign on the Trails"),
                ("existing_traps", "Describe the Location and Nature of Existing Track Traps"),
                ("erase_traps", "Did You Erase Any Track Traps"),
                ("new_traps", "Did You Create Any New Track Traps"),
                ("route_tracks", "Describe the Route Taken by Any Tracks You Followed"),
                ("why_discontinue", "Why Did You Discontinue Following These Tracks"),
            ]:
                w = QTextEdit(parent); w.setFixedHeight(60)
                w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)
            # Attachments booleans
            lay.addRow(QLabel("Attachments"))
            widgets["att_individual_sketches"] = QCheckBox("Individual Track Sketches Attached", parent); lay.addRow("", widgets["att_individual_sketches"])
            widgets["att_trap_summary"] = QCheckBox("Track Trap Summary Sketches Attached", parent); lay.addRow("", widgets["att_trap_summary"])

        # Hasty Search Supplement
        def _build_hasty(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            for key, lab in [
                ("visibility", "Visibility During Search (Day/Dusk/Night/Other)"),
                ("attract", "Describe Your Efforts to Attract a Responsive Subject"),
                ("hear", "Describe Ability to Hear a Response (Background Noise)"),
                ("trail_cond", "Describe the Trail Conditions"),
                ("offtrail_cond", "Describe the Off-Trail Conditions"),
                ("map_accuracy", "Does the Map Accurately Reflect the Trails"),
                ("features", "Did You Locate Features That Would Likely Contain the Subject"),
                ("tracking_cond", "How Are the Tracking Conditions"),
                ("hazards_attract", "Describe any Hazards or Attractions You Found"),
            ]:
                w = QTextEdit(parent); w.setFixedHeight(60)
                w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)

        # Air (General)
        def _build_air_general(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            def _add(key, lab):
                w = QTextEdit(parent) if key in ("summary", "results", "weather", "remarks") else QLineEdit(parent)
                if isinstance(w, QTextEdit):
                    w.setFixedHeight(60)
                w.setPlaceholderText(lab)
                widgets[key] = w; lay.addRow(lab, w)
            for k, l in [
                ("flight_plan_closed", "Flight Plan Closed (Yes/No)"),
                ("atd", "ATD"), ("ata", "ATA"),
                ("hobbs_start", "Hobbs Start"), ("hobbs_end", "Hobbs End"), ("hobbs_to_from", "Hobbs To/From"), ("hobbs_in_area", "Hobbs in Area"), ("hobbs_total", "Hobbs Total"),
                ("tach_start", "Tach Start"), ("tach_end", "Tach End"),
                ("fuel_used_gal", "Fuel Used (Gal)"), ("oil_used_qt", "Oil Used (Qt)"), ("fuel_oil_cost", "Fuel & Oil Cost"), ("receipt_no", "Receipt #"),
                ("summary", "Summary"), ("results", "Results/Deliverables"), ("weather", "Weather Conditions"), ("remarks", "Remarks"),
            ]:
                _add(k, l)
            widgets["sortie_effectiveness"] = _combo(parent, ["", "Successful", "Marginal", "Unsuccessful", "Not Flown", "Not Required"]); lay.addRow("Sortie Effectiveness", widgets["sortie_effectiveness"])
            widgets["reason_not_success"] = _combo(parent, ["", "Weather", "Crew Unavailable", "Aircraft Maintenance", "Customer Cancellation", "Equipment Failure", "Other"]); lay.addRow("Reason (if not successful)", widgets["reason_not_success"])
            lay.addRow(QLabel("Attachments/Documentation"))
            for key, lab in [
                ("capf104a", "CAPF 104A SAR"),
                ("capf104b", "CAPF 104B Recon Summary"),
                ("ics214", "ICS 214 Unit Log"),
                ("receipts", "Receipts"),
                ("aif_orm", "AIF ORM Matrix"),
            ]:
                cb = QCheckBox(lab, parent); widgets[f"att_{key}"] = cb; lay.addRow("", cb)

        # Air (SAR Worksheet)
        def _build_air_sar(parent: QWidget, lay: QFormLayout, widgets: Dict[str, QWidget]):
            lay.addRow(QLabel("Search Area"))
            for key, lab in [
                ("name", "Name"), ("grid", "Grid"),
                ("nw", "NW Corner (Lat/Long)"), ("ne", "NE Corner (Lat/Long)"),
                ("sw", "SW Corner (Lat/Long)"), ("se", "SE Corner (Lat/Long)"),
            ]:
                widgets[f"area_{key}"] = QLineEdit(parent); widgets[f"area_{key}"].setPlaceholderText(lab); lay.addRow(lab, widgets[f"area_{key}"])
            lay.addRow(QLabel("Sortie Search Actual"))
            for key, lab in [
                ("pattern", "Search Pattern"), ("visibility_nm", "Search Visibility (NM)"), ("altitude_agl", "Search Altitude (AGL)"), ("speed_kts", "Search Speed (Knots)"), ("track_spacing_nm", "Track Spacing (NM)"),
            ]:
                widgets[f"act_{key}"] = QLineEdit(parent); widgets[f"act_{key}"].setPlaceholderText(lab); lay.addRow(lab, widgets[f"act_{key}"])
            widgets["act_terrain"] = _combo(parent, ["", "Flat", "Rolling Hills", "Rugged Hills", "Mountainous"]); lay.addRow("Terrain", widgets["act_terrain"])
            widgets["act_cover"] = _combo(parent, ["", "Open", "Moderate", "Heavy", "Light Snow", "Heavy Snow"]); lay.addRow("Cover", widgets["act_cover"])
            widgets["act_turbulence"] = _combo(parent, ["", "Light", "Moderate", "Heavy"]); lay.addRow("Turbulence", widgets["act_turbulence"])
            for key, lab in [
                ("pod", "Probability of Detection"),
                ("time_to_search", "Time to Search Area"), ("time_started", "Time Started Search"), ("time_ended", "Time Ended Search"), ("time_in_area", "Time in Search Area"), ("time_from_area", "Time from Search Area"), ("total_sortie_time", "Total Sortie Time"),
            ]:
                widgets[f"act_{key}"] = QLineEdit(parent); widgets[f"act_{key}"].setPlaceholderText(lab); lay.addRow(lab, widgets[f"act_{key}"])
            lay.addRow(QLabel("Crew Remarks and Notes"))
            widgets["remarks_effectiveness"] = _combo(parent, ["", "Excellent", "Good", "Fair", "Poor"]); lay.addRow("Effectiveness", widgets["remarks_effectiveness"])
            widgets["remarks_visibility"] = _combo(parent, ["", "Excellent", "Good", "Fair", "Poor"]); lay.addRow("Visibility", widgets["remarks_visibility"])

        # Build tabs according to selected types
        types_keys = list(d.get("types") or [])
        labels = self._debrief_type_labels()
        for key in types_keys:
            title = labels.get(key, key)
            if key == "ground":
                _add_form_tab(title, key, _build_ground)
            elif key == "area":
                _add_form_tab(title, key, _build_area)
            elif key == "tracking":
                _add_form_tab(title, key, _build_tracking)
            elif key == "hasty":
                _add_form_tab(title, key, _build_hasty)
            elif key == "air_general":
                _add_form_tab(title, key, _build_air_general)
            elif key == "air_sar":
                _add_form_tab(title, key, _build_air_sar)

        self._deb_editor_v.addWidget(forms_tabs)

    def _populate_form_widgets(self, widgets: Dict[str, QWidget], data: Dict[str, Any]) -> None:
        for k, w in widgets.items():
            try:
                v = data.get(k)
            except Exception:
                v = None
            try:
                if isinstance(w, QLineEdit):
                    w.setText("") if v is None else w.setText(str(v))
                elif isinstance(w, QTextEdit):
                    w.setPlainText("") if v is None else w.setPlainText(str(v))
                elif isinstance(w, QComboBox):
                    if v is None:
                        w.setCurrentIndex(0)
                    else:
                        idx = w.findText(str(v))
                        w.setCurrentIndex(idx if idx >= 0 else 0)
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(v))
            except Exception:
                pass

    def _gather_form_widgets(self, widgets: Dict[str, QWidget]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, w in widgets.items():
            try:
                if isinstance(w, QLineEdit):
                    out[k] = w.text().strip()
                elif isinstance(w, QTextEdit):
                    out[k] = w.toPlainText().strip()
                elif isinstance(w, QComboBox):
                    out[k] = w.currentText()
                elif isinstance(w, QCheckBox):
                    out[k] = 1 if w.isChecked() else 0
            except Exception:
                pass
        return out

    def _save_debrief_form(self, debrief_id: int, form_key: str) -> None:
        try:
            from modules.operations.taskings.repository import save_debrief_form, update_debrief_header
        except Exception:
            return
        widgets = (self._deb_form_widgets or {}).get(form_key) or {}
        data = self._gather_form_widgets(widgets)
        try:
            save_debrief_form(int(debrief_id), str(form_key), dict(data))
            # Flag for review when saved
            update_debrief_header(int(debrief_id), {"flagged_for_review": 1})
            self.load_debriefs()
            try:
                QMessageBox.information(self, "Debrief", "Saved.")
            except Exception:
                pass
        except Exception as e:
            try:
                QMessageBox.warning(self, "Debrief", f"Could not save: {e}")
            except Exception:
                pass

    def _submit_selected_debrief(self) -> None:
        did = self._selected_debrief_id()
        if not did:
            return
        # Use bridge to set status and write audit if available
        try:
            from modules.operations.taskings.bridge import TaskingsBridge
            br = TaskingsBridge()
            br.submitDebrief(int(did))
        except Exception:
            try:
                from modules.operations.taskings.repository import update_debrief_header
                update_debrief_header(int(did), {"status": "Submitted", "flagged_for_review": 1})
            except Exception:
                pass
        self.load_debriefs()
        try:
            QMessageBox.information(self, "Debrief", "Submitted for review.")
        except Exception:
            pass

    def _mark_selected_debrief_reviewed(self) -> None:
        did = self._selected_debrief_id()
        if not did:
            return
        try:
            from modules.operations.taskings.bridge import TaskingsBridge
            br = TaskingsBridge(); br.markDebriefReviewed(int(did))
        except Exception:
            try:
                from modules.operations.taskings.repository import update_debrief_header
                update_debrief_header(int(did), {"status": "Reviewed", "flagged_for_review": 0})
            except Exception:
                pass
        self.load_debriefs()

    def _archive_selected_debrief(self) -> None:
        did = self._selected_debrief_id()
        if not did:
            return
        try:
            from modules.operations.taskings.repository import archive_debrief
            archive_debrief(int(did))
        except Exception:
            pass
        self.load_debriefs()

    def _delete_selected_debrief(self) -> None:
        did = self._selected_debrief_id()
        if not did:
            return
        try:
            resp = QMessageBox.question(self, "Delete", "Delete selected debrief?")
            if resp != QMessageBox.Yes:
                return
        except Exception:
            pass
        try:
            from modules.operations.taskings.repository import delete_debrief
            delete_debrief(int(did))
        except Exception:
            pass
        self.load_debriefs()
