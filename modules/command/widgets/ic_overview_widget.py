"""Incident Commander overview widget (Command Dashboard)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QEvent, QObject
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from modules.command import data_access
from styles import icons as app_icons
from styles import tokens
from styles import styles as style_palette
from utils import timefmt


_LOGGER = logging.getLogger(__name__)


@dataclass
class AlertPresentation:
    label: str
    icon: QIcon
    tooltip: str


_ALERT_META: Dict[str, AlertPresentation] = {
    "CHECKIN_WARNING": AlertPresentation(
        label="Check-in warning",
        icon=QIcon(),
        tooltip="Check-in warning (>= 50 minutes since last check-in).",
    ),
    "CHECKIN_OVERDUE": AlertPresentation(
        label="Check-in overdue",
        icon=QIcon(),
        tooltip="Check-in overdue (>= 60 minutes since last check-in).",
    ),
    "NEEDS_ASSISTANCE": AlertPresentation(
        label="Needs assistance",
        icon=QIcon(),
        tooltip="Team has requested assistance.",
    ),
    "EMERGENCY": AlertPresentation(
        label="Emergency",
        icon=QIcon(),
        tooltip="Team reported an emergency condition.",
    ),
}


def _get_alert_icon(alert_type: str) -> QIcon:
    if alert_type == "CHECKIN_WARNING":
        return app_icons.icon_clock_warning()
    if alert_type == "CHECKIN_OVERDUE":
        return app_icons.icon_clock_overdue()
    if alert_type == "EMERGENCY":
        return app_icons.icon_beacon_emergency()
    return app_icons.icon_triangle_warning()


def _team_status_colors(status: str) -> tuple[str, str]:
    palette = style_palette.team_status_colors()
    key = status.strip().lower()
    aliases = {
        "returning to base": "returning",
        "returning": "returning",
        "at other location": "aol",
        "to other location": "tol",
    }
    key = aliases.get(key, key)
    entry = palette.get(key)
    if entry:
        try:
            bg = entry["bg"].color().name()
            fg = entry["fg"].color().name()
            return bg, fg
        except Exception:
            pass
    return tokens.PILL_BG_MUTED, "#ffffff"


class _Panel(QFrame):
    """A titled panel with a fixed header and an independently scrollable body.

    Panels are placed inside a vertical :class:`QSplitter` so the boundary
    between two panels in the same column can be dragged to resize them,
    while the column itself never scrolls as a whole.
    """

    def __init__(self, title: str, icon: Optional[QIcon] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DashboardPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(tokens.DEFAULT_PADDING, tokens.SMALL_PADDING, tokens.DEFAULT_PADDING, tokens.SMALL_PADDING)
        outer.setSpacing(tokens.SMALL_PADDING)

        header = QHBoxLayout()
        header.setSpacing(tokens.SMALL_PADDING)
        if icon is not None:
            icon_label = QLabel(self)
            icon_label.setPixmap(icon.pixmap(tokens.ICON_SIZE_SM, tokens.ICON_SIZE_SM))
            header.addWidget(icon_label)
        title_label = QLabel(title.upper(), self)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(max(title_font.pointSize() - 1, 7))
        title_label.setFont(title_font)
        title_label.setProperty("role", "subtle")
        header.addWidget(title_label)
        header.addStretch(1)
        self._header_extra = QHBoxLayout()
        header.addLayout(self._header_extra)
        outer.addLayout(header)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget(self._scroll)
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(tokens.SMALL_PADDING)
        self._scroll.setWidget(body)
        outer.addWidget(self._scroll, 1)

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def add_header_button(self, text: str) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("role", "accent")
        self._header_extra.addWidget(button)
        return button

    def clear(self) -> None:
        for i in reversed(range(self._body_layout.count())):
            item = self._body_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            self._body_layout.removeItem(item)

    def set_empty_state(self, message: str) -> None:
        self.clear()
        label = QLabel(message, self)
        label.setWordWrap(True)
        label.setProperty("role", "faint")
        self._body_layout.addWidget(label)
        self._body_layout.addStretch(1)


def _row_widget(parent: QWidget) -> tuple[QWidget, QHBoxLayout]:
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(tokens.SMALL_PADDING)
    return row, layout


def _status_pill(text: str, bg: str, fg: str, parent: QWidget) -> QLabel:
    pill = QLabel(text, parent)
    pill.setStyleSheet(
        "QLabel { background-color: %s; color: %s; border-radius: 6px; padding: 1px 7px; font-weight: 600; font-size: 10px; }"
        % (bg, fg)
    )
    return pill


class TeamStatusPanel(_Panel):
    """Live roster with per-team status."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Team status", app_icons.icon_card_teams(), parent)

    def update_teams(self, teams: List[dict[str, Any]]) -> None:
        self.clear()
        if not teams:
            self.set_empty_state("No teams checked in for this operational period.")
            return

        def sort_key(team: dict[str, Any]) -> tuple[int, str]:
            status = (team.get("status") or "").strip().lower()
            urgent = 0 if (team.get("emergency") or team.get("needs_assistance")) else 1
            return (urgent, status)

        for team in sorted(teams, key=sort_key):
            row, layout = _row_widget(self)
            top, top_layout = _row_widget(row)
            name = QLabel(team.get("team_name") or "Unnamed", top)
            name_font = name.font()
            name_font.setBold(True)
            name.setFont(name_font)
            top_layout.addWidget(name, 1)
            status_text = team.get("status") or "Unknown"
            bg, fg = _team_status_colors(status_text)
            top_layout.addWidget(_status_pill(status_text, bg, fg, top))

            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(top)
            meta = QLabel(
                timefmt.humanize_relative(team.get("last_checkin_ts"), default="No check-in yet"),
                row,
            )
            meta.setProperty("role", "subtle")
            col.addWidget(meta)
            layout.addLayout(col)
            self.body_layout.addWidget(row)
        self.body_layout.addStretch(1)


class TaskStatusPanel(_Panel):
    """Tasks due soonest for the active operational period."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Tasks due soon", app_icons.icon_card_tasks(), parent)

    def update_summary(self, summary: dict[str, Any]) -> None:
        self.clear()
        due = summary.get("due", [])
        if not due:
            self.set_empty_state("No tasks with an upcoming due time.")
            return
        for task in due:
            row, layout = _row_widget(self)
            col = QVBoxLayout()
            col.setSpacing(1)
            title = QLabel(f"{task.get('task_id', '')}  {task.get('title', '')}", row)
            title_font = title.font()
            title_font.setBold(True)
            title.setFont(title_font)
            col.addWidget(title)
            foot, foot_layout = _row_widget(row)
            assigned = QLabel(task.get("assigned_to") or "Unassigned", foot)
            assigned.setProperty("role", "muted")
            foot_layout.addWidget(assigned)
            foot_layout.addStretch(1)
            due_label = QLabel(timefmt.humanize_relative(task.get("due_time"), default="—"), foot)
            due_label.setProperty("role", "subtle")
            foot_layout.addWidget(due_label)
            col.addWidget(foot)
            layout.addLayout(col)
            self.body_layout.addWidget(row)
        self.body_layout.addStretch(1)


class CriticalAlertsPanel(_Panel):
    """Highest-priority alerts across teams."""

    viewAllRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Critical alerts", app_icons.icon_beacon_emergency(), parent)
        self._view_all_button = self.add_header_button("View all")
        self._view_all_button.clicked.connect(self.viewAllRequested.emit)

    def update_alerts(self, alerts: Iterable[dict[str, Any]]) -> None:
        self.clear()
        alerts = list(alerts)
        if not alerts:
            self.set_empty_state("No active alerts.")
            return
        for alert in alerts[:8]:
            alert_type = str(alert.get("type") or "")
            meta = _ALERT_META.get(alert_type)
            if not meta:
                continue
            row, layout = _row_widget(self)
            icon_label = QLabel(row)
            icon_label.setPixmap(_get_alert_icon(alert_type).pixmap(tokens.ICON_SIZE_MD, tokens.ICON_SIZE_MD))
            icon_label.setToolTip(meta.tooltip)
            layout.addWidget(icon_label)
            col = QVBoxLayout()
            col.setSpacing(1)
            label = QLabel(meta.label, row)
            label_font = label.font()
            label_font.setBold(True)
            label.setFont(label_font)
            col.addWidget(label)
            sub = QLabel(
                f"{alert.get('team_name') or 'Unknown team'} · "
                f"{timefmt.humanize_relative(alert.get('last_checkin_ts'), default='—')}",
                row,
            )
            sub.setProperty("role", "subtle")
            col.addWidget(sub)
            layout.addLayout(col, 1)
            self.body_layout.addWidget(row)
        self.body_layout.addStretch(1)


class PendingApprovalsPanel(_Panel):
    """Placeholder until incident approvals have a backing data model."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Pending approvals", None, parent)
        self.set_empty_state("Pending approvals aren't tracked yet. This panel will populate once resource, task, and comms approvals are wired up.")


class GeographicSnapshotPanel(_Panel):
    """Placeholder until a map/GIS snapshot data source is available."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Geographic snapshot", None, parent)
        self.set_empty_state("Map integration isn't available yet in this view.")


class SectionHealthPanel(_Panel):
    """Placeholder until per-section health status is tracked."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Section health", None, parent)
        self.set_empty_state("Section health isn't tracked yet.")


class OperationalPeriodReadinessPanel(_Panel):
    """Placeholder until ICS-form readiness checks are tracked."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Operational period readiness", None, parent)
        self.set_empty_state("Operational period readiness checklist isn't tracked yet.")


class RecentActivityPanel(_Panel):
    """Placeholder until an incident-wide activity feed exists."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Recent major activity", None, parent)
        self.set_empty_state("A combined activity feed isn't available yet.")


class _KpiTile(QFrame):
    """A single KPI card in the bottom strip. Colors only apply when the
    metric has a meaningful status; purely informational counts stay neutral.
    """

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("KpiTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.SMALL_PADDING, tokens.DEFAULT_PADDING, tokens.SMALL_PADDING)
        layout.setSpacing(2)
        self._label = QLabel(label.upper(), self)
        label_font = self._label.font()
        label_font.setPointSize(max(label_font.pointSize() - 2, 7))
        self._label.setFont(label_font)
        layout.addWidget(self._label)
        self._value = QLabel("—", self)
        value_font = self._value.font()
        value_font.setPointSize(value_font.pointSize() + 8)
        value_font.setBold(True)
        self._value.setFont(value_font)
        layout.addWidget(self._value)
        self._bg = tokens.CARD_BG
        self._fg = "#ffffff"
        self._value_color: Optional[str] = None
        self._label_color: Optional[str] = None
        self._neutral_bg = tokens.CARD_BG
        self._neutral_fg = "#ffffff"

    def set_neutral_colors(self, bg: str, fg: str) -> None:
        self._neutral_bg = bg
        self._neutral_fg = fg
        if self._value_color is None:
            self._apply_style(bg, fg)

    def set_value(self, value: Any) -> None:
        self._value.setText(str(value) if value is not None else "—")

    def set_status_color(self, bg: Optional[str], fg: Optional[str]) -> None:
        """Apply a solid status fill, or clear back to the neutral panel color."""
        self._value_color = fg
        if bg and fg:
            self._apply_style(bg, fg)
        else:
            self._apply_style(self._neutral_bg, self._neutral_fg)

    def _apply_style(self, bg: str, fg: str) -> None:
        self.setStyleSheet(
            "QFrame#KpiTile { background-color: %s; border-radius: %dpx; }"
            "QFrame#KpiTile QLabel { background: transparent; color: %s; }"
            % (bg, tokens.CARD_RADIUS, fg)
        )


class ICOverviewWidget(QWidget):
    """Command Dashboard: the Incident Commander's primary working view."""

    operationalPeriodChanged = Signal(int)
    requestOpenModule = Signal(str, dict)
    statusMessage = Signal(str, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ICOverviewWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._current_op = 1
        self._operational_periods: List[int] = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15_000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1_000)
        self._clock_timer.timeout.connect(self._update_clock)

        self._build_ui()
        style_palette.subscribe_theme(self, self._apply_theme)

        _rt = self._refresh_timer
        _ct = self._clock_timer

        def _stop_timers() -> None:
            try:
                _rt.stop()
            except RuntimeError:
                pass
            try:
                _ct.stop()
            except RuntimeError:
                pass

        self.destroyed.connect(_stop_timers)

        self._clock_timer.start()
        self._refresh_timer.start()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_identity_band())
        layout.addWidget(self._build_dock())
        layout.addWidget(self._build_board(), 1)
        layout.addWidget(self._build_kpi_strip())

        self._refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self._refresh_shortcut.activated.connect(self.refresh)

    def _build_identity_band(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("IdentityBand")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.SMALL_PADDING, tokens.DEFAULT_PADDING, tokens.SMALL_PADDING)
        layout.setSpacing(tokens.SECTION_SPACING)

        name_col = QVBoxLayout()
        name_col.setSpacing(tokens.TINY_PADDING)
        self._incident_name_label = QLabel("—", container)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(name_font.pointSize() + 2)
        self._incident_name_label.setFont(name_font)
        name_col.addWidget(self._incident_name_label)
        info_row = QHBoxLayout()
        info_row.setSpacing(tokens.SMALL_PADDING)
        self._incident_number_label = QLabel("#—", container)
        self._incident_number_label.setProperty("role", "subtle")
        info_row.addWidget(self._incident_number_label)
        self._status_label = QLabel("", container)
        info_row.addWidget(self._status_label)
        name_col.addLayout(info_row)
        layout.addLayout(name_col)

        layout.addWidget(self._build_field("ICP location"))
        self._icp_value = self._last_field_value
        layout.addWidget(self._build_field("Incident commander", placeholder="Not set"))
        self._ic_value = self._last_field_value
        layout.addWidget(self._build_field("Next meeting", placeholder="None scheduled"))
        self._meeting_value = self._last_field_value

        op_col = QVBoxLayout()
        op_col.setSpacing(tokens.TINY_PADDING)
        op_title = QLabel("OPERATIONAL PERIOD", container)
        op_title.setProperty("role", "faint")
        op_font = op_title.font()
        op_font.setPointSize(max(op_font.pointSize() - 2, 7))
        op_title.setFont(op_font)
        op_col.addWidget(op_title)
        op_row = QHBoxLayout()
        op_row.setSpacing(tokens.TINY_PADDING)
        self._op_prev_button = QToolButton(container)
        self._op_prev_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self._op_prev_button.setToolTip("Previous operational period")
        self._op_prev_button.clicked.connect(lambda: self._change_operational_period(-1))
        op_row.addWidget(self._op_prev_button)
        self._op_label = QLabel("OP 1", container)
        self._op_label.setMinimumWidth(50)
        self._op_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        op_row.addWidget(self._op_label)
        self._op_next_button = QToolButton(container)
        self._op_next_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self._op_next_button.setToolTip("Next operational period")
        self._op_next_button.clicked.connect(lambda: self._change_operational_period(1))
        op_row.addWidget(self._op_next_button)
        op_col.addLayout(op_row)
        layout.addLayout(op_col)

        layout.addStretch(1)

        clock_col = QVBoxLayout()
        clock_col.setSpacing(tokens.TINY_PADDING)
        clock_title = QLabel("TIME", container)
        clock_title.setProperty("role", "faint")
        clock_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_title.setFont(op_font)
        clock_col.addWidget(clock_title)
        self._clock_label = QLabel("--:--:--", container)
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_col.addWidget(self._clock_label)
        layout.addLayout(clock_col)

        return container

    def _build_field(self, title: str, placeholder: str = "—") -> QWidget:
        wrapper = QWidget(self)
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(tokens.TINY_PADDING)
        title_label = QLabel(title.upper(), wrapper)
        title_label.setProperty("role", "faint")
        title_font = title_label.font()
        title_font.setPointSize(max(title_font.pointSize() - 2, 7))
        title_label.setFont(title_font)
        col.addWidget(title_label)
        value_label = QLabel(placeholder, wrapper)
        col.addWidget(value_label)
        self._last_field_value = value_label
        return wrapper

    def _build_dock(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("DashboardDock")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.TINY_PADDING, tokens.DEFAULT_PADDING, tokens.TINY_PADDING)
        layout.setSpacing(tokens.TINY_PADDING)

        self._new_objective_button = QPushButton("New Objective", container)
        self._new_objective_button.setToolTip("Create a new incident objective")
        self._new_objective_button.clicked.connect(
            lambda: self.requestOpenModule.emit("planning.objectives.new", {})
        )
        layout.addWidget(self._new_objective_button)

        self._resource_request_button = QPushButton("Resource Request", container)
        self._resource_request_button.setToolTip("Start a new resource request")
        self._resource_request_button.clicked.connect(
            lambda: self.requestOpenModule.emit("logistics.new_request", {})
        )
        layout.addWidget(self._resource_request_button)

        self._open_iap_button = QPushButton("Open IAP", container)
        self._open_iap_button.setToolTip("Open the current Incident Action Plan")
        self._open_iap_button.clicked.connect(
            lambda: self.requestOpenModule.emit("planning.iap", {})
        )
        layout.addWidget(self._open_iap_button)

        layout.addStretch(1)

        self._pause_button = QToolButton(container)
        self._pause_button.setCheckable(True)
        self._pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self._pause_button.setToolTip("Pause automatic refresh")
        self._pause_button.clicked.connect(self._toggle_refresh)
        layout.addWidget(self._pause_button)

        self._manual_refresh_button = QToolButton(container)
        self._manual_refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._manual_refresh_button.setToolTip("Refresh now (Ctrl+R)")
        self._manual_refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self._manual_refresh_button)

        self.setTabOrder(self._new_objective_button, self._resource_request_button)
        self.setTabOrder(self._resource_request_button, self._open_iap_button)
        self.setTabOrder(self._open_iap_button, self._pause_button)

        return container

    def _build_board(self) -> QWidget:
        self._board = QSplitter(Qt.Orientation.Horizontal, self)
        self._board.setObjectName("DashboardBoard")
        self._board.setChildrenCollapsible(False)
        self._board.setHandleWidth(1)

        # Left column: team status above pending approvals.
        self._team_status_panel = TeamStatusPanel()
        self._approvals_panel = PendingApprovalsPanel()
        left = self._make_column([self._team_status_panel, self._approvals_panel])

        # Middle column: geographic snapshot above task status.
        self._map_panel = GeographicSnapshotPanel()
        self._task_status_panel = TaskStatusPanel()
        mid = self._make_column([self._map_panel, self._task_status_panel])

        # Right column: critical alerts, section health, OP readiness, activity.
        self._alerts_panel = CriticalAlertsPanel()
        self._alerts_panel.viewAllRequested.connect(
            lambda: self.requestOpenModule.emit("command.alerts", {})
        )
        self._section_health_panel = SectionHealthPanel()
        self._readiness_panel = OperationalPeriodReadinessPanel()
        self._activity_panel = RecentActivityPanel()
        right = self._make_column(
            [self._alerts_panel, self._section_health_panel, self._readiness_panel, self._activity_panel]
        )

        self._board.addWidget(left)
        self._board.addWidget(mid)
        self._board.addWidget(right)
        self._board.setStretchFactor(0, 1)
        self._board.setStretchFactor(1, 1)
        self._board.setStretchFactor(2, 1)
        return self._board

    def _make_column(self, panels: List[_Panel]) -> QSplitter:
        column = QSplitter(Qt.Orientation.Vertical)
        column.setChildrenCollapsible(False)
        column.setHandleWidth(1)
        for panel in panels:
            column.addWidget(panel)
        for index in range(len(panels)):
            column.setStretchFactor(index, 1)
        return column

    def _build_kpi_strip(self) -> QWidget:
        container = QWidget(self)
        container.setObjectName("KpiStrip")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)

        self._kpi_active_tasks = _KpiTile("Active tasks", container)
        self._kpi_teams_deployed = _KpiTile("Teams deployed", container)
        self._kpi_teams_available = _KpiTile("Teams available", container)
        self._kpi_open_requests = _KpiTile("Open resource requests", container)
        self._kpi_personnel = _KpiTile("Personnel checked in", container)
        self._kpi_leads = _KpiTile("Open leads", container)
        self._kpi_safety = _KpiTile("Safety issues", container)

        for tile in (
            self._kpi_active_tasks,
            self._kpi_teams_deployed,
            self._kpi_teams_available,
            self._kpi_open_requests,
            self._kpi_personnel,
            self._kpi_leads,
            self._kpi_safety,
        ):
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(tile)

        # Metrics with no backing data source yet stay a dash and get a
        # tooltip explaining why, rather than showing a fabricated number.
        for tile, reason in (
            (self._kpi_personnel, "Personnel check-in totals aren't tracked yet."),
            (self._kpi_leads, "Investigative leads aren't surfaced on this dashboard yet."),
            (self._kpi_safety, "Safety issue tracking isn't wired up yet."),
        ):
            tile.setToolTip(reason)

        return container

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def _apply_theme(self, theme_name: str) -> None:
        palette = style_palette.get_palette()
        fg_default = "#111111" if theme_name == "light" else "#f0f0f0"

        def _ensure_color(value: Any, fallback: QColor) -> QColor:
            if isinstance(value, QColor):
                return value
            if hasattr(value, "color"):
                candidate = value.color()
                if isinstance(candidate, QColor):
                    return candidate
            if isinstance(value, str):
                candidate = QColor(value)
                if candidate.isValid():
                    return candidate
            return fallback

        base_bg_color = _ensure_color(palette.get("bg"), QColor(tokens.CARD_BG))
        fg_color = _ensure_color(palette.get("fg"), QColor(fg_default))
        muted_color = _ensure_color(palette.get("muted"), QColor("#888888"))
        accent_color = _ensure_color(palette.get("accent"), QColor("#2f80ed"))
        success_color = _ensure_color(palette.get("success"), QColor("#4caf50"))
        warning_color = _ensure_color(palette.get("warning"), QColor("#ffb300"))
        error_color = _ensure_color(palette.get("error"), QColor("#ef5350"))
        ctrl_bg_color = _ensure_color(palette.get("ctrl_bg"), base_bg_color)
        ctrl_hover_color = _ensure_color(palette.get("ctrl_hover"), ctrl_bg_color)
        divider_color = _ensure_color(palette.get("divider"), QColor(tokens.CARD_BORDER))
        ctrl_border_color = _ensure_color(palette.get("ctrl_border"), divider_color)
        card_surface_color = _ensure_color(
            palette.get("bg_panel" if theme_name == "light" else "bg_raised"),
            base_bg_color,
        )
        panel_surface_color = _ensure_color(
            palette.get("bg_raised" if theme_name == "light" else "bg_panel"),
            base_bg_color,
        )

        fg = fg_color.name()
        accent = accent_color.name()
        ctrl_bg = ctrl_bg_color.name()
        ctrl_border = ctrl_border_color.name()
        ctrl_hover = ctrl_hover_color.name()
        subtle = QColor(muted_color).lighter(130 if theme_name == "light" else 115).name()
        faint = QColor(muted_color).lighter(160 if theme_name == "light" else 135).name()
        muted = muted_color.name()
        card_bg = card_surface_color.name()
        card_border = divider_color.name()
        panel_bg = panel_surface_color.name()

        # Muted, desaturated status fills for the KPI strip: legible without
        # glowing neon, and only ever applied when a metric has real status.
        text_on_fill = "#ffffff" if theme_name == "dark" else "#ffffff"
        kpi_ok_bg = QColor(success_color).darker(150 if theme_name == "dark" else 115).name()
        kpi_warn_bg = QColor(warning_color).darker(150 if theme_name == "dark" else 115).name()
        kpi_crit_bg = QColor(error_color).darker(150 if theme_name == "dark" else 115).name()

        stylesheet = f"""
        QWidget#ICOverviewWidget {{
            background-color: transparent;
            color: {fg};
        }}
        QWidget#ICOverviewWidget QLabel {{
            color: {fg};
        }}
        QWidget#ICOverviewWidget QLabel[role="muted"] {{
            color: {muted};
        }}
        QWidget#ICOverviewWidget QLabel[role="subtle"] {{
            color: {subtle};
        }}
        QWidget#ICOverviewWidget QLabel[role="faint"] {{
            color: {faint};
        }}
        QWidget#ICOverviewWidget QLabel[role="accent"],
        QWidget#ICOverviewWidget QToolButton[role="accent"] {{
            color: {accent};
        }}
        QWidget#IdentityBand {{
            background-color: {card_bg};
            border-bottom: 1px solid {card_border};
        }}
        QWidget#DashboardDock {{
            background-color: {panel_bg};
            border-bottom: 1px solid {card_border};
        }}
        QFrame#DashboardPanel {{
            background-color: {card_bg};
        }}
        QSplitter#DashboardBoard::handle,
        QSplitter::handle {{
            background-color: {card_border};
        }}
        QSplitter::handle:hover {{
            background-color: {accent};
        }}
        QWidget#ICOverviewWidget QPushButton {{
            background-color: {ctrl_bg};
            border: 1px solid {ctrl_border};
            color: {fg};
            padding: 5px 12px;
            border-radius: 4px;
        }}
        QWidget#ICOverviewWidget QPushButton:hover {{
            background-color: {ctrl_hover};
        }}
        QWidget#ICOverviewWidget QToolButton {{
            background-color: transparent;
        }}
        QWidget#KpiStrip {{
            background-color: {card_border};
        }}
        """
        self.setStyleSheet(stylesheet)

        for panel in (
            self._team_status_panel,
            self._approvals_panel,
            self._map_panel,
            self._task_status_panel,
            self._alerts_panel,
            self._section_health_panel,
            self._readiness_panel,
            self._activity_panel,
        ):
            panel.setStyleSheet(
                "QFrame#DashboardPanel { background-color: %s; }" % card_bg
            )

        neutral_bg = panel_bg
        for tile in (
            self._kpi_active_tasks,
            self._kpi_teams_deployed,
            self._kpi_teams_available,
            self._kpi_open_requests,
            self._kpi_personnel,
            self._kpi_leads,
            self._kpi_safety,
        ):
            tile.set_neutral_colors(neutral_bg, fg)

        self._kpi_status_colors = {
            "ok": (kpi_ok_bg, text_on_fill),
            "warn": (kpi_warn_bg, text_on_fill),
            "crit": (kpi_crit_bg, text_on_fill),
        }
        self._refresh_kpi_colors()

    def _refresh_kpi_colors(self) -> None:
        colors = getattr(self, "_kpi_status_colors", None)
        if not colors:
            return
        ok_bg, ok_fg = colors["ok"]
        warn_bg, warn_fg = colors["warn"]
        crit_bg, crit_fg = colors["crit"]
        self._kpi_teams_available.set_status_color(ok_bg, ok_fg)
        self._kpi_open_requests.set_status_color(warn_bg, warn_fg)
        self._kpi_safety.set_status_color(None, None)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            header = data_access.get_incident_header()
            periods = data_access.get_operational_periods()
            self._operational_periods = periods
            if header.get("operational_period"):
                self._current_op = int(header["operational_period"])
            if self._current_op not in self._operational_periods and self._operational_periods:
                self._current_op = self._operational_periods[0]
            teams = data_access.list_team_checkins(self._current_op)
            tasks = data_access.list_task_summary(self._current_op)
            logistics = data_access.list_logistics_requests(self._current_op)
            alerts = data_access.compute_alerts(self._current_op, now=datetime.now())

            self._update_header(header)
            self._update_op_picker()
            self._team_status_panel.update_teams(teams)
            self._task_status_panel.update_summary(tasks)
            self._alerts_panel.update_alerts(alerts)
            self._update_kpis(teams, tasks, logistics)
        except RuntimeError:
            self._refresh_timer.stop()
            self._clock_timer.stop()
        except Exception:
            _LOGGER.exception("Failed to refresh Command Dashboard")
            try:
                self.statusMessage.emit("Unable to refresh incident overview", 5000)
            except RuntimeError:
                self._refresh_timer.stop()
                self._clock_timer.stop()

    def _update_header(self, header: dict[str, Any]) -> None:
        self._incident_name_label.setText(header.get("incident_name") or "—")
        number = header.get("incident_number") or "—"
        self._incident_number_label.setText(f"#{number}")
        status = header.get("status") or "Unknown"
        bg, fg = tokens.ALERT_WARNING, "#111111"
        self._status_label.setText(status)
        self._status_label.setStyleSheet(
            "QLabel { background-color: %s; color: %s; border-radius: 6px; padding: 2px 8px; font-weight: 600; }"
            % (bg, fg)
        )
        icp = header.get("icp_location")
        self._icp_value.setText(icp or "—")

    def _update_op_picker(self) -> None:
        self._op_label.setText(f"OP {self._current_op}")
        has_prev = any(op < self._current_op for op in self._operational_periods)
        has_next = any(op > self._current_op for op in self._operational_periods)
        self._op_prev_button.setEnabled(has_prev)
        self._op_next_button.setEnabled(has_next)

    def _update_kpis(
        self,
        teams: List[dict[str, Any]],
        tasks: dict[str, Any],
        logistics: Dict[str, int],
    ) -> None:
        counts = tasks.get("counts", {})
        active = sum(
            counts.get(key, 0) for key in ("Planned", "In Progress")
        )
        self._kpi_active_tasks.set_value(active)
        self._kpi_teams_deployed.set_value(len(teams))
        available = sum(1 for t in teams if (t.get("status") or "").strip().lower() == "available")
        self._kpi_teams_available.set_value(available)
        open_requests = sum(
            logistics.get(key, 0) for key in ("Submitted", "In Progress")
        )
        self._kpi_open_requests.set_value(open_requests)
        # No data source yet for these: leave the em dash rather than fake it.
        self._kpi_personnel.set_value("—")
        self._kpi_leads.set_value("—")
        self._kpi_safety.set_value("—")

    def _update_clock(self) -> None:
        try:
            self._clock_label.setText(datetime.now().strftime("%H:%M:%S"))
        except RuntimeError:
            self._clock_timer.stop()

    def _toggle_refresh(self) -> None:
        if self._pause_button.isChecked():
            self._refresh_timer.stop()
            self._pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.statusMessage.emit("Auto-refresh paused", 3000)
        else:
            self._refresh_timer.start()
            self._pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.statusMessage.emit("Auto-refresh resumed", 3000)

    def _change_operational_period(self, delta: int) -> None:
        if not self._operational_periods:
            self._operational_periods = data_access.get_operational_periods()
        new_op = self._current_op + delta
        valid_ops = sorted(set(self._operational_periods))
        if not valid_ops:
            return
        if new_op < valid_ops[0]:
            new_op = valid_ops[0]
        if new_op > valid_ops[-1]:
            new_op = valid_ops[-1]
        if new_op == self._current_op:
            return
        self._current_op = new_op
        try:
            data_access.set_operational_period(new_op)
        except Exception:
            pass
        self.operationalPeriodChanged.emit(new_op)
        self.refresh()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    widget = ICOverviewWidget()
    widget.resize(1400, 860)
    widget.show()
    sys.exit(app.exec())
