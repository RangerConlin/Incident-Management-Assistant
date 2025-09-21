"""Incident Commander overview widget."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QEvent, QObject
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
        icon=app_icons.icon_clock_warning(),
        tooltip="Check-in warning (≥ 50 minutes since last check-in).",
    ),
    "CHECKIN_OVERDUE": AlertPresentation(
        label="Check-in overdue",
        icon=app_icons.icon_clock_overdue(),
        tooltip="Check-in overdue (≥ 60 minutes since last check-in).",
    ),
    "NEEDS_ASSISTANCE": AlertPresentation(
        label="Needs assistance",
        icon=app_icons.icon_triangle_warning(),
        tooltip="Team has requested assistance.",
    ),
    "EMERGENCY": AlertPresentation(
        label="Emergency",
        icon=app_icons.icon_beacon_emergency(),
        tooltip="Team reported an emergency condition.",
    ),
}


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


class OverviewCard(QFrame):
    """Base card with a header and content area."""

    def __init__(self, title: str, icon: Optional[QIcon] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("OverviewCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self._bg_color = tokens.CARD_BG
        self._border_color = tokens.CARD_BORDER
        self._update_card_style()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING)
        layout.setSpacing(tokens.SECTION_SPACING)

        header = QHBoxLayout()
        header.setSpacing(tokens.SMALL_PADDING)
        self._header_icon = QLabel(self)
        if icon is not None:
            self._header_icon.setPixmap(icon.pixmap(tokens.ICON_SIZE_MD, tokens.ICON_SIZE_MD))
        else:
            self._header_icon.hide()
        header.addWidget(self._header_icon)
        self._title_label = QLabel(title, self)
        title_font = self._title_label.font()
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        header.addWidget(self._title_label)
        header.addStretch(1)
        layout.addLayout(header)

        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(tokens.SMALL_PADDING)
        layout.addLayout(self._content_layout)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def clear(self) -> None:
        for i in reversed(range(self._content_layout.count())):
            item = self._content_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            self._content_layout.removeItem(item)

    def set_card_colors(self, background: str, border: str) -> None:
        if background == self._bg_color and border == self._border_color:
            return
        self._bg_color = background
        self._border_color = border
        self._update_card_style()

    def _update_card_style(self) -> None:
        self.setStyleSheet(
            """
            QFrame#OverviewCard {
                background-color: %s;
                border: 1px solid %s;
                border-radius: %dpx;
            }
            """
            % (self._bg_color, self._border_color, tokens.CARD_RADIUS)
        )


class AlertsCard(OverviewCard):
    """Alerts display card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Alerts", app_icons.icon_beacon_emergency(), parent)
        header_row = QHBoxLayout()
        header_row.setSpacing(tokens.SMALL_PADDING)
        info = QLabel("Highest priority alerts", self)
        info.setProperty("role", "muted")
        header_row.addWidget(info)
        legend_button = QToolButton(self)
        legend_button.setText("?")
        legend_button.setCursor(Qt.CursorShape.PointingHandCursor)
        legend_button.setToolTip(
            "Check-in warning triggers at 50 minutes, overdue at 60 minutes."
        )
        legend_button.setObjectName("LegendButton")
        legend_button.setProperty("role", "muted")
        header_row.addWidget(legend_button)
        header_row.addStretch(1)
        self.content_layout.addLayout(header_row)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(tokens.SMALL_PADDING)
        self.content_layout.addLayout(self._list_layout)

        footer_row = QHBoxLayout()
        footer_row.addStretch(1)
        self._view_all_button = QToolButton(self)
        self._view_all_button.setText("View all alerts")
        self._view_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_all_button.setProperty("role", "accent")
        footer_row.addWidget(self._view_all_button)
        self.content_layout.addLayout(footer_row)

    @property
    def view_all_button(self) -> QToolButton:
        return self._view_all_button

    def update_alerts(self, alerts: Iterable[dict[str, Any]]) -> None:
        for i in reversed(range(self._list_layout.count())):
            item = self._list_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            self._list_layout.removeItem(item)

        for alert in list(alerts)[:4]:
            meta = _ALERT_META.get(alert["type"])
            if not meta:
                continue
            row_widget = QWidget(self)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(tokens.SMALL_PADDING)
            icon_label = QLabel(row_widget)
            icon_label.setPixmap(meta.icon.pixmap(tokens.ICON_SIZE_MD, tokens.ICON_SIZE_MD))
            icon_label.setToolTip(meta.tooltip)
            row_layout.addWidget(icon_label)
            text_label = QLabel(f"{meta.label}", row_widget)
            text_font = text_label.font()
            text_font.setBold(True)
            text_label.setFont(text_font)
            row_layout.addWidget(text_label)
            team_label = QLabel(alert.get("team_name") or "Unknown team", row_widget)
            team_label.setProperty("role", "muted")
            row_layout.addWidget(team_label)
            last_check = timefmt.humanize_relative(alert.get("last_checkin_ts"), default="—")
            time_label = QLabel(last_check, row_widget)
            time_label.setProperty("role", "subtle")
            row_layout.addWidget(time_label)
            row_layout.addStretch(1)
            self._list_layout.addWidget(row_widget)

        if self._list_layout.count() == 0:
            empty = QLabel("No active alerts", self)
            empty.setProperty("role", "faint")
            self._list_layout.addWidget(empty)


class TeamsCard(OverviewCard):
    """Teams summary card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Teams", app_icons.icon_card_teams(), parent)
        self._kpi_labels: Dict[str, QLabel] = {}
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(tokens.SMALL_PADDING)
        for key in ("Total Teams", "Active", "Available", "Out of Service"):
            block = self._make_kpi_block(key)
            kpi_layout.addLayout(block)
        kpi_layout.addStretch(1)
        self.content_layout.addLayout(kpi_layout)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(tokens.SMALL_PADDING)
        self.content_layout.addLayout(self._list_layout)

    def _make_kpi_block(self, label: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        title = QLabel(label, self)
        title.setProperty("role", "subtle")
        layout.addWidget(title)
        value = QLabel("0", self)
        value_font = value.font()
        value_font.setPointSize(value_font.pointSize() + 2)
        value_font.setBold(True)
        value.setFont(value_font)
        layout.addWidget(value)
        self._kpi_labels[label] = value
        return layout

    def update_summary(self, teams: List[dict[str, Any]], alerts: Dict[Any, List[str]]) -> None:
        total = len(teams)
        active = sum(1 for team in teams if team.get("status", "").lower() in {"enroute", "arrival", "returning", "returning to base", "at other location", "to other location", "find"})
        available = sum(1 for team in teams if team.get("status", "").lower() == "available")
        out_of_service = sum(1 for team in teams if "out" in (team.get("status", "").lower()))
        self._kpi_labels["Total Teams"].setText(str(total))
        self._kpi_labels["Active"].setText(str(active))
        self._kpi_labels["Available"].setText(str(available))
        self._kpi_labels["Out of Service"].setText(str(out_of_service))

        for i in reversed(range(self._list_layout.count())):
            item = self._list_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            self._list_layout.removeItem(item)

        def sort_key(team: dict[str, Any]) -> tuple[int, float]:
            alert_types = alerts.get(team.get("team_id"), [])
            last_ts = team.get("last_checkin_ts")
            minutes = timefmt.minutes_since(last_ts) if last_ts else None
            # Negative priority for presence of alerts to push them to top
            alert_score = -len(alert_types)
            delay = minutes if minutes is not None else 0
            return (alert_score, -(delay))

        for team in sorted(teams, key=sort_key)[:3]:
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(tokens.SMALL_PADDING)
            name = QLabel(team.get("team_name") or "Unnamed", row)
            layout.addWidget(name)
            status_text = team.get("status") or "Unknown"
            status_label = QLabel(status_text, row)
            bg_color, fg_color = _team_status_colors(status_text)
            status_label.setStyleSheet(
                "QLabel { background-color: %s; color: %s; border-radius: 6px; padding: 1px 6px; }"
                % (bg_color, fg_color)
            )
            layout.addWidget(status_label)
            checkin = QLabel(timefmt.humanize_relative(team.get("last_checkin_ts"), default="—"), row)
            checkin.setProperty("role", "subtle")
            layout.addWidget(checkin)
            alert_container = QHBoxLayout()
            alert_container.setSpacing(2)
            for alert_type in alerts.get(team.get("team_id"), [])[:3]:
                meta = _ALERT_META.get(alert_type)
                if not meta:
                    continue
                icon = QLabel(row)
                icon.setPixmap(meta.icon.pixmap(tokens.ICON_SIZE_SM, tokens.ICON_SIZE_SM))
                icon.setToolTip(meta.tooltip)
                alert_container.addWidget(icon)
            alert_container.addStretch(1)
            layout.addLayout(alert_container)
            layout.addStretch(1)
            self._list_layout.addWidget(row)

        if self._list_layout.count() == 0 and teams:
            filler = QLabel("All teams nominal", self)
            filler.setProperty("role", "faint")
            self._list_layout.addWidget(filler)


class TasksCard(OverviewCard):
    """Tasks summary card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Tasks", app_icons.icon_card_tasks(), parent)
        self._kpi_labels: Dict[str, QLabel] = {}
        row = QHBoxLayout()
        row.setSpacing(tokens.SMALL_PADDING)
        for label in ("Draft", "Planned", "In Progress", "Completed", "Cancelled"):
            block = self._make_kpi(label)
            row.addLayout(block)
        row.addStretch(1)
        self.content_layout.addLayout(row)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(tokens.SMALL_PADDING)
        self.content_layout.addLayout(self._list_layout)

    def _make_kpi(self, label: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        title = QLabel(label, self)
        title.setProperty("role", "subtle")
        layout.addWidget(title)
        value = QLabel("0", self)
        font = value.font()
        font.setBold(True)
        value.setFont(font)
        layout.addWidget(value)
        self._kpi_labels[label] = value
        return layout

    def update_summary(self, summary: dict[str, Any]) -> None:
        counts = summary.get("counts", {})
        for key, label in self._kpi_labels.items():
            label.setText(str(counts.get(key, 0)))

        for i in reversed(range(self._list_layout.count())):
            item = self._list_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            self._list_layout.removeItem(item)

        for task in summary.get("due", [])[:3]:
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(tokens.SMALL_PADDING)
            title = QLabel(f"{task.get('task_id', '')} {task.get('title', '')}", row)
            title_font = title.font()
            title_font.setBold(True)
            title.setFont(title_font)
            layout.addWidget(title)
            due_label = QLabel(timefmt.humanize_relative(task.get("due_time"), default="—"), row)
            due_label.setProperty("role", "subtle")
            layout.addWidget(due_label)
            assigned = QLabel(task.get("assigned_to") or "Unassigned", row)
            assigned.setProperty("role", "muted")
            layout.addWidget(assigned)
            layout.addStretch(1)
            self._list_layout.addWidget(row)

        if self._list_layout.count() == 0:
            empty = QLabel("No tasks due soon", self)
            empty.setProperty("role", "faint")
            self._list_layout.addWidget(empty)


class CommsCard(OverviewCard):
    """Communications summary card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Comms", app_icons.icon_card_comms(), parent)
        self._active_label = QLabel("0", self)
        self._remarks_label = QLabel("0", self)
        self._last_updated_label = QLabel("—", self)

        top = QHBoxLayout()
        top.setSpacing(tokens.SMALL_PADDING)
        top.addLayout(self._build_metric_block("Active Channels", self._active_label))
        top.addLayout(self._build_metric_block("With Remarks", self._remarks_label))
        top.addLayout(self._build_metric_block("Last Updated", self._last_updated_label, is_value=False))
        top.addStretch(1)
        self.content_layout.addLayout(top)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(tokens.SMALL_PADDING)
        self.content_layout.addLayout(self._list_layout)

    def _build_metric_block(self, title: str, value_label: QLabel, *, is_value: bool = True) -> QVBoxLayout:
        layout = QVBoxLayout()
        title_label = QLabel(title, self)
        title_label.setProperty("role", "subtle")
        layout.addWidget(title_label)
        if is_value:
            font = value_label.font()
            font.setBold(True)
            value_label.setFont(font)
        layout.addWidget(value_label)
        return layout

    def update_channels(self, channels: List[dict[str, Any]]) -> None:
        self._active_label.setText(str(len(channels)))
        remarks_count = sum(1 for ch in channels if (ch.get("remarks") or "").strip())
        self._remarks_label.setText(str(remarks_count))
        last = max((ch.get("last_updated") for ch in channels if ch.get("last_updated")), default=None)
        self._last_updated_label.setText(timefmt.humanize_relative(last, default="—"))

        for i in reversed(range(self._list_layout.count())):
            item = self._list_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            self._list_layout.removeItem(item)

        for channel in channels[:3]:
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(tokens.SMALL_PADDING)
            name = QLabel(channel.get("name") or "", row)
            name_font = name.font()
            name_font.setBold(True)
            name.setFont(name_font)
            layout.addWidget(name)
            function = QLabel(channel.get("function") or "", row)
            function.setProperty("role", "muted")
            layout.addWidget(function)
            mode = QLabel(channel.get("mode") or "", row)
            mode.setProperty("role", "subtle")
            layout.addWidget(mode)
            layout.addStretch(1)
            self._list_layout.addWidget(row)

        if self._list_layout.count() == 0:
            empty = QLabel("No communications channels configured", self)
            empty.setProperty("role", "faint")
            self._list_layout.addWidget(empty)


class LogisticsCard(OverviewCard):
    """Logistics summary card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Logistics", app_icons.icon_card_logistics(), parent)
        self._counts: Dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setSpacing(tokens.SMALL_PADDING)
        statuses = ["Submitted", "In Progress", "Ordered", "Fulfilled"]
        for index, status in enumerate(statuses):
            label = QLabel(status, self)
            label.setProperty("role", "subtle")
            value = QLabel("0", self)
            font = value.font()
            font.setBold(True)
            value.setFont(font)
            grid.addWidget(label, index, 0)
            grid.addWidget(value, index, 1)
            self._counts[status] = value
        self.content_layout.addLayout(grid)

        self._others_label = QLabel("", self)
        self._others_label.setProperty("role", "muted")
        self.content_layout.addWidget(self._others_label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._open_button = QToolButton(self)
        self._open_button.setText("Open Logistics Board")
        self._open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_button.setProperty("role", "accent")
        footer.addWidget(self._open_button)
        self.content_layout.addLayout(footer)

    @property
    def open_button(self) -> QToolButton:
        return self._open_button

    def update_counts(self, counts: Dict[str, int]) -> None:
        others: Dict[str, int] = {}
        for key in list(counts.keys()):
            if key in self._counts:
                self._counts[key].setText(str(counts[key]))
            else:
                others[key] = counts[key]
        if others:
            detail = ", ".join(f"{k}: {v}" for k, v in sorted(others.items()))
            self._others_label.setText(f"Other statuses: {detail}")
            self._others_label.setToolTip(detail)
        else:
            self._others_label.setText("")
            self._others_label.setToolTip("")


class ICOverviewWidget(QWidget):
    """Compact overview widget for the Incident Commander."""

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
        self._clock_timer.start()

        self._build_ui()
        style_palette.subscribe_theme(self, self._apply_theme)
        self._refresh_timer.start()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING, tokens.DEFAULT_PADDING)
        layout.setSpacing(tokens.SECTION_SPACING)

        header = self._build_header()
        layout.addWidget(header)

        self._alerts_card = AlertsCard(self)
        layout.addWidget(self._alerts_card)

        self._cards_container = QWidget(self)
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(tokens.SECTION_SPACING)
        layout.addWidget(self._cards_container)

        self._teams_card = TeamsCard(self._cards_container)
        self._tasks_card = TasksCard(self._cards_container)
        self._comms_card = CommsCard(self._cards_container)
        self._logistics_card = LogisticsCard(self._cards_container)
        self._summary_cards = [
            self._teams_card,
            self._tasks_card,
            self._comms_card,
            self._logistics_card,
        ]
        self._reflow_cards()

        # Hook up actions
        self._alerts_card.view_all_button.clicked.connect(
            lambda: self.requestOpenModule.emit("command.alerts", {})
        )
        self._logistics_card.open_button.clicked.connect(
            lambda: self.requestOpenModule.emit("logistics.requests", {})
        )

        self._card_routes: Dict[QWidget, tuple[str, dict[str, Any]]] = {
            self._teams_card: ("teams.overview", {}),
            self._tasks_card: ("tasks.board", {}),
            self._comms_card: ("comms.plan", {}),
        }
        for card in self._card_routes:
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.installEventFilter(self)

        self._refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self._refresh_shortcut.activated.connect(self.refresh)

        self.setTabOrder(self._op_prev_button, self._op_next_button)
        self.setTabOrder(self._op_next_button, self._new_objective_button)
        self.setTabOrder(self._new_objective_button, self._resource_request_button)
        self.setTabOrder(self._resource_request_button, self._open_iap_button)
        self.setTabOrder(self._open_iap_button, self._pause_button)

    def _apply_theme(self, theme_name: str) -> None:
        palette = style_palette.get_palette()
        fg = palette["fg"].name()
        muted_color = palette["muted"]
        accent = palette["accent"].name()
        ctrl_bg = palette.get("ctrl_bg", palette["bg"]).name()
        ctrl_border = palette.get("ctrl_border", palette["divider"]).name()
        ctrl_hover = palette.get("ctrl_hover", palette["bg"]).name()
        divider_value = palette.get("divider", tokens.CARD_BORDER)
        card_surface = palette.get("bg_panel" if theme_name == "light" else "bg_raised", palette["bg"])
        card_border_value = divider_value
        subtle = muted_color.lighter(130 if theme_name == "light" else 115).name()
        faint = muted_color.lighter(160 if theme_name == "light" else 135).name()
        muted = muted_color.name()

        card_bg = card_surface.name() if hasattr(card_surface, "name") else str(card_surface)
        card_border = (
            card_border_value.name() if hasattr(card_border_value, "name") else str(card_border_value)
        )

        stylesheet = f"""
        QWidget#ICOverviewWidget {{
            background-color: transparent;
            color: {fg};
        }}
        QWidget#ICOverviewWidget QLabel {{
            color: {fg};
        }}
        QWidget#ICOverviewWidget QLabel[role="muted"],
        QWidget#ICOverviewWidget QToolButton[role="muted"],
        QWidget#ICOverviewWidget QPushButton[role="muted"] {{
            color: {muted};
        }}
        QWidget#ICOverviewWidget QLabel[role="subtle"] {{
            color: {subtle};
        }}
        QWidget#ICOverviewWidget QLabel[role="faint"] {{
            color: {faint};
        }}
        QWidget#ICOverviewWidget QLabel[role="accent"],
        QWidget#ICOverviewWidget QToolButton[role="accent"],
        QWidget#ICOverviewWidget QPushButton[role="accent"] {{
            color: {accent};
        }}
        QWidget#ICOverviewWidget QFrame#OverviewCard {{
            background-color: {card_bg};
            border: 1px solid {card_border};
            border-radius: {tokens.CARD_RADIUS}px;
        }}
        QWidget#ICOverviewWidget QPushButton {{
            background-color: {card_bg if theme_name == 'dark' else ctrl_bg};
            border: 1px solid {ctrl_border};
            color: {fg};
            padding: 4px 10px;
        }}
        QWidget#ICOverviewWidget QPushButton:hover {{
            background-color: {ctrl_hover};
        }}
        QWidget#ICOverviewWidget QToolButton {{
            background-color: transparent;
        }}
        QWidget#ICOverviewWidget QToolButton#LegendButton {{
            border: 1px solid {card_border};
            border-radius: 8px;
            padding: 1px 4px;
        }}
        QWidget#ICOverviewWidget QToolButton#LegendButton:hover {{
            background-color: {ctrl_hover};
        }}
        """

        self.setStyleSheet(stylesheet)

        for card in [self._alerts_card, *self._summary_cards]:
            card.set_card_colors(card_bg, card_border)

    def _build_header(self) -> QWidget:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(tokens.SECTION_SPACING)

        # Left cluster
        left = QVBoxLayout()
        left.setSpacing(tokens.TINY_PADDING)
        self._incident_name_label = QLabel("—", container)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(name_font.pointSize() + 2)
        self._incident_name_label.setFont(name_font)
        left.addWidget(self._incident_name_label)
        info_row = QHBoxLayout()
        info_row.setSpacing(tokens.SMALL_PADDING)
        self._incident_number_label = QLabel("#—", container)
        self._incident_number_label.setProperty("role", "subtle")
        info_row.addWidget(self._incident_number_label)
        self._status_label = QLabel("", container)
        self._status_label.setStyleSheet(
            "QLabel { background-color: %s; color: #111111; border-radius: 6px; padding: 2px 6px; }"
            % tokens.ALERT_WARNING
        )
        info_row.addWidget(self._status_label)
        left.addLayout(info_row)
        layout.addLayout(left)

        # Middle cluster - operational period picker
        middle = QHBoxLayout()
        middle.setSpacing(tokens.SMALL_PADDING)
        self._op_prev_button = QToolButton(container)
        self._op_prev_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self._op_prev_button.setToolTip("Previous operational period")
        self._op_prev_button.clicked.connect(lambda: self._change_operational_period(-1))
        middle.addWidget(self._op_prev_button)
        self._op_label = QLabel("OP 1", container)
        self._op_label.setMinimumWidth(60)
        self._op_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        middle.addWidget(self._op_label)
        self._op_next_button = QToolButton(container)
        self._op_next_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self._op_next_button.setToolTip("Next operational period")
        self._op_next_button.clicked.connect(lambda: self._change_operational_period(1))
        middle.addWidget(self._op_next_button)
        middle_widget = QWidget(container)
        middle_widget.setLayout(middle)
        layout.addWidget(middle_widget)

        # Right cluster
        right = QHBoxLayout()
        right.setSpacing(tokens.SMALL_PADDING)
        self._clock_label = QLabel("--:--:--", container)
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clock_label.setFixedWidth(80)
        self._clock_label.setProperty("role", "muted")
        right.addWidget(self._clock_label)

        self._new_objective_button = QPushButton("New Objective", container)
        self._new_objective_button.setToolTip("Create a new incident objective")
        self._new_objective_button.clicked.connect(
            lambda: self.requestOpenModule.emit("planning.objectives.new", {})
        )
        right.addWidget(self._new_objective_button)

        self._resource_request_button = QPushButton("Resource Request", container)
        self._resource_request_button.setToolTip("Start a new resource request")
        self._resource_request_button.clicked.connect(
            lambda: self.requestOpenModule.emit("logistics.new_request", {})
        )
        right.addWidget(self._resource_request_button)

        self._open_iap_button = QPushButton("Open IAP", container)
        self._open_iap_button.setToolTip("Open the current Incident Action Plan")
        self._open_iap_button.clicked.connect(
            lambda: self.requestOpenModule.emit("planning.iap", {})
        )
        right.addWidget(self._open_iap_button)

        self._pause_button = QToolButton(container)
        self._pause_button.setCheckable(True)
        self._pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self._pause_button.setToolTip("Pause automatic refresh")
        self._pause_button.clicked.connect(self._toggle_refresh)
        right.addWidget(self._pause_button)

        self._manual_refresh_button = QToolButton(container)
        self._manual_refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._manual_refresh_button.setToolTip("Refresh now (Ctrl+R)")
        self._manual_refresh_button.clicked.connect(self.refresh)
        right.addWidget(self._manual_refresh_button)

        layout.addLayout(right)
        layout.addStretch(1)
        return container

    # --- UI updates -----------------------------------------------------

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
            comms = data_access.list_comms_channels(self._current_op)
            logistics = data_access.list_logistics_requests(self._current_op)
            alerts = data_access.compute_alerts(self._current_op, now=datetime.now())
        except Exception as exc:
            _LOGGER.exception("Failed to refresh IC overview")
            self.statusMessage.emit("Unable to refresh incident overview", 5000)
            return

        self._update_header(header)
        self._update_op_picker()
        self._alerts_card.update_alerts(alerts)
        alert_map: Dict[Any, List[str]] = {}
        for alert in alerts:
            alert_map.setdefault(alert.get("team_id"), []).append(alert["type"])
        self._teams_card.update_summary(teams, alert_map)
        self._tasks_card.update_summary(tasks)
        self._comms_card.update_channels(comms)
        self._logistics_card.update_counts(logistics)

    def _update_header(self, header: dict[str, Any]) -> None:
        self._incident_name_label.setText(header.get("incident_name") or "—")
        number = header.get("incident_number") or "—"
        self._incident_number_label.setText(f"#{number}")
        status = header.get("status") or "Unknown"
        self._status_label.setText(status)

    def _update_op_picker(self) -> None:
        self._op_label.setText(f"OP {self._current_op}")
        has_prev = any(op < self._current_op for op in self._operational_periods)
        has_next = any(op > self._current_op for op in self._operational_periods)
        self._op_prev_button.setEnabled(has_prev)
        self._op_next_button.setEnabled(has_next)

    def _update_clock(self) -> None:
        self._clock_label.setText(datetime.now().strftime("%H:%M:%S"))

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

    def _reflow_cards(self) -> None:
        width = self.width() or self.sizeHint().width()
        columns = 1 if width <= 520 else 2
        for card in self._summary_cards:
            self._cards_layout.removeWidget(card)
        for index, card in enumerate(self._summary_cards):
            row = index // columns
            col = index % columns
            self._cards_layout.addWidget(card, row, col)
        for col in range(2):
            self._cards_layout.setColumnStretch(col, 1 if col < columns else 0)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reflow_cards()

    def _emit_request(self, module: str, payload: dict[str, Any]) -> None:
        self.requestOpenModule.emit(module, payload)

    def eventFilter(self, obj: QObject, event: QEvent):  # type: ignore[override]
        routes = getattr(self, "_card_routes", {})
        if obj in routes:
            if event.type() == QEvent.Type.MouseButtonRelease and hasattr(event, "button"):
                if event.button() == Qt.MouseButton.LeftButton:
                    module, payload = routes[obj]
                    self._emit_request(module, payload)
                    return True
        return super().eventFilter(obj, event)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    widget = ICOverviewWidget()
    widget.resize(900, 600)
    widget.show()
    sys.exit(app.exec())
