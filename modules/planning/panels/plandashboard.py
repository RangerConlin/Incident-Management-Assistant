"""
Planning — At-a-Glance dashboard widget (Qt Widgets, PySide6).

Wiring instructions (add a Planning menu QAction next to “Strategic Objectives” / “Taskings”):

1) In your main window/menu setup (e.g., in `MainWindow` where the Planning menu is created),
   add a new QAction under the Planning menu and connect it to a slot that opens this widget.

   Example (inside your MainWindow setup code):

       from modules.planning.panels.plandashboard import make_planning_glance_widget

       # ... in menu construction for Planning ...
       self.actionPlanningGlance = QAction("Planning At-a-Glance", self)
       self.menuPlanning.addAction(self.actionPlanningGlance)

       # Slot to open the widget modeless and enable auto-refresh
       def open_planning_glance():
           # Keep a reference on the MainWindow to avoid GC
           if not hasattr(self, "_planning_glance_widget") or self._planning_glance_widget is None:
               self._planning_glance_widget = make_planning_glance_widget(self)
           w = self._planning_glance_widget
           w.setAutoRefresh(30_000)  # e.g., refresh every 30 seconds
           w.show()
           w.raise_()
           w.activateWindow()

       self.actionPlanningGlance.triggered.connect(open_planning_glance)

2) Optional (if your app uses an ADS/Dock Manager):

       # Example docking (pseudo-code; adapt to your dock framework)
       def open_planning_glance():
           if not hasattr(self, "_planning_glance_widget") or self._planning_glance_widget is None:
               self._planning_glance_widget = make_planning_glance_widget(self)
           w = self._planning_glance_widget
           w.setAutoRefresh(30_000)
           try:
               # If using Qt Advanced Docking System or similar
               self.dock_manager.addDockWidgetTabify("planning", w, title="Planning — At-a-Glance")
           except Exception:
               # Fallback to modeless window
               w.show()
               w.raise_()
               w.activateWindow()

This widget is purely presentational: no DB or network calls. Use the public
slots to push data in from your controllers/services.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedLayout,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class PillCard(QFrame):
    """Rounded small card showing a numeric value and label."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PillCard")
        self._value_label = QLabel("0", self)
        self._title_label = QLabel(title, self)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        self._value_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self._title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        # Typography
        f1 = self._value_label.font()
        f1.setPointSize(20)
        f1.setBold(True)
        self._value_label.setFont(f1)
        f2 = self._title_label.font()
        f2.setPointSize(10)
        self._title_label.setFont(f2)

        layout.addWidget(self._value_label)
        layout.addWidget(self._title_label)

        # Inline style (approx. shared look)
        self.setStyleSheet(
            """
            QFrame#PillCard {
                background: #ffffff;
                border: 1px solid #e1e5ea;
                border-radius: 12px;
            }
            QFrame#PillCard QLabel {
                color: #1a1f2b;
            }
            """
        )

    def set_value(self, value: Any) -> None:
        self._value_label.setText(str(value))


def _make_section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    f = lbl.font()
    f.setBold(True)
    f.setPointSize(12)
    lbl.setFont(f)
    return lbl


def _priority_bg(priority: str) -> QColor:
    p = (priority or "").strip().upper()
    if p == "CRITICAL":
        return QColor("#ffebee")  # light red
    if p == "HIGH":
        return QColor("#fff3e0")  # light orange
    if p == "MED":
        return QColor("#fffde7")  # light yellow
    return QColor("#eceff1")  # gray for LOW/unknown


class PlanningGlanceWidget(QWidget):
    """Compact Planning — At-a-Glance widget.

    Public slots/methods:
    - set_context(op_period, now_text, role)
    - update_kpis(kpis:dict)
    - update_alerts(alerts:list[dict])
    - update_actions(actions:list[dict])
    - update_iap_snapshot(iap:dict)
    - update_objectives(objs:list[dict])
    - update_doc_health(doc:dict)
    - setIncidentOverlayVisible(visible: bool)
    - setAutoRefresh(interval_ms:int)
    """

    # Signals
    openActionRequested = Signal(str)
    approveRequested = Signal(str)
    promoteRequested = Signal(str)
    viewObjectiveRequested = Signal(str)
    linkTasksRequested = Signal(str)
    openIAPBuilderRequested = Signal()
    exportSITREPRequested = Signal()
    openFullPlannerRequested = Signal()
    openQueueRequested = Signal()
    acknowledgeAlertsRequested = Signal()
    refreshRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlanningGlanceWidget")
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(False)
        self._auto_timer.timeout.connect(self.refreshRequested)

        # Main stacked layout to support incident overlay
        self._stack = QStackedLayout(self)
        self._content = QWidget(self)
        self._stack.addWidget(self._content)  # index 0 = content
        self._overlay = QLabel("No active incident — select or create one.")
        self._overlay.setAlignment(Qt.AlignCenter)
        of = self._overlay.font()
        of.setPointSize(12)
        of.setBold(True)
        self._overlay.setFont(of)
        self._stack.addWidget(self._overlay)  # index 1 = overlay
        self._stack.setCurrentIndex(0)

        self._build_ui(self._content)
        self._apply_styles()

    # ------------------------------- UI ---------------------------------
    def _build_ui(self, root: QWidget) -> None:
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self._title = QLabel("Planning — At-a-Glance", self)
        tf = self._title.font()
        tf.setPointSize(18)
        tf.setBold(True)
        self._title.setFont(tf)
        header_row.addWidget(self._title)
        header_row.addStretch(1)
        self._context_label = QLabel("OP: —  Now: —  Role: —", self)
        header_row.addWidget(self._context_label)
        root_layout.addLayout(header_row)

        # KPI row (6 pills)
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)
        self._kpi_cards: Dict[str, PillCard] = {}
        kpi_spec = [
            ("pending_approvals", "Pending approvals"),
            ("tasks_total", "Tasks total"),
            ("due_24h", "Due ≤24h"),
            ("new_objectives", "New objectives"),
            ("draft_to_planned_gap", "Draft→Planned gap"),
            ("overdue_docs", "Overdue docs"),
        ]
        for i, (key, title) in enumerate(kpi_spec):
            card = PillCard(title, self)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, 0, i)
        root_layout.addLayout(kpi_grid)

        # Alerts section
        alerts_box = QFrame(self)
        alerts_box.setObjectName("SectionBox")
        alerts_layout = QVBoxLayout(alerts_box)
        alerts_layout.setContentsMargins(10, 10, 10, 10)
        alerts_layout.setSpacing(6)

        alerts_header = QHBoxLayout()
        alerts_header.addWidget(_make_section_header("Alerts (planning-critical, last 30 min)"))
        alerts_header.addStretch(1)
        self._btn_open_queue = QPushButton("Open Queue ▸", self)
        self._btn_ack = QPushButton("Acknowledge", self)
        self._btn_open_queue.clicked.connect(self.openQueueRequested)
        self._btn_ack.clicked.connect(self.acknowledgeAlertsRequested)
        alerts_header.addWidget(self._btn_open_queue)
        alerts_header.addWidget(self._btn_ack)
        alerts_layout.addLayout(alerts_header)

        self._alerts_list = QListWidget(self)
        self._configure_list(self._alerts_list)
        alerts_layout.addWidget(self._alerts_list)
        root_layout.addWidget(alerts_box)

        # Middle two-column
        mid_row = QHBoxLayout()
        mid_row.setSpacing(10)

        # Left: Top Planning Actions
        actions_box = QFrame(self)
        actions_box.setObjectName("SectionBox")
        actions_layout = QVBoxLayout(actions_box)
        actions_layout.setContentsMargins(10, 10, 10, 10)
        actions_layout.setSpacing(6)
        actions_layout.addWidget(_make_section_header("Top Planning Actions"))
        self._actions_list = QListWidget(self)
        self._configure_list(self._actions_list)
        self._actions_list.itemDoubleClicked.connect(self._emit_open_selected_action)
        self._actions_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._actions_list.customContextMenuRequested.connect(self._show_actions_context_menu)
        actions_layout.addWidget(self._actions_list)
        btn_row_actions = QHBoxLayout()
        self._btn_action_open = QPushButton("Open", self)
        self._btn_action_approve = QPushButton("Approve", self)
        self._btn_action_promote = QPushButton("Promote", self)
        self._btn_action_open.clicked.connect(self._emit_open_selected_action)
        self._btn_action_approve.clicked.connect(self._emit_approve_selected)
        self._btn_action_promote.clicked.connect(self._emit_promote_selected)
        btn_row_actions.addWidget(self._btn_action_open)
        btn_row_actions.addWidget(self._btn_action_approve)
        btn_row_actions.addWidget(self._btn_action_promote)
        btn_row_actions.addStretch(1)
        actions_layout.addLayout(btn_row_actions)

        # Right: IAP Inputs Snapshot
        iap_box = QFrame(self)
        iap_box.setObjectName("SectionBox")
        iap_layout = QVBoxLayout(iap_box)
        iap_layout.setContentsMargins(10, 10, 10, 10)
        iap_layout.setSpacing(6)
        iap_layout.addWidget(_make_section_header("IAP Inputs Snapshot"))
        self._iap_row1 = QHBoxLayout()
        self._iap_row1.setSpacing(8)
        self._lbl_202 = self._make_badge("202 open", "#eceff1")
        self._lbl_203 = self._make_badge("203 unfilled roles", "#eceff1")
        self._lbl_204d = self._make_badge("204 drafts", "#eceff1")
        self._lbl_204m = self._make_badge("204 missing sign", "#eceff1")
        self._lbl_215 = self._make_badge("215 unresolved", "#eceff1")
        for w in (self._lbl_202, self._lbl_203, self._lbl_204d, self._lbl_204m, self._lbl_215):
            self._iap_row1.addWidget(w)
        self._iap_row1.addStretch(1)
        iap_layout.addLayout(self._iap_row1)

        mid_row.addWidget(actions_box, 1)
        mid_row.addWidget(iap_box, 1)
        root_layout.addLayout(mid_row)

        # Lower two-panels
        lower_row = QHBoxLayout()
        lower_row.setSpacing(10)

        # Left: Strategic Objectives
        obj_box = QFrame(self)
        obj_box.setObjectName("SectionBox")
        obj_layout = QVBoxLayout(obj_box)
        obj_layout.setContentsMargins(10, 10, 10, 10)
        obj_layout.setSpacing(6)
        obj_layout.addWidget(_make_section_header("Strategic Objectives (new/changed)"))
        self._objs_list = QListWidget(self)
        self._configure_list(self._objs_list)
        obj_layout.addWidget(self._objs_list)
        obj_btns = QHBoxLayout()
        self._btn_view_obj = QPushButton("View Objective", self)
        self._btn_link_tasks = QPushButton("Link Tasks", self)
        self._btn_view_obj.clicked.connect(self._emit_view_selected_objective)
        self._btn_link_tasks.clicked.connect(self._emit_link_tasks_selected)
        obj_btns.addWidget(self._btn_view_obj)
        obj_btns.addWidget(self._btn_link_tasks)
        obj_btns.addStretch(1)
        obj_layout.addLayout(obj_btns)

        # Right: Documentation Health
        doc_box = QFrame(self)
        doc_box.setObjectName("SectionBox")
        doc_layout = QVBoxLayout(doc_box)
        doc_layout.setContentsMargins(10, 10, 10, 10)
        doc_layout.setSpacing(6)
        doc_layout.addWidget(_make_section_header("Documentation Health (quick)"))
        self._doc_labels: Dict[str, QLabel] = {
            "214_ok": self._make_badge("ICS 214", "#eceff1"),
            "205_ok": self._make_badge("ICS 205", "#eceff1"),
            "205a_ok": self._make_badge("ICS 205A", "#eceff1"),
            "206_status": self._make_badge("ICS 206", "#eceff1"),
        }
        row = QHBoxLayout()
        row.setSpacing(8)
        for key in ("214_ok", "205_ok", "205a_ok", "206_status"):
            row.addWidget(self._doc_labels[key])
        row.addStretch(1)
        doc_layout.addLayout(row)

        lower_row.addWidget(obj_box, 1)
        lower_row.addWidget(doc_box, 1)
        root_layout.addLayout(lower_row)

        # Bottom actions row
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self._btn_new_obj = QPushButton("New Objective", self)
        self._btn_new_task = QPushButton("New Task", self)
        self._btn_open_iap = QPushButton("Open IAP Builder", self)
        self._btn_export_sitrep = QPushButton("Export SITREP", self)
        self._btn_full_planner = QPushButton("Full Planner", self)
        # Wire bottom actions to signals
        self._btn_open_iap.clicked.connect(self.openIAPBuilderRequested)
        self._btn_export_sitrep.clicked.connect(self.exportSITREPRequested)
        self._btn_full_planner.clicked.connect(self.openFullPlannerRequested)
        bottom.addWidget(self._btn_new_obj)
        bottom.addWidget(self._btn_new_task)
        bottom.addStretch(1)
        bottom.addWidget(self._btn_open_iap)
        bottom.addWidget(self._btn_export_sitrep)
        bottom.addWidget(self._btn_full_planner)
        root_layout.addLayout(bottom)

    def _apply_styles(self) -> None:
        # Subtle badges and section boxes
        self.setStyleSheet(
            """
            QLabel[role="badge"] {
                padding: 3px 8px;
                border-radius: 10px;
                border: 1px solid #dfe3e8;
                background: #eceff1;
                color: #263238;
            }
            QFrame#SectionBox {
                background: #fafbfc;
                border: 1px solid #e1e5ea;
                border-radius: 8px;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #e1e5ea;
                border-radius: 6px;
            }
            QPushButton {
                padding: 4px 10px;
            }
            """
        )

    def _configure_list(self, lst: QListWidget) -> None:
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lst.setUniformItemSizes(True)
        lst.setAlternatingRowColors(False)
        lst.setSpacing(2)

    def _make_badge(self, text: str, bg: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setProperty("role", "badge")
        lbl.setStyleSheet(
            f"QLabel[role=\"badge\"] {{ background: {bg}; border: 1px solid #dfe3e8; border-radius: 10px; padding: 3px 8px; }}"
        )
        return lbl

    # ---------------------------- Public slots ---------------------------
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self._context_label.setText(f"OP: {op_period}  Now: {now_text}  Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict[str, Any]) -> None:
        for key, card in self._kpi_cards.items():
            card.set_value(kpis.get(key, 0))

    @Slot(list)
    def update_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        self._alerts_list.clear()
        for entry in list(alerts)[:8]:
            ts = str(entry.get("ts", ""))
            text = str(entry.get("text", ""))
            item = QListWidgetItem(f"{ts} — {text}")
            item.setToolTip(text)
            self._alerts_list.addItem(item)

    @Slot(list)
    def update_actions(self, actions: List[Dict[str, Any]]) -> None:
        self._actions_list.clear()
        for action in list(actions)[:5]:
            aid = str(action.get("id", ""))
            title = str(action.get("title", ""))
            prio = str(action.get("priority", "")).upper()
            text = f"[{prio or 'LOW'}] {title}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, aid)
            item.setData(Qt.UserRole + 1, prio)
            item.setToolTip(title)
            # Colored background chip-esque
            bg = _priority_bg(prio)
            item.setBackground(bg)
            self._actions_list.addItem(item)

    @Slot(dict)
    def update_iap_snapshot(self, iap: Dict[str, Any]) -> None:
        self._lbl_202.setText(f"202 open: {iap.get('f202_open', 0)}")
        self._lbl_203.setText(f"203 unfilled roles: {iap.get('f203_unfilled_roles', 0)}")
        self._lbl_204d.setText(f"204 drafts: {iap.get('f204_drafts', 0)}")
        self._lbl_204m.setText(f"204 missing sign: {iap.get('f204_missing_sign', 0)}")
        self._lbl_215.setText(f"215 unresolved: {iap.get('f215_unresolved', 0)}")

    @Slot(list)
    def update_objectives(self, objs: List[Dict[str, Any]]) -> None:
        self._objs_list.clear()
        for obj in list(objs)[:6]:
            oid = str(obj.get("id", ""))
            title = str(obj.get("title", ""))
            status = str(obj.get("status", ""))
            due = str(obj.get("due", ""))
            cust = str(obj.get("customer", ""))
            text = f"[{status}] {title} — due {due} — {cust}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, oid)
            item.setToolTip(text)
            self._objs_list.addItem(item)

    @Slot(dict)
    def update_doc_health(self, doc: Dict[str, Any]) -> None:
        def set_ok(label: QLabel, ok: bool, name: str) -> None:
            if ok:
                label.setText(f"{name}: OK")
                label.setStyleSheet("QLabel[role=\"badge\"] { background: #e8f5e9; border: 1px solid #c8e6c9; }")
            else:
                label.setText(f"{name}: Needs attention")
                label.setStyleSheet("QLabel[role=\"badge\"] { background: #ffebee; border: 1px solid #ffcdd2; }")

        set_ok(self._doc_labels["214_ok"], bool(doc.get("214_ok", False)), "ICS 214")
        set_ok(self._doc_labels["205_ok"], bool(doc.get("205_ok", False)), "ICS 205")
        set_ok(self._doc_labels["205a_ok"], bool(doc.get("205a_ok", False)), "ICS 205A")

        status_206 = str(doc.get("206_status", "Unknown"))
        lbl_206 = self._doc_labels["206_status"]
        if status_206.strip().lower() in ("ok", "green", "ready"):
            lbl_206.setText(f"ICS 206: {status_206}")
            lbl_206.setStyleSheet("QLabel[role=\"badge\"] { background: #e8f5e9; border: 1px solid #c8e6c9; }")
        else:
            lbl_206.setText(f"ICS 206: {status_206}")
            lbl_206.setStyleSheet("QLabel[role=\"badge\"] { background: #fff3e0; border: 1px solid #ffe0b2; }")

    @Slot(bool)
    def setIncidentOverlayVisible(self, visible: bool) -> None:  # noqa: N802 (Qt slot naming)
        self._stack.setCurrentIndex(1 if visible else 0)

    @Slot(int)
    def setAutoRefresh(self, interval_ms: int) -> None:  # noqa: N802 (Qt slot naming)
        if interval_ms and interval_ms > 0:
            self._auto_timer.start(interval_ms)
        else:
            self._auto_timer.stop()

    # -------------------------- Internal helpers ------------------------
    def _current_selected_action_id(self) -> Optional[str]:
        item = self._actions_list.currentItem()
        if not item:
            return None
        aid = item.data(Qt.UserRole)
        return str(aid) if aid is not None else None

    def _current_selected_objective_id(self) -> Optional[str]:
        item = self._objs_list.currentItem()
        if not item:
            return None
        oid = item.data(Qt.UserRole)
        return str(oid) if oid is not None else None

    def _emit_open_selected_action(self) -> None:
        aid = self._current_selected_action_id()
        if aid:
            self.openActionRequested.emit(aid)

    def _emit_approve_selected(self) -> None:
        aid = self._current_selected_action_id()
        if aid:
            self.approveRequested.emit(aid)

    def _emit_promote_selected(self) -> None:
        aid = self._current_selected_action_id()
        if aid:
            self.promoteRequested.emit(aid)

    def _emit_view_selected_objective(self) -> None:
        oid = self._current_selected_objective_id()
        if oid:
            self.viewObjectiveRequested.emit(oid)

    def _emit_link_tasks_selected(self) -> None:
        oid = self._current_selected_objective_id()
        if oid:
            self.linkTasksRequested.emit(oid)

    def _show_actions_context_menu(self, pos) -> None:
        item = self._actions_list.itemAt(pos)
        if not item:
            return
        aid = item.data(Qt.UserRole)
        menu = self._actions_list.createStandardContextMenu()
        menu.clear()
        act_open = QAction("Open", self)
        act_approve = QAction("Approve", self)
        act_promote = QAction("Promote", self)
        act_open.triggered.connect(self._emit_open_selected_action)
        act_approve.triggered.connect(self._emit_approve_selected)
        act_promote.triggered.connect(self._emit_promote_selected)
        menu.addAction(act_open)
        menu.addAction(act_approve)
        menu.addAction(act_promote)
        global_pos = self._actions_list.mapToGlobal(pos)
        menu.exec(global_pos)


def make_planning_glance_widget(parent: Optional[QWidget] = None) -> PlanningGlanceWidget:
    """Factory for PlanningGlanceWidget."""
    return PlanningGlanceWidget(parent)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = PlanningGlanceWidget()
    w.resize(1000, 700)
    w.set_context("OP 3", "14:32", "Plans Section Chief")
    w.update_kpis(
        {
            "pending_approvals": 4,
            "tasks_total": 128,
            "due_24h": 17,
            "new_objectives": 2,
            "draft_to_planned_gap": 5,
            "overdue_docs": 3,
        }
    )
    w.update_alerts(
        [
            {"ts": "14:01", "text": "ICS 204 draft needs PSC approval"},
            {"ts": "14:18", "text": "Objective O-17 promoted to Planned"},
        ]
    )
    w.update_actions(
        [
            {"id": "A-101", "title": "Approve O-17", "priority": "HIGH"},
            {"id": "A-102", "title": "Promote 204-Alpha", "priority": "CRITICAL"},
            {"id": "A-103", "title": "Review 203 for unfilled roles", "priority": "MED"},
        ]
    )
    w.update_iap_snapshot(
        {
            "f202_open": 3,
            "f203_unfilled_roles": 4,
            "f204_drafts": 5,
            "f204_missing_sign": 2,
            "f215_unresolved": 1,
        }
    )
    w.update_objectives(
        [
            {"id": "O-17", "title": "Stabilize perimeter", "status": "New", "due": "EOD", "customer": "IC"},
            {"id": "O-18", "title": "Expand comms coverage", "status": "Changed", "due": "+1 day", "customer": "Ops"},
        ]
    )
    w.update_doc_health({"214_ok": True, "205_ok": False, "205a_ok": True, "206_status": "Needs updates"})
    w.setAutoRefresh(10_000)
    w.show()
    sys.exit(app.exec())
