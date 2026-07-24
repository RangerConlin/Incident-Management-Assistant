from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QSplitter,
    QWidget,
)

from utils.styles import team_status_colors, task_status_colors, get_palette, subscribe_theme


def _settings() -> QSettings:
    # Bare QSettings() relies on QCoreApplication's organization/application
    # name being set elsewhere, which nothing in this app does — on Windows
    # that means the native registry backend silently fails to round-trip
    # values. Pass identity explicitly so persistence actually works,
    # independent of whatever (if anything) sets it app-wide.
    return QSettings("SARApp", "ProjectionDashboard")

# Use incident DB repositories for source data (no fake seed data here)
try:  # pragma: no cover - repos may be unavailable in some test contexts
    from modules.operations.data.repository import (
        fetch_team_assignment_rows,
        fetch_task_rows,
    )  # type: ignore
except Exception:  # pragma: no cover
    fetch_team_assignment_rows = None  # type: ignore[assignment]
    fetch_task_rows = None  # type: ignore[assignment]

# Alert helpers reused from team panel
try:  # pragma: no cover
    from modules.operations.panels.team_alerts import (
        AlertKind,
        TeamAlertState,
        compute_alert_kind,
        get_checkin_thresholds,
    )
except Exception:
    AlertKind = None  # type: ignore
    TeamAlertState = None  # type: ignore
    compute_alert_kind = None  # type: ignore
    def get_checkin_thresholds():  # type: ignore
        class _T:
            warning_minutes = 50
            overdue_minutes = 60
        return _T()


# ---------------------------- Utilities ----------------------------------- #

def _bold_font(base: QFont, delta_pt: int = 2, *, bold: bool = True) -> QFont:
    f = QFont(base)
    f.setPointSize(max(8, f.pointSize() + delta_pt))
    f.setBold(bold)
    return f


def _ensure_iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None or dt.utcoffset() is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat(timespec="seconds")
    return str(dt)


# ---------------------------- Team Board ---------------------------------- #

class TeamBoard(QFrame):
    """Read-only team status board for projection.

    Large fonts, tall rows, high contrast. No sorting; stable order follows
    source model (ORDER BY id in repository).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._widths_applied = False
        self.setObjectName("ProjectionTeamBoard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Team Status", self)
        title.setFont(_bold_font(title.font(), 6, bold=True))
        layout.addWidget(title)

        self.table = QTableWidget(self)
        fnt = self.table.font()
        fnt.setPointSize(max(14, fnt.pointSize()+6))
        self.table.setFont(fnt)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(self.table.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setVisible(True)
        self.table.verticalHeader().setVisible(False)
        try:
            self.table.verticalHeader().setDefaultSectionSize(42)
        except Exception:
            pass
        self.table.setShowGrid(False)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Team",
            "Leader",
            "Assignment",
            "Location",
            "Status",
            "Last Update",
        ])
        hdr_font = _bold_font(self.table.font(), 2, bold=True)
        self.table.horizontalHeader().setFont(hdr_font)
        layout.addWidget(self.table)
        try:
            hdr = self.table.horizontalHeader()
            hdr.sectionResized.connect(self._on_section_resized)
        except Exception:
            pass
        self._apply_saved_widths()
        subscribe_theme(self, lambda *_: self._recolor_all())

    def reload(self) -> None:
        rows: List[Dict[str, Any]] = []
        if fetch_team_assignment_rows:
            try:
                rows = list(fetch_team_assignment_rows())
            except Exception:
                rows = []
        self.table.setRowCount(0)
        for row in rows:
            self._append_row(row)
        self._resize_columns()
        self._recolor_all()

    def _append_row(self, data: dict[str, Any]) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        name = str(data.get("name") or "")
        leader = str(data.get("leader") or "")
        assignment = str(data.get("assignment") or "")
        location = str(data.get("location") or "")
        status = str(data.get("status") or "").strip().lower()
        last_iso = _ensure_iso(
            data.get("last_checkin_at")
            or data.get("checkin_reference_at")
            or data.get("team_status_updated")
            or data.get("last_updated")
        )
        last_disp = self._format_elapsed(last_iso)
        for c, text in enumerate([name, leader, assignment, location, status.title(), last_disp]):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if c == 5:
                try:
                    item.setTextAlignment(Qt.AlignCenter)
                except Exception:
                    pass
                item.setData(Qt.UserRole, last_iso or "")
            self.table.setItem(r, c, item)

    def _format_elapsed(self, iso_ts: Optional[str]) -> str:
        if not iso_ts:
            return ""
        try:
            dt = datetime.fromisoformat(iso_ts)
            if dt.tzinfo is None or dt.utcoffset() is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            secs = int(max(delta.total_seconds(), 0))
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        except Exception:
            return ""

    def _resize_columns(self) -> None:
        try:
            hdr = self.table.horizontalHeader()
            hdr.setStretchLastSection(True)
            for i in range(self.table.columnCount() - 1):
                hdr.setSectionResizeMode(i, hdr.ResizeMode.Interactive)
        except Exception:
            pass
        try:
            # Heuristic widths for readability
            self.table.setColumnWidth(0, 260)  # Team
            self.table.setColumnWidth(1, 220)  # Leader
            self.table.setColumnWidth(2, 320)  # Assignment
            self.table.setColumnWidth(3, 220)  # Location
            self.table.setColumnWidth(4, 140)  # Status
        except Exception:
            pass

    def _settings_group(self) -> str:
        return f"projection_dashboard/{self.objectName()}/column_widths"

    def _apply_saved_widths(self) -> None:
        if self._widths_applied:
            return
        self._widths_applied = True
        try:
            widths = _settings().value(self._settings_group(), [])
            if isinstance(widths, str):
                widths = [part for part in widths.split(",") if part]
            if not isinstance(widths, list):
                return
            for index, width in enumerate(widths):
                if index >= self.table.columnCount() - 1:
                    break
                size = int(width)
                if size > 0:
                    self.table.setColumnWidth(index, size)
        except Exception:
            pass

    def _on_section_resized(self, _logical_index: int, _old_size: int, _new_size: int) -> None:
        try:
            widths = [
                self.table.columnWidth(index)
                for index in range(self.table.columnCount() - 1)
            ]
            _settings().setValue(self._settings_group(), widths)
        except Exception:
            pass

    def _recolor_all(self) -> None:
        styles = team_status_colors()
        fg_default = get_palette()["fg"]
        try:
            status_col = 4
            for r in range(self.table.rowCount()):
                item = self.table.item(r, status_col)
                key = (item.text() if item else "").strip().lower()
                style = styles.get(key)
                for c in range(self.table.columnCount()):
                    cell = self.table.item(r, c)
                    if not cell:
                        continue
                    if style:
                        cell.setBackground(style["bg"])  # type: ignore[arg-type]
                        cell.setForeground(style["fg"])  # type: ignore[arg-type]
                    else:
                        cell.setBackground(get_palette()["bg"])  # type: ignore[arg-type]
                        cell.setForeground(fg_default)  # type: ignore[arg-type]
        except Exception:
            pass


# ---------------------------- Task Board ---------------------------------- #


class TaskBoard(QFrame):
    """Read-only task status board for projection."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._widths_applied = False
        super().__init__(parent)
        self.setObjectName("ProjectionTaskBoard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Task Status", self)
        title.setFont(_bold_font(title.font(), 6, bold=True))
        layout.addWidget(title)

        self.table = QTableWidget(self)
        fnt = self.table.font()
        fnt.setPointSize(max(14, fnt.pointSize() + 6))
        self.table.setFont(fnt)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(self.table.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setVisible(True)
        self.table.verticalHeader().setVisible(False)
        try:
            self.table.verticalHeader().setDefaultSectionSize(42)
        except Exception:
            pass
        self.table.setShowGrid(False)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Task #",
            "Description",
            "Assigned Team(s)",
            "Priority",
            "Status",
            "Due / Age",
        ])
        hdr_font = _bold_font(self.table.font(), 2, bold=True)
        self.table.horizontalHeader().setFont(hdr_font)
        layout.addWidget(self.table)
        try:
            hdr = self.table.horizontalHeader()
            hdr.sectionResized.connect(self._on_section_resized)
        except Exception:
            pass
        self._apply_saved_widths()

        subscribe_theme(self, lambda *_: self._recolor_all())

    def reload(self) -> None:
        rows: List[Dict[str, Any]] = []
        if fetch_task_rows:
            try:
                rows = list(fetch_task_rows())
            except Exception:
                rows = []
        self.table.setRowCount(0)
        for row in rows:
            self._append_row(row)
        self._resize_columns()
        self._recolor_all()

    def _append_row(self, data: dict[str, Any]) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        num = str(data.get("number") or data.get("id") or "")
        title = str(data.get("name") or "")
        assigned = ", ".join([str(x) for x in data.get("assigned_teams", [])])
        priority = str(data.get("priority") or "")
        status = str(data.get("status") or "").strip().lower().title()
        # Due / Age not available from repository; leave blank for now
        due = ""
        texts = [num, title, assigned, priority, status, due]
        for c, text in enumerate(texts):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, c, item)

    def _resize_columns(self) -> None:
        try:
            hdr = self.table.horizontalHeader()
            hdr.setStretchLastSection(True)
            for i in range(self.table.columnCount() - 1):
                hdr.setSectionResizeMode(i, hdr.ResizeMode.Interactive)
        except Exception:
            pass
        try:
            self.table.setColumnWidth(0, 120)
            self.table.setColumnWidth(1, 420)
            self.table.setColumnWidth(2, 320)
            self.table.setColumnWidth(3, 120)
            self.table.setColumnWidth(4, 160)
        except Exception:
            pass

    def _settings_group(self) -> str:
        return f"projection_dashboard/{self.objectName()}/column_widths"

    def _apply_saved_widths(self) -> None:
        if self._widths_applied:
            return
        self._widths_applied = True
        try:
            widths = _settings().value(self._settings_group(), [])
            if isinstance(widths, str):
                widths = [part for part in widths.split(",") if part]
            if not isinstance(widths, list):
                return
            for index, width in enumerate(widths):
                if index >= self.table.columnCount() - 1:
                    break
                size = int(width)
                if size > 0:
                    self.table.setColumnWidth(index, size)
        except Exception:
            pass

    def _on_section_resized(self, _logical_index: int, _old_size: int, _new_size: int) -> None:
        try:
            widths = [
                self.table.columnWidth(index)
                for index in range(self.table.columnCount() - 1)
            ]
            _settings().setValue(self._settings_group(), widths)
        except Exception:
            pass

    def _recolor_all(self) -> None:
        styles = task_status_colors()
        fg_default = get_palette()["fg"]
        try:
            status_col = 4
            for r in range(self.table.rowCount()):
                item = self.table.item(r, status_col)
                key = (item.text() if item else "").strip().lower()
                style = styles.get(key)
                for c in range(self.table.columnCount()):
                    cell = self.table.item(r, c)
                    if not cell:
                        continue
                    if style:
                        cell.setBackground(style["bg"])  # type: ignore[arg-type]
                        cell.setForeground(style["fg"])  # type: ignore[arg-type]
                    else:
                        cell.setBackground(get_palette()["bg"])  # type: ignore[arg-type]
                        cell.setForeground(fg_default)  # type: ignore[arg-type]
        except Exception:
            pass


# ---------------------------- Footer Widgets ------------------------------- #

class AlertsWidget(QFrame):
    """Compact list of current operational alerts (teams)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel("Alerts", self)
        title.setFont(_bold_font(title.font(), 2, bold=True))
        layout.addWidget(title)
        self.list = QListWidget(self)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setSelectionMode(self.list.SelectionMode.NoSelection)
        layout.addWidget(self.list)
        self._thresholds = get_checkin_thresholds()

    def reload(self) -> None:
        teams: List[Dict[str, Any]] = []
        if fetch_team_assignment_rows:
            try:
                teams = list(fetch_team_assignment_rows())
            except Exception:
                teams = []
        self.list.clear()
        entries = self._compute_alerts(teams)
        for text, severity in entries:
            item = QListWidgetItem(text)
            if severity == "critical":
                item.setForeground(get_palette()["error"])  # type: ignore[arg-type]
            elif severity == "warning":
                item.setForeground(get_palette()["warning"])  # type: ignore[arg-type]
            self.list.addItem(item)
        if self.list.count() == 0:
            self.list.addItem(QListWidgetItem("No active alerts"))

    def _compute_alerts(self, teams: List[Dict[str, Any]]):
        out: List[tuple[str, str]] = []  # (text, severity)
        for t in teams:
            status = str(t.get("status") or "").strip().lower()
            label = str(t.get("name") or t.get("sortie") or t.get("team_id") or "Team")
            emergency = bool(t.get("emergency_flag"))
            assist = bool(t.get("needs_attention") or t.get("needs_assistance_flag"))
            last_check = t.get("last_checkin_at") or t.get("checkin_reference_at") or t.get("team_status_updated")
            ref = last_check or t.get("last_updated")
            state = TeamAlertState(
                emergency_flag=emergency,
                needs_assistance_flag=assist,
                last_checkin_at=None,
                team_status=status,
                reference_time=None,
            ) if TeamAlertState else None
            try:
                # Parse ISO reference_time if available
                if state is not None and ref:
                    try:
                        dt = datetime.fromisoformat(str(ref))
                        if dt.tzinfo is None or dt.utcoffset() is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        state = TeamAlertState(
                            emergency_flag=state.emergency_flag,
                            needs_assistance_flag=state.needs_assistance_flag,
                            last_checkin_at=None,
                            team_status=state.team_status,
                            reference_time=dt,
                        )
                    except Exception:
                        pass
                kind = compute_alert_kind(state, now=datetime.now(timezone.utc), thresholds=self._thresholds) if state else None
            except Exception:
                kind = None
            if not kind or not AlertKind:
                continue
            if kind == AlertKind.EMERGENCY:
                out.append((f"Emergency — {label}", "critical"))
            elif kind == AlertKind.NEEDS_ASSISTANCE:
                out.append((f"Needs assistance — {label}", "warning"))
            elif kind == AlertKind.CHECKIN_OVERDUE:
                out.append((f"Check-in overdue — {label}", "critical"))
            elif kind == AlertKind.CHECKIN_WARNING:
                out.append((f"Check-in due soon — {label}", "warning"))
        return out[:6]


class WeatherWidget(QFrame):
    """Compact weather snippet sourced from the incident's default weather station."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel("Weather", self)
        title.setFont(_bold_font(title.font(), 2, bold=True))
        layout.addWidget(title)

        self.summary = QLabel("—", self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self._manager = None
        try:
            from utils.incident_context import get_active_incident_id
            from modules.intel.weather.services.weather_manager import get_weather_manager

            incident_id = get_active_incident_id()
            if incident_id:
                self._manager = get_weather_manager(incident_id)
                self._manager.snapshotUpdated.connect(lambda *_: self._on_data())
                self._on_data()
        except Exception:
            self._manager = None

    def _on_data(self) -> None:
        if self._manager is None:
            self.summary.setText("—")
            return
        location = self._manager.default_location()
        if location is None:
            self.summary.setText("—")
            return
        reading = self._manager.normalized_current(location.location_id)
        parts = []
        temp_f = reading.get("temperature_f")
        if temp_f is not None:
            parts.append(f"Temp {temp_f:.0f}°F")
        wind_kt = reading.get("wind_speed_kt")
        wind_dir = reading.get("wind_direction_deg")
        if wind_kt is not None:
            if wind_dir is not None:
                parts.append(f"Wind {int(wind_dir):03d}/{wind_kt:.0f} kt")
            else:
                parts.append(f"Wind {wind_kt:.0f} kt")
        vis = reading.get("visibility_sm")
        if vis is not None:
            parts.append(f"Vis {vis:.0f} sm")
        self.summary.setText("  •  ".join(parts) if parts else "—")


class IncidentInfoWidget(QFrame):
    """Compact counts for incident resources and tasks.

    Uses existing repositories for teams/tasks. Personnel/resource counts can be
    added later by integrating Check-in repositories.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel("Incident Info", self)
        title.setFont(_bold_font(title.font(), 2, bold=True))
        layout.addWidget(title)

        self.lines: List[QLabel] = []
        for _ in range(6):
            lbl = QLabel("", self)
            layout.addWidget(lbl)
            self.lines.append(lbl)
        layout.addStretch(1)

    def reload(self) -> None:
        teams = []
        tasks = []
        if fetch_team_assignment_rows:
            try:
                teams = list(fetch_team_assignment_rows())
            except Exception:
                teams = []
        if fetch_task_rows:
            try:
                tasks = list(fetch_task_rows())
            except Exception:
                tasks = []
        # Teams
        total_teams = len(teams)
        available = sum(1 for t in teams if str(t.get("status", "")).strip().lower() == "available")
        active = sum(1 for t in teams if str(t.get("status", "")).strip().lower() in {
            "enroute","arrival","returning","returning to base","aol","tol","find","in progress","assigned"
        })
        oos = sum(1 for t in teams if "out" in str(t.get("status", "")).strip().lower())
        # Tasks
        open_tasks = sum(1 for x in tasks if str(x.get("status","")) not in {"complete","completed","cancelled"})
        completed = sum(1 for x in tasks if str(x.get("status","")) in {"complete","completed"})
        # Render
        values = [
            f"Teams: {total_teams}",
            f"Active Teams: {active}",
            f"Available Teams: {available}",
            f"Out of Service: {oos}",
            f"Open Tasks: {open_tasks}",
            f"Completed Tasks: {completed}",
        ]
        for i, text in enumerate(values):
            if i < len(self.lines):
                self.lines[i].setText(text)


# ---------------------------- Main Window --------------------------------- #

class ProjectionDashboard(QWidget):
    """Projection-friendly read-only dashboard widget.

    Layout:
      - Minimal top strip with a clock (top-right)
      - Team Status board (full-width)
      - Task Status board (full-width)
      - Footer with 3 columns: Alerts, Weather, Incident Info
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectionDashboard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Top strip with clock aligned right
        top = QHBoxLayout()
        top.addStretch(1)
        self.clock = QLabel("—:— —", self)
        f = self.clock.font()
        f.setPointSize(max(36, f.pointSize()+16))
        self.clock.setFont(f)
        top.addWidget(self.clock)
        outer.addLayout(top)

        # Main content: resizable splitters
        body_splitter = QSplitter(Qt.Vertical, self)

        boards_splitter = QSplitter(Qt.Vertical, body_splitter)
        self.team_board = TeamBoard(self)
        self.task_board = TaskBoard(self)
        boards_splitter.addWidget(self.team_board)
        boards_splitter.addWidget(self.task_board)

        footer_container = QWidget(body_splitter)
        footer = QGridLayout(footer_container)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setHorizontalSpacing(12)
        footer.setVerticalSpacing(0)

        self.alerts = AlertsWidget(self)
        self.weather = WeatherWidget(self)
        self.incident_info = IncidentInfoWidget(self)

        footer.addWidget(self._wrap_in_card(self.alerts), 0, 0)
        footer.addWidget(self._wrap_in_card(self.weather), 0, 1)
        footer.addWidget(self._wrap_in_card(self.incident_info), 0, 2)

        outer.addWidget(body_splitter)
        try:
            boards_splitter.setSizes([900, 500])
            body_splitter.setSizes([1200, 260])
        except Exception:
            pass

        # Timers
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.reload_all)
        self._refresh_timer.start(15_000)  # 15s cadence for projection

        self.reload_all()

    def _wrap_in_card(self, inner: QWidget) -> QFrame:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Plain)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(inner)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return frame

    def _tick_clock(self) -> None:
        try:
            self.clock.setText(datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass

    def reload_all(self) -> None:
        try:
            self.team_board.reload()
        except Exception:
            pass
        try:
            self.task_board.reload()
        except Exception:
            pass
        try:
            self.alerts.reload()
        except Exception:
            pass
        try:
            self.incident_info.reload()
        except Exception:
            pass


# Public factory used by the main window router

def get_projection_dashboard_panel(_incident_id=None) -> QWidget:
    panel = ProjectionDashboard()
    panel.setWindowTitle("Projection Dashboard")
    return panel
