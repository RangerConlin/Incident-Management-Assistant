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
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QStyledItemDelegate,
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

        # Other tabs (placeholders, kept minimal to avoid scope growth)
        tabs.addTab(QLabel("Teams — coming soon"), "Teams")
        tabs.addTab(QLabel("Personnel — coming soon"), "Personnel")
        tabs.addTab(QLabel("Vehicles — coming soon"), "Vehicles")
        tabs.addTab(QLabel("Assignment Details — coming soon"), "Assignment Details")
        tabs.addTab(QLabel("Communications — coming soon"), "Communications")
        tabs.addTab(QLabel("Debriefing — coming soon"), "Debriefing")
        tabs.addTab(QLabel("Log — coming soon"), "Log")
        tabs.addTab(QLabel("Attachments/Forms — coming soon"), "Attachments/Forms")
        tabs.addTab(QLabel("Planning — coming soon"), "Planning")

        # Initial data load
        self._load_header()
        self.load_narrative()

    # --- Data Bridges ---
    def _ib(self):
        from bridge.incident_bridge import IncidentBridge

        return IncidentBridge()

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
