from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QStyledItemDelegate,
    QSizePolicy,
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
        return dt.strftime("%m-%d-%y %H:%M:%S")
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


class TaskDetailWindow(QWidget):
    """QWidget-based Task Detail window with embedded Narrative tab."""

    def __init__(self, task_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task_id = int(task_id)
        self.setWindowTitle(f"Task Detail — {task_id}")
        self.resize(1100, 720)

        root = QVBoxLayout(self)

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
        self._prio = QComboBox(self);
        self._prio.addItems(self._lookups["priorities"])  # Priority
        self._stat = QComboBox(self);
        self._stat.addItems(self._lookups["statuses"])  # Status
        self._task_id_edit = QLineEdit(self);
        self._task_id_edit.setPlaceholderText("Task ID")
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

        # Title/Location/Assignment row + Save/Cancel
        row2 = QHBoxLayout()
        self._title_edit = QLineEdit(self); self._title_edit.setPlaceholderText("Task Title")
        self._location_edit = QLineEdit(self); self._location_edit.setPlaceholderText("Location")
        self._assignment_edit = QLineEdit(self); self._assignment_edit.setPlaceholderText("Assignment")
        self._save_btn = QPushButton("Save"); self._save_btn.clicked.connect(self._save_header)
        self._cancel_btn = QPushButton("Cancel"); self._cancel_btn.clicked.connect(self._load_header)
        for lab, w in [("Title", self._title_edit),("Location", self._location_edit),("Assignment", self._assignment_edit)]:
            row2.addWidget(QLabel(lab)); row2.addWidget(w, 1)
        row2.addStretch(1)
        row2.addWidget(self._save_btn); row2.addWidget(self._cancel_btn)
        root.addLayout(row2)

        # Team leader row
        row_team = QHBoxLayout()
        self._team_leader_edit = QLineEdit(self); self._team_leader_edit.setPlaceholderText("Team Leader Name")
        self._team_phone_edit = QLineEdit(self); self._team_phone_edit.setPlaceholderText("Team Leader Phone")
        row_team.addWidget(QLabel("Team Leader")); row_team.addWidget(self._team_leader_edit, 1)
        row_team.addWidget(QLabel("Phone")); row_team.addWidget(self._team_phone_edit, 1)
        root.addLayout(row_team)

        # Header summary
        self._title_lbl = QLabel("Task Detail")
        self._title_lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._primary_team_lbl = QLabel("")
        self._status_lbl = QLabel("")
        header = QHBoxLayout()
        header.addWidget(self._title_lbl)
        header.addSpacing(18)
        header.addWidget(QLabel("Primary Team:"))
        header.addWidget(self._primary_team_lbl)
        header.addSpacing(18)
        header.addWidget(QLabel("Status:"))
        header.addWidget(self._status_lbl)
        header.addStretch(1)
        root.addLayout(header)

        # Tabs
        tabs = QTabWidget(self)
        root.addWidget(tabs, 1)

        # Narrative tab
        self._nar_model = QStandardItemModel(0, 6, self)
        self._nar_model.setHorizontalHeaderLabels(["ID", "Date/Time (UTC)", "Entry", "Entered By", "Team", "Critical"]) 
        nar_widget = QWidget(self)
        nar_layout = QVBoxLayout(nar_widget)
        try:
            nar_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        quick = QHBoxLayout()
        try:
            quick.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._nar_entry = QLineEdit(self)
        self._nar_entry.setPlaceholderText("Type narrative… (Enter to add)")
        self._nar_entry.returnPressed.connect(self.add_narrative)
        self._nar_crit = QComboBox(self)
        self._nar_crit.addItems(["No", "Yes"])
        add_btn = QPushButton("Add")
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
        hh: QHeaderView = self._nar_table.horizontalHeader()
        # Default: interactive columns; make Entry column stretch to fill remaining width
        try:
            hh.setStretchLastSection(False)
            hh.setSectionResizeMode(QHeaderView.Interactive)
            hh.setSectionResizeMode(2, QHeaderView.Stretch)  # Entry
        except Exception:
            pass
        self._nar_table.setItemDelegateForColumn(5, _YesNoDelegate(self._nar_table))

        nar_layout.addLayout(quick)
        nar_layout.addWidget(self._nar_table, 1)
        tabs.addTab(nar_widget, "Narrative")

        # Teams tab
        teams_widget = QWidget(self)
        teams_layout = QVBoxLayout(teams_widget)
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
        tbar.addStretch(1)
        teams_layout.addLayout(tbar)
        self._teams_model = QStandardItemModel(0, 13, self)
        self._teams_model.setHorizontalHeaderLabels(["ID", "Primary", "Sortie", "Team", "Leader", "Phone", "Status", "Assigned", "Briefed", "Enroute", "Arrival", "Discovery", "Complete"]) 
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
            th.setSectionResizeMode(QHeaderView.Interactive)
            th.setSectionResizeMode(3, QHeaderView.Stretch)
        except Exception:
            pass
        teams_layout.addWidget(self._teams_table, 1)
        tabs.addTab(teams_widget, "Teams")

        # Personnel tab
        pers_widget = QWidget(self)
        pers_layout = QVBoxLayout(pers_widget)
        try:
            pers_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        self._pers_model = QStandardItemModel(0, 8, self)
        self._pers_model.setHorizontalHeaderLabels(["Active", "Name", "ID", "Rank", "Role", "Organization", "Phone", "Team"]) 
        self._pers_table = QTableView(self)
        self._pers_table.setModel(self._pers_model)
        self._pers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._pers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._pers_table.setAlternatingRowColors(True)
        self._pers_table.setSortingEnabled(True)
        thp: QHeaderView = self._pers_table.horizontalHeader()
        try:
            thp.setStretchLastSection(False)
            thp.setSectionResizeMode(QHeaderView.Interactive)
            thp.setSectionResizeMode(1, QHeaderView.Stretch)
        except Exception:
            pass
        pers_layout.addWidget(self._pers_table, 1)
        tabs.addTab(pers_widget, "Personnel")

        # Other tabs (placeholders, kept minimal to avoid scope growth)
        tabs.addTab(QLabel("Teams — coming soon"), "Teams")
        tabs.addTab(QLabel("Personnel — coming soon"), "Personnel")
        # Vehicles tab
        veh_widget = QWidget(self)
        veh_layout = QVBoxLayout(veh_widget)
        try:
            veh_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        # Vehicles (ground)
        self._veh_model = QStandardItemModel(0, 5, self)
        self._veh_model.setHorizontalHeaderLabels(["Active", "ID", "License Plate", "Type", "Organization"]) 
        self._veh_table = QTableView(self)
        self._veh_table.setModel(self._veh_model)
        self._veh_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._veh_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._veh_table.setAlternatingRowColors(True)
        self._veh_table.setSortingEnabled(True)
        veh_layout.addWidget(self._veh_table)
        # Aircraft
        self._air_label = QLabel("Aircraft")
        veh_layout.addWidget(self._air_label)
        self._air_model = QStandardItemModel(0, 5, self)
        self._air_model.setHorizontalHeaderLabels(["Active", "Callsign", "Tail Number", "Type", "Organization"]) 
        self._air_table = QTableView(self)
        self._air_table.setModel(self._air_model)
        self._air_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._air_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._air_table.setAlternatingRowColors(True)
        self._air_table.setSortingEnabled(True)
        veh_layout.addWidget(self._air_table)
        tabs.addTab(veh_widget, "Vehicles")
        tabs.addTab(QLabel("Assignment Details — coming soon"), "Assignment Details")
        tabs.addTab(QLabel("Communications — coming soon"), "Communications")
        tabs.addTab(QLabel("Debriefing — coming soon"), "Debriefing")
        tabs.addTab(QLabel("Log — coming soon"), "Log")
        tabs.addTab(QLabel("Attachments/Forms — coming soon"), "Attachments/Forms")
        tabs.addTab(QLabel("Planning — coming soon"), "Planning")

        # Initial data load
        self._load_header()
        self.load_narrative()
        try:
            self.load_vehicles()
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

    # --- Header ---
    def _load_header(self) -> None:
        d = self._repo_detail()
        try:
            t = (d or {}).get("task") or {}
            tid = t.get("task_id") or self._task_id
            title = t.get("title") or ""
            status = t.get("status") or ""
            self._title_lbl.setText(" - ".join([str(x) for x in [tid, title] if str(x)]))
            self._status_lbl.setText(str(status))
            self._primary_team_lbl.setText(self._primary_team_name(d))
        except Exception:
            pass

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
            items[5].setData(crit, Qt.EditRole)
            if crit:
                hl = QColor(Qt.red).lighter(160)
                for it in items:
                    it.setData(hl, Qt.BackgroundRole)
            self._nar_model.appendRow(items)
        # Default widths
        self._nar_table.setColumnWidth(1, 180)
        self._nar_table.setColumnWidth(3, 160)
        self._nar_table.setColumnWidth(4, 140)
        self._nar_table.setColumnWidth(5, 100)

    def add_narrative(self) -> None:
        text = self._nar_entry.text().strip()
        if not text:
            return
        payload = {
            "taskid": self._task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "narrative": text,
            "entered_by": "",
            "team_num": "",
            "critical": 1 if self._nar_crit.currentIndex() == 1 else 0,
        }
        try:
            ib = self._ib()
            ib.createTaskNarrative(payload)
            self._nar_entry.clear()
            self._nar_crit.setCurrentIndex(0)
            self.load_narrative()
        except Exception:
            # Ignore failures silently for now
            pass

    # --- Save/Load Header Ops ---
    def _save_header(self) -> None:
        try:
            from modules.operations.taskings.repository import update_task_header
            typ_val = self._typ.currentText() if hasattr(self, '_typ') else ''
            if typ_val in ('(select type)', '(select category first)'):
                typ_val = ''
            payload = {
                'task_id': self._task_id_edit.text().strip() if hasattr(self, '_task_id_edit') else str(self._task_id),
                'title': self._title_edit.text().strip() if hasattr(self, '_title_edit') else '',
                'location': self._location_edit.text().strip() if hasattr(self, '_location_edit') else '',
                'assignment': self._assignment_edit.text().strip() if hasattr(self, '_assignment_edit') else '',
                'team_leader': self._team_leader_edit.text().strip() if hasattr(self, '_team_leader_edit') else '',
                'team_phone': self._team_phone_edit.text().strip() if hasattr(self, '_team_phone_edit') else '',
                'category': self._cat.currentText() if hasattr(self, '_cat') else '',
                'task_type': typ_val,
                'priority': self._prio.currentText() if hasattr(self, '_prio') else '',
                'status': self._stat.currentText() if hasattr(self, '_stat') else '',
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

