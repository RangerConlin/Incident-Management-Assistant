from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, List, Any

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore

try:  # pragma: no cover - real Qt path
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QHBoxLayout, QPushButton, QLineEdit, QMessageBox, QFrame,
        QGridLayout, QSizePolicy,
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont, QColor
    _QT = True
except Exception:  # pragma: no cover - headless fallback
    _QT = False

    class QWidget:  # type: ignore[misc]
        def __init__(self, *a, **k): pass
        def setStyleSheet(self, *a, **k): pass
        def setSizePolicy(self, *a, **k): pass
        def setFixedHeight(self, *a, **k): pass
        def setMinimumWidth(self, *a, **k): pass

    class _Layout:
        def __init__(self, *a, **k): pass
        def addWidget(self, *a, **k): pass
        def addLayout(self, *a, **k): pass
        def setContentsMargins(self, *a, **k): pass
        def setSpacing(self, *a, **k): pass
        def addStretch(self, *a, **k): pass
        def addItem(self, *a, **k): pass

    class QVBoxLayout(_Layout): pass
    class QHBoxLayout(_Layout): pass
    class QGridLayout(_Layout):
        def addWidget(self, *a, **k): pass
        def setColumnStretch(self, *a, **k): pass

    class QLabel:
        def __init__(self, *a, **k): pass
        def setStyleSheet(self, *a, **k): pass
        def setFont(self, *a, **k): pass
        def setAlignment(self, *a, **k): pass
        def setWordWrap(self, *a, **k): pass
        def setText(self, *a, **k): pass
        def setFixedHeight(self, *a, **k): pass

    class QListWidget(QWidget):
        def clear(self): pass
        def addItem(self, *a, **k): pass
        def setStyleSheet(self, *a, **k): pass

    class QListWidgetItem:
        def __init__(self, *a, **k): pass
        def setForeground(self, *a, **k): pass
        def setFont(self, *a, **k): pass

    class QPushButton(QWidget):
        def __init__(self, *a, **k): pass
        def clicked(self): return lambda: None

    class QLineEdit(QWidget):
        def __init__(self, *a, **k): pass
        def setPlaceholderText(self, *a, **k): pass
        def text(self): return ""

    class QMessageBox(QWidget):
        @staticmethod
        def information(*a, **k): pass
        @staticmethod
        def warning(*a, **k): pass
        @staticmethod
        def critical(*a, **k): pass

    class QFrame(QWidget):
        HLine = 4
        Sunken = 2
        def setFrameShape(self, *a, **k): pass
        def setFrameShadow(self, *a, **k): pass
        def setFixedHeight(self, *a, **k): pass

    class QGridLayout(_Layout): pass

    class QSizePolicy:
        Expanding = 7
        Preferred = 4
        Minimum = 1
        def __init__(self, *a, **k): pass

    class QTimer:
        def __init__(self, *a, **k): pass
        def setInterval(self, *a, **k): pass
        def timeout(self): return type("sig", (), {"connect": lambda self, f: None})()
        def start(self, *a, **k): pass

    class Qt:
        AlignCenter = 0x4 | 0x80
        AlignLeft = 0x1
        AlignRight = 0x2
        AlignTop = 0x20
        AlignVCenter = 0x80

    class QFont:
        def __init__(self, *a, **k): pass
        def setBold(self, *a, **k): pass
        def setPointSize(self, *a, **k): pass

    class QColor:
        def __init__(self, *a, **k): pass

from utils.settingsmanager import SettingsManager

# ---------------------------------------------------------------------------
# Palette helpers
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    # team/task statuses
    "available":       "#4caf50",
    "staging":         "#4caf50",
    "assigned":        "#2196f3",
    "enroute":         "#2196f3",
    "arrival":         "#2196f3",
    "returning":       "#ff9800",
    "returning to base": "#ff9800",
    "find":            "#9c27b0",
    "out of service":  "#f44336",
    "unavailable":     "#f44336",
    "demobilized":     "#9e9e9e",
    # task statuses
    "draft":           "#9e9e9e",
    "planned":         "#607d8b",
    "in progress":     "#2196f3",
    "completed":       "#4caf50",
    "cancelled":       "#f44336",
    # risk levels
    "l":  "#4caf50",
    "m":  "#ff9800",
    "h":  "#f44336",
    "eh": "#9c27b0",
}


def _status_color(status: str) -> str:
    return _STATUS_COLORS.get(status.lower().strip(), "#bdbdbd")


def _risk_color(risk: str) -> str:
    return _STATUS_COLORS.get((risk or "").lower().strip(), "#bdbdbd")


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _vbox(widget: QWidget, margins: int = 8, spacing: int = 6) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    try:
        layout.setContentsMargins(margins, margins, margins, margins)
        layout.setSpacing(spacing)
    except Exception:
        pass
    return layout


def _hbox(spacing: int = 6) -> QHBoxLayout:
    layout = QHBoxLayout()
    try:
        layout.setSpacing(spacing)
        layout.setContentsMargins(0, 0, 0, 0)
    except Exception:
        pass
    return layout


def _bold_label(text: str) -> QLabel:
    lbl = QLabel(text)
    try:
        f = QFont()
        f.setBold(True)
        lbl.setFont(f)
    except Exception:
        pass
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    try:
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(1)
        line.setStyleSheet("color: rgba(128,128,128,0.3);")
    except Exception:
        pass
    return line


def _section_header(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    try:
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: rgba(128,128,128,0.8);"
            "letter-spacing: 1px; margin-top: 4px;"
        )
    except Exception:
        pass
    return lbl


# ---------------------------------------------------------------------------
# LiveWidget base — auto-refresh + last-updated footer
# ---------------------------------------------------------------------------

_REFRESH_INTERVAL_MS = 30_000


class LiveWidget(QWidget):
    """Base class for widgets that poll data on a timer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        try:
            self._timer.timeout.connect(self.refresh)
            self._timer.start(_REFRESH_INTERVAL_MS)
        except Exception:
            pass

    def refresh(self):
        """Subclasses override this to reload and re-render data."""

    def _updated_label(self) -> QLabel:
        lbl = QLabel()
        try:
            lbl.setStyleSheet("font-size: 9px; color: rgba(128,128,128,0.6);")
            lbl.setAlignment(Qt.AlignRight)
        except Exception:
            pass
        self._ts_label = lbl
        return lbl

    def _touch_timestamp(self):
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            self._ts_label.setText(f"Updated {ts}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Incident Info
# ---------------------------------------------------------------------------

class IncidentInfoWidget(LiveWidget):
    def __init__(self, incident_provider: Callable, user_provider: Callable, parent=None):
        super().__init__(parent)
        self._incident_provider = incident_provider
        self._user_provider = user_provider
        layout = _vbox(self, margins=10, spacing=4)

        self._name_lbl = _bold_label("—")
        try:
            self._name_lbl.setStyleSheet("font-size: 13px;")
        except Exception:
            pass
        layout.addWidget(self._name_lbl)

        grid = QGridLayout()
        try:
            grid.setSpacing(4)
            grid.setContentsMargins(0, 4, 0, 0)
        except Exception:
            pass

        def _kv(row, col_label, col_val, key, value):
            k = QLabel(key + ":")
            v = QLabel(value)
            try:
                k.setStyleSheet("color: rgba(128,128,128,0.9); font-size: 11px;")
                v.setStyleSheet("font-size: 11px;")
            except Exception:
                pass
            try:
                grid.addWidget(k, row, col_label)
                grid.addWidget(v, row, col_val)
            except Exception:
                pass
            return v

        self._number_v  = _kv(0, 0, 1, "Number", "—")
        self._type_v    = _kv(0, 2, 3, "Type", "—")
        self._status_v  = _kv(1, 0, 1, "Status", "—")
        self._period_v  = _kv(1, 2, 3, "Op Period", "—")
        self._icp_v     = _kv(2, 0, 1, "ICP", "—")
        self._start_v   = _kv(2, 2, 3, "Start", "—")

        try:
            grid.setColumnStretch(1, 2)
            grid.setColumnStretch(3, 2)
        except Exception:
            pass

        layout.addLayout(grid)
        layout.addWidget(_separator())

        row_user = _hbox(4)
        self._user_lbl = QLabel("—")
        try:
            self._user_lbl.setStyleSheet("font-size: 11px; color: rgba(128,128,128,0.9);")
        except Exception:
            pass
        try:
            row_user.addWidget(QLabel("Logged in as:"))
            row_user.addWidget(self._user_lbl)
            row_user.addStretch()
        except Exception:
            pass
        layout.addLayout(row_user)
        layout.addStretch()
        layout.addWidget(self._updated_label())

        self.refresh()

    def refresh(self):
        try:
            d = self._incident_provider()
            self._name_lbl.setText(d.get("name", "—"))
            self._number_v.setText(d.get("number", "—"))
            self._type_v.setText(d.get("type", "—"))
            status = d.get("status", "—")
            self._status_v.setText(status)
            try:
                self._status_v.setStyleSheet(
                    f"font-size:11px; color: {_status_color(status)}; font-weight: bold;"
                )
            except Exception:
                pass
            self._period_v.setText(str(d.get("operational_period", "—")))
            self._icp_v.setText(d.get("icp_location", "—"))
            self._start_v.setText(str(d.get("start_time", "—"))[:16])
            u = self._user_provider()
            self._user_lbl.setText(f"{u.get('name', '—')} ({u.get('role', '—')})")
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Team Status Board
# ---------------------------------------------------------------------------

class TeamStatusBoardWidget(LiveWidget):
    def __init__(self, title: str = "Team Status", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))

        # Count row
        count_row = _hbox(12)
        self._avail_lbl  = self._big_count("Available", "#4caf50")
        self._assign_lbl = self._big_count("Assigned", "#2196f3")
        self._oos_lbl    = self._big_count("OOS", "#f44336")
        try:
            for w in (self._avail_lbl, self._assign_lbl, self._oos_lbl):
                count_row.addWidget(w)
            count_row.addStretch()
        except Exception:
            pass
        layout.addLayout(count_row)
        layout.addWidget(_separator())

        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())

        self.refresh()

    def _big_count(self, label: str, color: str):
        wrapper = QWidget()
        vb = QVBoxLayout(wrapper)
        try:
            vb.setSpacing(0)
            vb.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        num = QLabel("0")
        try:
            num.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
            num.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        cap = QLabel(label)
        try:
            cap.setStyleSheet("font-size: 9px; color: rgba(128,128,128,0.8);")
            cap.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        try:
            vb.addWidget(num)
            vb.addWidget(cap)
        except Exception:
            pass
        wrapper._num = num  # type: ignore[attr-defined]
        return wrapper

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            counts = dp.teams_getStatusSummary()
            self._avail_lbl._num.setText(str(counts.get("available", 0)))
            self._assign_lbl._num.setText(str(counts.get("assigned", 0)))
            self._oos_lbl._num.setText(str(counts.get("out_of_service", 0)))

            teams = dp.teams_getList()
            try:
                self._list.clear()
            except Exception:
                pass
            for t in teams:
                name = t.get("team_name") or t.get("name") or "?"
                status = str(t.get("status") or "?")
                text = f"  {name}  —  {status}"
                item = QListWidgetItem(text)
                try:
                    item.setForeground(QColor(_status_color(status)))
                except Exception:
                    pass
                try:
                    self._list.addItem(item)
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Task Status Board
# ---------------------------------------------------------------------------

class TaskStatusBoardWidget(LiveWidget):
    def __init__(self, title: str = "Task Status", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))

        count_row = _hbox(8)
        self._counts: dict[str, QWidget] = {}
        for key, label, color in [
            ("draft", "Draft", "#9e9e9e"),
            ("planned", "Planned", "#607d8b"),
            ("in_progress", "Active", "#2196f3"),
            ("completed", "Done", "#4caf50"),
            ("cancelled", "Cancelled", "#f44336"),
        ]:
            w = self._mini_count(label, color)
            self._counts[key] = w
            try:
                count_row.addWidget(w)
            except Exception:
                pass
        try:
            count_row.addStretch()
        except Exception:
            pass
        layout.addLayout(count_row)
        layout.addWidget(_separator())

        layout.addWidget(_section_header("Due Soon"))
        self._due_list = QListWidget()
        try:
            self._due_list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._due_list)
        layout.addWidget(self._updated_label())

        self.refresh()

    def _mini_count(self, label: str, color: str):
        wrapper = QWidget()
        vb = QVBoxLayout(wrapper)
        try:
            vb.setSpacing(1)
            vb.setContentsMargins(4, 2, 4, 2)
        except Exception:
            pass
        num = QLabel("0")
        try:
            num.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
            num.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        cap = QLabel(label)
        try:
            cap.setStyleSheet("font-size: 9px; color: rgba(128,128,128,0.8);")
            cap.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        try:
            vb.addWidget(num)
            vb.addWidget(cap)
        except Exception:
            pass
        wrapper._num = num  # type: ignore[attr-defined]
        return wrapper

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            counts = dp.tasks_getSummary_active()
            for key, w in self._counts.items():
                w._num.setText(str(counts.get(key, 0)))

            due = dp.tasks_getDueSoon()
            try:
                self._due_list.clear()
            except Exception:
                pass
            if due:
                for item in due:
                    title = item.get("title", "?")
                    due_time = str(item.get("due_time", ""))[:16].replace("T", " ")
                    team = item.get("assigned_to") or item.get("primary_team") or ""
                    text = title
                    if due_time:
                        text += f"  ({due_time})"
                    if team:
                        text += f"  → {team}"
                    try:
                        self._due_list.addItem(QListWidgetItem(text))
                    except Exception:
                        pass
            else:
                try:
                    self._due_list.addItem(QListWidgetItem("No tasks due soon"))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Personnel Availability (mock backend — no clean query available yet)
# ---------------------------------------------------------------------------

class PersonnelAvailabilityWidget(LiveWidget):
    def __init__(self, title: str = "Personnel", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))

        count_row = _hbox(12)
        self._avail  = self._big_count("Available", "#4caf50")
        self._assign = self._big_count("Assigned", "#2196f3")
        self._out    = self._big_count("Unavailable", "#9e9e9e")
        try:
            for w in (self._avail, self._assign, self._out):
                count_row.addWidget(w)
            count_row.addStretch()
        except Exception:
            pass
        layout.addLayout(count_row)
        layout.addStretch()
        layout.addWidget(self._updated_label())
        self.refresh()

    def _big_count(self, label: str, color: str):
        wrapper = QWidget()
        vb = QVBoxLayout(wrapper)
        try:
            vb.setSpacing(0)
            vb.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        num = QLabel("0")
        try:
            num.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
            num.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        cap = QLabel(label)
        try:
            cap.setStyleSheet("font-size: 9px; color: rgba(128,128,128,0.8);")
            cap.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        try:
            vb.addWidget(num)
            vb.addWidget(cap)
        except Exception:
            pass
        wrapper._num = num  # type: ignore[attr-defined]
        return wrapper

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            s = dp.personnel_getAvailabilitySummary()
            self._avail._num.setText(str(s.get("available", s.get("checked_in", 0))))
            self._assign._num.setText(str(s.get("assigned", 0)))
            self._out._num.setText(str(s.get("unavailable", s.get("checked_out", 0))))
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Equipment Snapshot
# ---------------------------------------------------------------------------

class EquipmentSnapshotWidget(LiveWidget):
    def __init__(self, title: str = "Equipment", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))

        count_row = _hbox(12)
        self._total  = self._mini("Total", "#607d8b")
        self._assign = self._mini("Assigned", "#2196f3")
        self._oos    = self._mini("OOS", "#f44336")
        try:
            for w in (self._total, self._assign, self._oos):
                count_row.addWidget(w)
            count_row.addStretch()
        except Exception:
            pass
        layout.addLayout(count_row)
        layout.addStretch()
        layout.addWidget(self._updated_label())
        self.refresh()

    def _mini(self, label: str, color: str):
        wrapper = QWidget()
        vb = QVBoxLayout(wrapper)
        try:
            vb.setSpacing(0)
            vb.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass
        num = QLabel("0")
        try:
            num.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
            num.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        cap = QLabel(label)
        try:
            cap.setStyleSheet("font-size: 9px; color: rgba(128,128,128,0.8);")
            cap.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        try:
            vb.addWidget(num)
            vb.addWidget(cap)
        except Exception:
            pass
        wrapper._num = num  # type: ignore[attr-defined]
        return wrapper

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            s = dp.equipment_getSnapshot()
            self._total._num.setText(str(s.get("checked_in", 0)))
            self._assign._num.setText(str(s.get("assigned", 0)))
            self._oos._num.setText(str(s.get("out_of_service", 0)))
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Vehicle / Aircraft Snapshot
# ---------------------------------------------------------------------------

class VehicleSnapshotWidget(LiveWidget):
    def __init__(self, title: str = "Vehicles/Aircraft", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))

        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            vehicles = dp.vehicles_getStatus()
            aircraft = dp.aircraft_getStatus()

            try:
                self._list.clear()
            except Exception:
                pass

            if not vehicles and not aircraft:
                try:
                    self._list.addItem(QListWidgetItem("No vehicles or aircraft on file"))
                except Exception:
                    pass
                self._touch_timestamp()
                return

            for v in vehicles:
                unit = v.get("unit", "?")
                status = str(v.get("status", "?"))
                item = QListWidgetItem(f"🚗  {unit}  —  {status}")
                try:
                    item.setForeground(QColor(_status_color(status)))
                except Exception:
                    pass
                try:
                    self._list.addItem(item)
                except Exception:
                    pass

            for a in aircraft:
                tail = a.get("tail", "?")
                status = str(a.get("status", "?"))
                item = QListWidgetItem(f"✈  {tail}  —  {status}")
                try:
                    item.setForeground(QColor(_status_color(status)))
                except Exception:
                    pass
                try:
                    self._list.addItem(item)
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Operations Feed (placeholder — no events backend yet)
# ---------------------------------------------------------------------------

class OpsDashboardFeedWidget(LiveWidget):
    def __init__(self, title: str = "Operations Feed", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            events = dp.ops_getRecentEvents(20)
            try:
                self._list.clear()
            except Exception:
                pass
            if events:
                for e in events:
                    try:
                        self._list.addItem(QListWidgetItem(str(e)))
                    except Exception:
                        pass
            else:
                try:
                    self._list.addItem(QListWidgetItem("No recent events"))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Comms — Recent Messages
# ---------------------------------------------------------------------------

class RecentMessagesWidget(LiveWidget):
    def __init__(self, title: str = "Recent Messages", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            msgs = dp.comms_getRecentMessages(20)
            try:
                self._list.clear()
            except Exception:
                pass
            for m in msgs or ["No messages"]:
                try:
                    self._list.addItem(QListWidgetItem(str(m)))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Notifications (safety + system alerts)
# ---------------------------------------------------------------------------

class NotificationsWidget(LiveWidget):
    def __init__(self, title: str = "Notifications", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            alerts = dp.alerts_getAll_min_info()
            try:
                self._list.clear()
            except Exception:
                pass
            for a in alerts or ["No active alerts"]:
                try:
                    self._list.addItem(QListWidgetItem(str(a)))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# ICS-205 Comm Plan
# ---------------------------------------------------------------------------

class ICS205CommPlanWidget(LiveWidget):
    def __init__(self, title: str = "ICS-205", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))

        self._list = QListWidget()
        try:
            self._list.setStyleSheet(
                "QListWidget { border: none; font-family: monospace; font-size: 11px; }"
            )
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            channels = dp.comms_getChannels()
            try:
                self._list.clear()
            except Exception:
                pass

            if not channels:
                freqs = dp.comms_getPrimaryFrequencies()
                for f in freqs:
                    try:
                        self._list.addItem(QListWidgetItem(str(f)))
                    except Exception:
                        pass
                self._touch_timestamp()
                return

            for ch in channels:
                name = ch.get("channel") or ch.get("name") or "—"
                fn   = ch.get("function") or ""
                mode = ch.get("mode") or ""
                line = f"{name:<12}  {fn:<20}  {mode}"
                try:
                    self._list.addItem(QListWidgetItem(line.rstrip()))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Comms Log Feed
# ---------------------------------------------------------------------------

class CommLogFeedWidget(LiveWidget):
    def __init__(self, title: str = "Comms Log", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            entries = dp.comms_getCommsLog(50)
            try:
                self._list.clear()
            except Exception:
                pass
            for e in entries or ["No log entries"]:
                try:
                    self._list.addItem(QListWidgetItem(str(e)))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Objectives Tracker
# ---------------------------------------------------------------------------

class ObjectivesTrackerWidget(LiveWidget):
    def __init__(self, title: str = "Objectives", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            objectives = dp.planning_getObjectives()
            try:
                self._list.clear()
            except Exception:
                pass
            for obj in objectives:
                item = QListWidgetItem(str(obj))
                if "✓" in str(obj):
                    try:
                        item.setForeground(QColor("#4caf50"))
                    except Exception:
                        pass
                try:
                    self._list.addItem(item)
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Forms In Progress (placeholder)
# ---------------------------------------------------------------------------

class FormsInProgressWidget(LiveWidget):
    def __init__(self, title: str = "Open Forms", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self._populate(items)

    def _populate(self, items):
        for text in (items or ["No open forms"]):
            try:
                self._list.addItem(QListWidgetItem(str(text)))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# SITREP Feed (placeholder)
# ---------------------------------------------------------------------------

class SitrepFeedWidget(LiveWidget):
    def __init__(self, title: str = "SITREP", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("No SITREP data available")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


# ---------------------------------------------------------------------------
# Upcoming Tasks
# ---------------------------------------------------------------------------

class UpcomingTasksWidget(LiveWidget):
    def __init__(self, title: str = "Upcoming Tasks", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            tasks = dp.planning_getUpcomingTasks()
            try:
                self._list.clear()
            except Exception:
                pass
            for t in tasks or ["No upcoming tasks"]:
                try:
                    self._list.addItem(QListWidgetItem(str(t)))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Safety Alerts
# ---------------------------------------------------------------------------

_RISK_DISPLAY = {"EH": "EXTREME", "H": "HIGH", "M": "MEDIUM", "L": "LOW"}


class SafetyAlertsWidget(LiveWidget):
    def __init__(self, title: str = "Safety Alerts", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            hazards = dp.safety_getHazards()
            try:
                self._list.clear()
            except Exception:
                pass

            if not hazards:
                try:
                    item = QListWidgetItem("No active hazards")
                    item.setForeground(QColor("#4caf50"))
                    self._list.addItem(item)
                except Exception:
                    pass
                self._touch_timestamp()
                return

            for h in hazards:
                risk = h.residual_risk or "?"
                label = _RISK_DISPLAY.get(risk.upper(), risk.upper())
                activity = (h.sub_activity or "").strip()
                outcome = (h.hazard_outcome or "").strip()[:55]
                text = f"[{label}]  {activity}: {outcome}"
                item = QListWidgetItem(text)
                try:
                    item.setForeground(QColor(_risk_color(risk)))
                except Exception:
                    pass
                try:
                    self._list.addItem(item)
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Medical Incident Log (placeholder — no backend yet)
# ---------------------------------------------------------------------------

class MedicalIncidentLogWidget(LiveWidget):
    def __init__(self, title: str = "Medical Incidents", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("No medical log data available")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


# ---------------------------------------------------------------------------
# ICS-206 Snapshot (placeholder — no backend yet)
# ---------------------------------------------------------------------------

class ICS206SnapshotWidget(LiveWidget):
    def __init__(self, title: str = "ICS-206 Snapshot", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("No ICS-206 data available")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


# ---------------------------------------------------------------------------
# Intel Dashboard (placeholder — no backend yet)
# ---------------------------------------------------------------------------

class IntelDashboardWidget(LiveWidget):
    def __init__(self, title: str = "Intel Dashboard", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("No intel data available")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


# ---------------------------------------------------------------------------
# Clue Log Snapshot (placeholder — no backend yet)
# ---------------------------------------------------------------------------

class ClueLogSnapshotWidget(LiveWidget):
    def __init__(self, title: str = "Clue Log", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("No clue log data available")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


# ---------------------------------------------------------------------------
# Map Snapshot (placeholder — no widget backend yet)
# ---------------------------------------------------------------------------

class MapSnapshotWidget(LiveWidget):
    def __init__(self, title: str = "Map Snapshot", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("Map widget not available in this view")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


# ---------------------------------------------------------------------------
# PIO — Press Drafts / Media Log / Briefing Queue (placeholders)
# ---------------------------------------------------------------------------

class PressDraftsWidget(LiveWidget):
    def __init__(self, title: str = "Draft Press Releases", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            drafts = dp.pio_getPressDrafts()
            try:
                self._list.clear()
            except Exception:
                pass
            for d in drafts or ["No press drafts"]:
                try:
                    self._list.addItem(QListWidgetItem(str(d)))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


class MediaLogWidget(LiveWidget):
    def __init__(self, title: str = "Media Log", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        lbl = QLabel("No media log data available")
        try:
            lbl.setStyleSheet("color: rgba(128,128,128,0.7); font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())


class BriefingQueueWidget(LiveWidget):
    def __init__(self, title: str = "Briefing Queue", items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header(title))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            items = dp.pio_getPendingApprovals()
            try:
                self._list.clear()
            except Exception:
                pass
            for it in items or ["No pending approvals"]:
                try:
                    self._list.addItem(QListWidgetItem(str(it)))
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Quick Entry
# ---------------------------------------------------------------------------

class QuickEntryWidget(QWidget):
    """Quick actions toolbar + simple command line."""

    def __init__(self, action_router: Callable[[str, dict], None], cli_execute: Callable[[str], str], parent=None):
        super().__init__(parent)
        self._router = action_router
        self._cli = cli_execute

        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header("Quick Entry"))
        row = _hbox(4)
        layout.addLayout(row)

        def btn(text: str, action: str, payload: dict | None = None):
            b = QPushButton(text, self)
            try:
                b.clicked.connect(lambda: self._safe_dispatch(action, payload or {}))
            except Exception:
                pass
            try:
                row.addWidget(b)
            except Exception:
                pass

        btn("New Task", "tasks.create")
        btn("Log Entry (214)", "logs.createActivity")
        btn("Comm Entry (213)", "comms.createLogEntry")
        btn("Resource Request", "logistics.createResourceRequest")
        btn("Safety Report", "safety.createReport")

        cli_row = _hbox(4)
        layout.addLayout(cli_row)
        self.cli_edit = QLineEdit(self)
        try:
            self.cli_edit.setPlaceholderText(
                'Command, e.g.: task new "Ground Sweep Alpha" priority=High team=G-2'
            )
        except Exception:
            pass
        run = QPushButton("Run", self)
        try:
            run.clicked.connect(self._run_cli)
        except Exception:
            pass
        try:
            cli_row.addWidget(self.cli_edit)
            cli_row.addWidget(run)
        except Exception:
            pass

    def _safe_dispatch(self, action: str, payload: dict):
        try:
            self._router(action, payload)
            QMessageBox.information(self, "Success", f"Action executed: {action}")
        except PermissionError as e:
            QMessageBox.warning(self, "Permission", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Action failed: {e}")

    def _run_cli(self):
        try:
            cmd = self.cli_edit.text().strip()
        except Exception:
            return
        if not cmd:
            return
        try:
            res = self._cli(cmd)
            QMessageBox.information(self, "CLI", res or "OK")
        except Exception as e:
            QMessageBox.critical(self, "CLI Error", str(e))


# ---------------------------------------------------------------------------
# Clock (Local + UTC)
# ---------------------------------------------------------------------------

class ClockDualWidget(QWidget):
    """Always shows Local + UTC times. Local tz from Settings."""

    def __init__(self, settings: SettingsManager | None = None, parent=None):
        super().__init__(parent)
        self._settings = settings or SettingsManager()
        layout = _vbox(self, margins=10, spacing=4)
        layout.addWidget(_section_header("Clock"))

        self.local_lbl = QLabel("Local: --:--:--")
        self.utc_lbl   = QLabel("UTC:   --:--:--")
        try:
            for lbl in (self.local_lbl, self.utc_lbl):
                lbl.setStyleSheet("font-size: 14px; font-family: monospace;")
        except Exception:
            pass
        layout.addWidget(self.local_lbl)
        layout.addWidget(self.utc_lbl)
        layout.addStretch()

        self._timer = QTimer(self)
        try:
            self._timer.timeout.connect(self._tick)
            self._timer.start(1000)
        except Exception:
            pass
        self._tick()

    def _tick(self):
        now_utc = datetime.now(timezone.utc)
        tzname = None
        try:
            tzname = self._settings.get("timezone", None)
        except Exception:
            pass
        if ZoneInfo and tzname:
            try:
                local_dt = now_utc.astimezone(ZoneInfo(tzname))
            except Exception:
                local_dt = datetime.now()
        else:
            local_dt = datetime.now()
        try:
            self.local_lbl.setText(
                f"Local:  {local_dt.strftime('%Y-%m-%d  %H:%M:%S')}  ({tzname or 'local'})"
            )
            self.utc_lbl.setText(
                f"UTC:    {now_utc.strftime('%Y-%m-%d  %H:%M:%S')}"
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Weather Snapshot
#
# The dashboard tile itself now lives in
# modules/intel/weather/ui/dashboard_tile.py (WeatherDashboardTile) since it
# is module-owned business UI, not a generic dashboard widget. Registered in
# ui/widgets/registry.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operational Period Countdown
# ---------------------------------------------------------------------------

class OpPeriodWidget(LiveWidget):
    """Shows the active operational period with countdown to end time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header("Operational Period"))

        # Big period number
        self._period_lbl = QLabel("OP —")
        try:
            self._period_lbl.setStyleSheet("font-size: 20px; font-weight: bold;")
        except Exception:
            pass
        layout.addWidget(self._period_lbl)

        # Status badge
        self._status_lbl = QLabel()
        try:
            self._status_lbl.setStyleSheet("font-size: 11px; color: #4caf50;")
        except Exception:
            pass
        layout.addWidget(self._status_lbl)

        layout.addWidget(_separator())

        grid = QGridLayout()
        try:
            grid.setSpacing(4)
            grid.setContentsMargins(0, 2, 0, 2)
        except Exception:
            pass

        def _row(r, label, value_attr):
            k = QLabel(label + ":")
            v = QLabel("—")
            try:
                k.setStyleSheet("color: rgba(128,128,128,0.9); font-size: 11px;")
                v.setStyleSheet("font-size: 11px;")
                grid.addWidget(k, r, 0)
                grid.addWidget(v, r, 1)
            except Exception:
                pass
            setattr(self, value_attr, v)

        _row(0, "Start",    "_start_lbl")
        _row(1, "End",      "_end_lbl")
        _row(2, "Briefing", "_brief_lbl")

        layout.addLayout(grid)
        layout.addWidget(_separator())

        # Countdown
        self._countdown_lbl = QLabel("—")
        try:
            self._countdown_lbl.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: #2196f3;"
            )
            self._countdown_lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        layout.addWidget(self._countdown_lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())

        # 1-second tick for the countdown
        self._tick_timer = QTimer(self)
        try:
            self._tick_timer.timeout.connect(self._update_countdown)
            self._tick_timer.start(1000)
        except Exception:
            pass

        self._end_dt: datetime | None = None
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            rec = dp.opperiod_getActive()
            if rec is None:
                self._period_lbl.setText("No active period")
                self._status_lbl.setText("")
                self._start_lbl.setText("—")
                self._end_lbl.setText("—")
                self._brief_lbl.setText("—")
                self._countdown_lbl.setText("—")
                self._end_dt = None
            else:
                num = rec.get("number", "—")
                name = rec.get("name") or f"Period {num}"
                self._period_lbl.setText(f"OP {num}  —  {name}")

                status = rec.get("status", "")
                color = "#4caf50" if status == "Active" else "#ff9800"
                try:
                    self._status_lbl.setStyleSheet(
                        f"font-size: 11px; font-weight: bold; color: {color};"
                    )
                except Exception:
                    pass
                self._status_lbl.setText(status)

                def _fmt(iso: str) -> str:
                    if not iso:
                        return "—"
                    return str(iso)[:16].replace("T", "  ")

                self._start_lbl.setText(_fmt(rec.get("start_time", "")))
                self._end_lbl.setText(_fmt(rec.get("end_time", "")))
                self._brief_lbl.setText(_fmt(rec.get("briefing_time", "")))

                end_raw = rec.get("end_time", "")
                self._end_dt = None
                if end_raw:
                    try:
                        from datetime import timezone as _tz
                        dt = datetime.fromisoformat(str(end_raw))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=_tz.utc)
                        self._end_dt = dt
                    except Exception:
                        pass
        except Exception:
            pass
        self._update_countdown()
        self._touch_timestamp()

    def _update_countdown(self):
        if self._end_dt is None:
            return
        try:
            now = datetime.now(timezone.utc)
            delta = self._end_dt - now
            total_secs = int(delta.total_seconds())
            if total_secs <= 0:
                self._countdown_lbl.setText("Period ended")
                try:
                    self._countdown_lbl.setStyleSheet(
                        "font-size: 16px; font-weight: bold; color: #f44336;"
                    )
                except Exception:
                    pass
            else:
                hours, remainder = divmod(total_secs, 3600)
                mins, secs = divmod(remainder, 60)
                self._countdown_lbl.setText(f"{hours:02d}:{mins:02d}:{secs:02d} remaining")
                color = "#f44336" if hours < 1 else "#2196f3"
                try:
                    self._countdown_lbl.setStyleSheet(
                        f"font-size: 16px; font-weight: bold; color: {color};"
                    )
                except Exception:
                    pass
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Resource Request Status (ICS-213RR)
# ---------------------------------------------------------------------------

_REQUEST_STATUS_COLORS = {
    "DRAFT":      "#9e9e9e",
    "SUBMITTED":  "#2196f3",
    "REVIEWED":   "#ff9800",
    "APPROVED":   "#4caf50",
    "DENIED":     "#f44336",
    "CANCELLED":  "#9e9e9e",
}

_REQUEST_PRIORITY_COLORS = {
    "CRITICAL": "#9c27b0",
    "HIGH":     "#f44336",
    "MEDIUM":   "#ff9800",
    "LOW":      "#4caf50",
}


class ResourceRequestWidget(LiveWidget):
    """Shows ICS-213RR resource request counts and open requests."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header("Resource Requests (ICS-213RR)"))

        # Status count row
        count_row = _hbox(8)
        self._count_widgets: dict[str, QWidget] = {}
        for status, color in _REQUEST_STATUS_COLORS.items():
            if status in ("DRAFT", "CANCELLED"):
                continue
            w = self._mini_count(status.title(), color)
            self._count_widgets[status] = w
            try:
                count_row.addWidget(w)
            except Exception:
                pass
        try:
            count_row.addStretch()
        except Exception:
            pass
        layout.addLayout(count_row)
        layout.addWidget(_separator())

        layout.addWidget(_section_header("Open Requests"))
        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def _mini_count(self, label: str, color: str):
        wrapper = QWidget()
        vb = QVBoxLayout(wrapper)
        try:
            vb.setSpacing(1)
            vb.setContentsMargins(4, 2, 4, 2)
        except Exception:
            pass
        num = QLabel("0")
        try:
            num.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
            num.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        cap = QLabel(label)
        try:
            cap.setStyleSheet("font-size: 9px; color: rgba(128,128,128,0.8);")
            cap.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        try:
            vb.addWidget(num)
            vb.addWidget(cap)
        except Exception:
            pass
        wrapper._num = num  # type: ignore[attr-defined]
        return wrapper

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            data = dp.requests_getSummary()
            counts = data.get("counts", {})
            for status, w in self._count_widgets.items():
                w._num.setText(str(counts.get(status, 0)))

            open_reqs = data.get("open", [])
            try:
                self._list.clear()
            except Exception:
                pass
            if not open_reqs:
                try:
                    self._list.addItem(QListWidgetItem("No open requests"))
                except Exception:
                    pass
            else:
                for req in open_reqs:
                    status = str(req.get("status", "")).upper()
                    priority = str(req.get("priority", "")).upper()
                    title = req.get("title", "Untitled")
                    text = f"[{priority}]  {title}  ({status.title()})"
                    item = QListWidgetItem(text)
                    color = _REQUEST_PRIORITY_COLORS.get(priority, "#bdbdbd")
                    try:
                        item.setForeground(QColor(color))
                        self._list.addItem(item)
                    except Exception:
                        pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# ICS-214 Activity Log Feed
# ---------------------------------------------------------------------------

class ActivityLogWidget(LiveWidget):
    """Shows recent ICS-214 activity log entries across all streams."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=6)
        layout.addWidget(_section_header("Activity Log (ICS-214)"))

        self._list = QListWidget()
        try:
            self._list.setStyleSheet("QListWidget { border: none; font-size: 11px; }")
        except Exception:
            pass
        layout.addWidget(self._list)
        layout.addWidget(self._updated_label())
        self.refresh()

    def refresh(self):
        try:
            from ui.widgets import data_providers as dp
            entries = dp.ics214_getRecentEntries(30)
            try:
                self._list.clear()
            except Exception:
                pass
            if not entries:
                try:
                    self._list.addItem(QListWidgetItem("No activity log entries"))
                except Exception:
                    pass
                self._touch_timestamp()
                return
            for e in entries:
                ts = str(e.get("timestamp_utc") or "")[:16].replace("T", " ")
                stream = e.get("_stream_name") or ""
                text = (e.get("text") or "").strip()[:80]
                critical = e.get("critical_flag", False)
                display = f"[{ts}]"
                if stream:
                    display += f"  {stream}"
                display += f"  —  {text}"
                item = QListWidgetItem(display)
                if critical:
                    try:
                        item.setForeground(QColor("#f44336"))
                    except Exception:
                        pass
                try:
                    self._list.addItem(item)
                except Exception:
                    pass
        except Exception:
            pass
        self._touch_timestamp()


# ---------------------------------------------------------------------------
# Subject / Missing Person Profile
# ---------------------------------------------------------------------------

class SubjectProfileWidget(LiveWidget):
    """Shows subject/missing person profile cards for the active incident."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = _vbox(self, margins=10, spacing=8)
        layout.addWidget(_section_header("Subject Profile"))

        self._cards_layout = QVBoxLayout()
        try:
            self._cards_layout.setSpacing(8)
            self._cards_layout.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass

        self._no_data_lbl = QLabel("No subject data on file")
        try:
            self._no_data_lbl.setStyleSheet(
                "color: rgba(128,128,128,0.7); font-size: 11px;"
            )
            self._no_data_lbl.setAlignment(Qt.AlignCenter)
        except Exception:
            pass

        layout.addLayout(self._cards_layout)
        layout.addWidget(self._no_data_lbl)
        layout.addStretch()
        layout.addWidget(self._updated_label())
        self.refresh()

    def _clear_cards(self):
        try:
            while self._cards_layout.count():
                item = self._cards_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
        except Exception:
            pass

    def _make_card(self, subject: dict) -> QWidget:
        card = QWidget()
        try:
            card.setStyleSheet(
                "QWidget { border: 1px solid rgba(128,128,128,0.25);"
                " border-radius: 4px; padding: 6px; }"
            )
        except Exception:
            pass
        vb = QVBoxLayout(card)
        try:
            vb.setSpacing(3)
            vb.setContentsMargins(8, 6, 8, 6)
        except Exception:
            pass

        name = subject.get("name", "Unknown")
        name_lbl = _bold_label(name)
        try:
            name_lbl.setStyleSheet("font-size: 13px;")
        except Exception:
            pass
        try:
            vb.addWidget(name_lbl)
        except Exception:
            pass

        details = []
        if subject.get("sex"):
            details.append(f"Sex: {subject['sex']}")
        if subject.get("dob"):
            details.append(f"DOB: {subject['dob']}")
        if details:
            d_lbl = QLabel("  ·  ".join(details))
            try:
                d_lbl.setStyleSheet("font-size: 11px; color: rgba(200,200,200,0.85);")
            except Exception:
                pass
            try:
                vb.addWidget(d_lbl)
            except Exception:
                pass

        if subject.get("lkp_place"):
            lkp_lbl = QLabel(f"LKP: {subject['lkp_place']}")
            try:
                lkp_lbl.setStyleSheet("font-size: 11px;")
                lkp_lbl.setWordWrap(True)
            except Exception:
                pass
            try:
                vb.addWidget(lkp_lbl)
            except Exception:
                pass

        if subject.get("lkp_time"):
            t_lbl = QLabel(f"Last seen: {str(subject['lkp_time'])[:16].replace('T', ' ')}")
            try:
                t_lbl.setStyleSheet("font-size: 10px; color: rgba(128,128,128,0.8);")
            except Exception:
                pass
            try:
                vb.addWidget(t_lbl)
            except Exception:
                pass

        return card

    def refresh(self):
        self._clear_cards()
        try:
            from ui.widgets import data_providers as dp
            subjects = dp.subject_getProfiles()
            if not subjects:
                try:
                    self._no_data_lbl.setText("No subject data on file")
                    self._no_data_lbl.setStyleSheet(
                        "color: rgba(128,128,128,0.7); font-size: 11px;"
                    )
                except Exception:
                    pass
            else:
                try:
                    self._no_data_lbl.setText("")
                except Exception:
                    pass
                for s in subjects:
                    card = self._make_card(s)
                    try:
                        self._cards_layout.addWidget(card)
                    except Exception:
                        pass
        except Exception:
            pass
        self._touch_timestamp()
