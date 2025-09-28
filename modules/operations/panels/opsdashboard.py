"""
Operations — Dashboard compact widget (PySide6, Widgets-only).

Menu wiring instructions (add under Operations menu):

- Goal: Add a new QAction labeled "Operations Dashboard" under the
  Operations menu in place of the legacy "Assignments Dashboard".
- Behavior: When triggered, create and show an `OpsGlanceWidget` instance
  (reusing any existing instance if you manage singletons/docks).

Example integration sketch (adapt to your app's menu framework):

    from modules.operations.panels.opsdashboard import make_ops_glance_widget

    class MainWindow(QMainWindow):
        def __init__(self, ...):
            super().__init__(...)
            ops_menu = self.menuBar().findChild(QMenu, 'menuOperations') or self.menuBar().addMenu('Operations')

            # Locate where "Assignments Dashboard" is added and insert this right below it.
            self.action_ops_glance = QAction('Operations Dashboard', self)
            self.action_ops_glance.triggered.connect(self.show_ops_glance)
            ops_menu.addAction(self.action_ops_glance)  # Place near Assignments Dashboard

        @Slot()
        def show_ops_glance(self):
            # Typical patterns: show in a dock, a tab, or as a standalone dialog.
            # Example: show in a dock.
            if not hasattr(self, '_ops_glance_widget') or self._ops_glance_widget is None:
                self._ops_glance_widget = make_ops_glance_widget(self)
            self._ops_glance_widget.setIncidentOverlayVisible(False)
            self._ops_glance_widget.show()
            self._ops_glance_widget.raise_()
            self._ops_glance_widget.activateWindow()

Notes:
- Keep this widget self-contained (no backend calls). Wire it to your app state
  or repositories as needed elsewhere.
- For CI/offscreen contexts, set `QT_QPA_PLATFORM=offscreen` before running UI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QSize, Signal, Slot
from PySide6.QtGui import QAction, QColor, QContextMenuEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
    QStackedLayout,
)


class KpiCard(QFrame):
    """Simple rounded KPI pill with a big number and small label."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self._value_label = QLabel("0", self)
        self._caption_label = QLabel(label, self)

        self._value_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self._caption_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self._value_label.setProperty("kpiValue", True)
        self._caption_label.setProperty("kpiCaption", True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        lay.addWidget(self._value_label)
        lay.addWidget(self._caption_label)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_value(self, value: int | str) -> None:
        self._value_label.setText(str(value))


class StatusBadge(QFrame):
    """Comms channel badge: status dot + name + role."""

    COLOR_MAP = {
        "OK": "#2e7d32",  # green
        "DEGRADED": "#f9a825",  # amber
        "DOWN": "#c62828",  # red
    }

    def __init__(self, name: str, role: str, status: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommsBadge")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        dot = QFrame(self)
        dot.setObjectName("StatusDot")
        dot.setFixedSize(10, 10)
        dot.setProperty("statusColor", self.COLOR_MAP.get(status.upper(), "#9e9e9e"))

        name_lbl = QLabel(name, self)
        name_lbl.setObjectName("CommsName")
        role_lbl = QLabel(role, self)
        role_lbl.setObjectName("CommsRole")

        layout.addWidget(dot)
        layout.addWidget(name_lbl)
        layout.addWidget(role_lbl)
        layout.addStretch(1)


class OpsGlanceWidget(QWidget):
    """Compact at-a-glance Operations dashboard widget.

    Exposes signals for high-level actions and updates via simple setters.
    No backend calls are performed here. All data is pushed in via update_*
    methods by the hosting application.
    """

    # Signals
    openTaskRequested = Signal(str)
    reassignRequested = Signal(object, object)  # (task_id_or_none, team_name_or_none)
    markCompleteRequested = Signal(str)
    print204Requested = Signal()
    export214Requested = Signal()
    openFullDashboardRequested = Signal()
    view214LogRequested = Signal()
    acknowledgeAlertsRequested = Signal()
    refreshRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("OpsGlanceWidget")
        self._refresh_timer: Optional[QTimer] = None

        # Stacked layout for overlay
        self._stack = QStackedLayout(self)

        # Page 0: Main content
        self._content = QWidget(self)
        self._stack.addWidget(self._content)

        # Page 1: Overlay when no active incident
        self._overlay = QWidget(self)
        self._stack.addWidget(self._overlay)
        self._build_overlay()

        # Build main UI
        self._build_ui()

        # Default stylesheet (light)
        self._apply_styles()

        # Default to showing overlay off (assume active incident until told otherwise)
        self.setIncidentOverlayVisible(False)

    # ------------------------- UI Construction -------------------------
    def _build_overlay(self) -> None:
        lay = QVBoxLayout(self._overlay)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        container = QWidget(self._overlay)
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.addStretch(1)
        msg = QLabel("No active incident — select or create one.", container)
        msg.setAlignment(Qt.AlignCenter)
        msg.setObjectName("OverlayMessage")
        c_lay.addWidget(msg)
        c_lay.addStretch(1)
        lay.addWidget(container)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self._content)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 1. Header row
        header_row = QHBoxLayout()
        title = QLabel("Operations — Dashboard", self._content)
        title.setObjectName("HeaderTitle")
        header_row.addWidget(title, 1)
        self._context_label = QLabel("OP: —    Now: —    Role: —", self._content)
        self._context_label.setObjectName("HeaderContext")
        self._context_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_row.addWidget(self._context_label, 0)
        root.addLayout(header_row)

        # 2. KPI row (six pills)
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(8)
        kpi_grid.setVerticalSpacing(8)
        self._kpi_cards: Dict[str, KpiCard] = {
            "active_tasks": KpiCard("Active Tasks", self._content),
            "due_2h": KpiCard("Due ≤ 2h", self._content),
            "teams_assigned": KpiCard("Teams Assigned", self._content),
            "teams_available": KpiCard("Teams Available", self._content),
            "blocking_issues": KpiCard("Blocking Issues", self._content),
            "new_debriefs": KpiCard("New Debriefs", self._content),
        }
        order = [
            "active_tasks",
            "due_2h",
            "teams_assigned",
            "teams_available",
            "blocking_issues",
            "new_debriefs",
        ]
        for idx, key in enumerate(order):
            kpi_grid.addWidget(self._kpi_cards[key], 0, idx)
        root.addLayout(kpi_grid)

        # 3. Alerts section
        alerts_row = QHBoxLayout()
        alerts_label = QLabel("Alerts (last 30 min)", self._content)
        alerts_label.setObjectName("AlertsLabel")
        alerts_row.addWidget(alerts_label)
        alerts_row.addStretch(1)
        self._alerts_log_btn = QPushButton("214 Log ▸", self._content)
        self._alerts_ack_btn = QPushButton("Acknowledge", self._content)
        alerts_row.addWidget(self._alerts_log_btn)
        alerts_row.addWidget(self._alerts_ack_btn)
        root.addLayout(alerts_row)

        self._alerts_list = QListWidget(self._content)
        self._alerts_list.setObjectName("AlertsList")
        self._alerts_list.setMaximumHeight(150)
        root.addWidget(self._alerts_list)

        # 4. Two-column middle section
        mid_row = QHBoxLayout()

        # Left: Top Tasks
        left_col = QVBoxLayout()
        top_tasks_label = QLabel("Top Tasks", self._content)
        top_tasks_label.setObjectName("SubsectionLabel")
        left_col.addWidget(top_tasks_label)
        self._tasks_list = QListWidget(self._content)
        self._tasks_list.setObjectName("TasksList")
        self._tasks_list.setMaximumHeight(180)
        self._tasks_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tasks_list.itemDoubleClicked.connect(self._on_task_double_clicked)
        self._tasks_list.customContextMenuRequested.connect(self._on_tasks_context_menu)
        left_col.addWidget(self._tasks_list)
        task_btn_row = QHBoxLayout()
        self._btn_open_task = QPushButton("Open Task", self._content)
        self._btn_reassign = QPushButton("Reassign", self._content)
        self._btn_mark_done = QPushButton("Mark Complete", self._content)
        for b in (self._btn_open_task, self._btn_reassign, self._btn_mark_done):
            task_btn_row.addWidget(b)
        task_btn_row.addStretch(1)
        left_col.addLayout(task_btn_row)
        mid_row.addLayout(left_col, 1)

        # Right: Team Snapshot
        right_col = QVBoxLayout()
        team_snap_label = QLabel("Team Snapshot", self._content)
        team_snap_label.setObjectName("SubsectionLabel")
        right_col.addWidget(team_snap_label)
        self._teams_list = QListWidget(self._content)
        self._teams_list.setObjectName("TeamsList")
        self._teams_list.setMaximumHeight(200)
        right_col.addWidget(self._teams_list)
        mid_row.addLayout(right_col, 1)

        root.addLayout(mid_row)

        # 5. Comms snapshot row
        comms_row = QHBoxLayout()
        comms_label = QLabel("Comms Snapshot", self._content)
        comms_label.setObjectName("SubsectionLabel")
        comms_row.addWidget(comms_label)
        comms_row.addStretch(1)
        root.addLayout(comms_row)

        self._comms_wrap = QHBoxLayout()
        self._comms_wrap.setSpacing(8)
        root.addLayout(self._comms_wrap)

        # 6. Bottom actions row
        bottom_row = QHBoxLayout()
        self._btn_new_task = QPushButton("New Task", self._content)
        self._btn_reassign_team = QPushButton("Reassign Team", self._content)
        self._btn_print_204 = QPushButton("Print 204", self._content)
        self._btn_export_214 = QPushButton("Export 214", self._content)
        self._btn_open_full = QPushButton("Open Full Dashboard", self._content)
        for b in (
            self._btn_new_task,
            self._btn_reassign_team,
            self._btn_print_204,
            self._btn_export_214,
            self._btn_open_full,
        ):
            bottom_row.addWidget(b)
        bottom_row.addStretch(1)
        root.addLayout(bottom_row)

        # Wire buttons
        self._alerts_log_btn.clicked.connect(self.view214LogRequested)
        self._alerts_ack_btn.clicked.connect(self.acknowledgeAlertsRequested)
        self._btn_open_task.clicked.connect(self._emit_open_selected_task)
        self._btn_reassign.clicked.connect(self._emit_reassign_selected_task)
        self._btn_mark_done.clicked.connect(self._emit_mark_complete_selected_task)
        self._btn_print_204.clicked.connect(self.print204Requested)
        self._btn_export_214.clicked.connect(self.export214Requested)
        self._btn_open_full.clicked.connect(self.openFullDashboardRequested)
        self._btn_reassign_team.clicked.connect(self._emit_reassign_selected_team)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            /* Header */
            #HeaderTitle { font-size: 18px; font-weight: 600; }
            #HeaderContext { color: #555; }

            /* KPI Cards */
            #KpiCard {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
            QLabel[kpiValue="true"] { font-size: 22px; font-weight: 700; }
            QLabel[kpiCaption="true"] { font-size: 11px; color: #666; }

            /* Lists */
            #AlertsList, #TasksList, #TeamsList {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            #AlertsLabel, #SubsectionLabel, #OverlayMessage { font-weight: 600; }

            /* Comms badges */
            #CommsBadge {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
            #CommsBadge > #StatusDot {
                background: #9e9e9e;
                border-radius: 5px;
            }
            /* dynamic color via palette since Qt stylesheets don't read properties for colors */
            """
        )

    # ------------------------- Slots / API -------------------------
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self._context_label.setText(f"OP: {op_period}    Now: {now_text}    Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict[str, Any]) -> None:
        mapping = {
            "active_tasks": 0,
            "due_2h": 0,
            "teams_assigned": 0,
            "teams_available": 0,
            "blocking_issues": 0,
            "new_debriefs": 0,
        }
        mapping.update({k: kpis.get(k, v) for k, v in mapping.items()})
        for key, card in self._kpi_cards.items():
            card.set_value(mapping.get(key, 0))

    @Slot(list)
    def update_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        self._alerts_list.clear()
        for alert in alerts[:8]:
            msg = alert.get("message") or alert.get("text") or "(no message)"
            ts = alert.get("ts") or alert.get("time") or ""
            item = QListWidgetItem(f"{ts}  —  {msg}")
            item.setData(Qt.UserRole, alert.get("id"))
            self._alerts_list.addItem(item)

    @Slot(list)
    def update_top_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        self._tasks_list.clear()
        for t in tasks[:5]:
            title = t.get("title") or t.get("name") or "(untitled)"
            due = t.get("due") or ""
            who = t.get("assignee") or t.get("assigned_to") or ""
            prio = t.get("priority")
            status = t.get("status") or ""
            pieces = []
            if prio not in (None, ""):
                try:
                    pieces.append(f"[P{int(prio)}]")
                except Exception:
                    pieces.append(f"[{prio}]")
            pieces.append(title)
            if who:
                pieces.append(str(who))
            if due:
                pieces.append(str(due))
            if status:
                pieces.append(str(status))
            text = "  —  ".join(pieces)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, str(t.get("id")))
            self._tasks_list.addItem(item)

    @Slot(list)
    def update_team_snapshot(self, teams: List[Dict[str, Any]]) -> None:
        self._teams_list.clear()
        for tm in teams[:6]:
            name = tm.get("name") or "(team)"
            status = tm.get("status") or ""
            assigned = tm.get("assigned") or tm.get("task") or ""
            last = tm.get("last_checkin_at") or tm.get("last_updated") or ""
            leader = tm.get("leader") or tm.get("leader_name") or ""
            bits = [name]
            meta = []
            if status:
                meta.append(str(status))
            if assigned:
                meta.append(f"Task: {assigned}")
            if leader:
                meta.append(f"Lead: {leader}")
            if last:
                meta.append(f"Last: {last}")
            if meta:
                bits.append("  |  ".join(meta))
            text = "  —  ".join(bits)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, name)
            self._teams_list.addItem(item)

    @Slot(list)
    def update_comms_snapshot(self, channels: List[Dict[str, Any]]) -> None:
        # Clear existing badges
        while self._comms_wrap.count():
            item = self._comms_wrap.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        max_show = 3
        show = channels[:max_show]
        more = max(0, len(channels) - len(show))

        for ch in show:
            name = ch.get("name") or "(ch)"
            role = ch.get("role") or ""
            status = (ch.get("status") or "").upper() or "OK"
            badge = StatusBadge(name, role, status, self)
            # Apply the color to the dot by palette (Qt stylesheets can't read dynamic properties for color values)
            for child in badge.findChildren(QFrame, "StatusDot"):
                pal = child.palette()
                color = QColor(StatusBadge.COLOR_MAP.get(status, "#9e9e9e"))
                pal.setColor(child.backgroundRole(), color)
                child.setStyleSheet(f"background: {color.name()}; border-radius: 5px;")
            self._comms_wrap.addWidget(badge)

        if more > 0:
            more_badge = QFrame(self)
            more_badge.setObjectName("CommsBadge")
            lay = QHBoxLayout(more_badge)
            lay.setContentsMargins(8, 4, 8, 4)
            lay.setSpacing(6)
            lay.addWidget(QLabel(f"+{more} more", more_badge))
            self._comms_wrap.addWidget(more_badge)

        self._comms_wrap.addStretch(1)

    @Slot(bool)
    def setIncidentOverlayVisible(self, visible: bool) -> None:
        self._stack.setCurrentIndex(1 if visible else 0)

    @Slot(int)
    def setAutoRefresh(self, interval_ms: int) -> None:
        if self._refresh_timer is None:
            self._refresh_timer = QTimer(self)
            self._refresh_timer.timeout.connect(self.refreshRequested)
        if interval_ms and interval_ms > 0:
            self._refresh_timer.start(interval_ms)
        else:
            self._refresh_timer.stop()

    # ------------------------- Internal helpers -------------------------
    def _get_selected_task_id(self) -> Optional[str]:
        item = self._tasks_list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _get_selected_team_name(self) -> Optional[str]:
        item = self._teams_list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _emit_open_selected_task(self) -> None:
        tid = self._get_selected_task_id()
        if tid is not None:
            self.openTaskRequested.emit(str(tid))

    def _emit_reassign_selected_task(self) -> None:
        tid = self._get_selected_task_id()
        if tid is not None:
            self.reassignRequested.emit(str(tid), None)

    def _emit_reassign_selected_team(self) -> None:
        team = self._get_selected_team_name()
        self.reassignRequested.emit(None, team)

    def _emit_mark_complete_selected_task(self) -> None:
        tid = self._get_selected_task_id()
        if tid is not None:
            self.markCompleteRequested.emit(str(tid))

    def _on_task_double_clicked(self, item: QListWidgetItem) -> None:
        tid = item.data(Qt.UserRole)
        if tid is not None:
            self.openTaskRequested.emit(str(tid))

    def _on_tasks_context_menu(self, pos) -> None:
        global_pos = self._tasks_list.mapToGlobal(pos)
        menu = QMenu(self)
        act_open = menu.addAction("Open")
        act_reassign = menu.addAction("Reassign")
        act_complete = menu.addAction("Mark Complete")
        chosen = menu.exec(global_pos)
        if chosen is act_open:
            self._emit_open_selected_task()
        elif chosen is act_reassign:
            self._emit_reassign_selected_task()
        elif chosen is act_complete:
            self._emit_mark_complete_selected_task()


def make_ops_glance_widget(parent: Optional[QWidget] = None) -> OpsGlanceWidget:
    """Factory function for the Operations Dashboard widget."""
    return OpsGlanceWidget(parent)


if __name__ == "__main__":
    # Demo harness intentionally removed per application integration.
    # Launch via the app's Operations menu (see module docstring).
    pass
