"""
Menu wiring instructions (Logistics Dashboard):

1) In the main window’s "Logistics" menu, create a single QAction named:
     "Logistics Dashboard"
   and connect it to a slot: open_logistics_dashboard()

2) open_logistics_dashboard() should create/show LogisticsDashboardWidget (modeless),
   set auto-refresh, and connect refreshRequested to the controller.

3) REMOVE any older placeholders or duplicate menu items for Logistics dashboard.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QGroupBox,
    QMenu,
    QStackedLayout,
    QApplication,
    QAbstractItemView,
)


class _KpiPill(QFrame):
    def __init__(self, label_text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("pill", True)
        self.setObjectName(f"pill_{label_text.lower().replace(' ', '_')}")
        self._value = QLabel("—")
        self._value.setObjectName("pill_value")
        self._label = QLabel(label_text)
        self._label.setObjectName("pill_label")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(0)
        lay.addWidget(self._value, alignment=Qt.AlignHCenter)
        lay.addWidget(self._label, alignment=Qt.AlignHCenter)

    def set_value(self, text: str) -> None:
        self._value.setText(text)


class _Badge(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("badge", True)
        self._dot = QLabel("●")
        self._dot.setObjectName("badge_dot")
        self._text = QLabel(title + ": —")
        self._text.setObjectName("badge_text")
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(6)
        h.addWidget(self._dot)
        h.addWidget(self._text, 1)

    def set_state(self, state_text: str) -> None:
        # Normalize
        st = (state_text or "").strip().lower()
        if st.startswith("ok"):
            self.setProperty("state", "ok")
        elif st.startswith("low"):
            self.setProperty("state", "low")
        else:
            # treat all others as tight/attention
            self.setProperty("state", "tight")
        self.style().unpolish(self)
        self.style().polish(self)
        # Update label body but preserve leading title
        prefix = self._text.text().split(":", 1)[0]
        self._text.setText(f"{prefix}: {state_text}")

    def set_text_value(self, value_text: str) -> None:
        prefix = self._text.text().split(":", 1)[0]
        self._text.setText(f"{prefix}: {value_text}")


class LogisticsDashboardWidget(QWidget):
    """Logistics Dashboard widget (Qt Widgets).

    Title: "Logistics — Dashboard"
    Compact, high-signal layout.
    """

    # Signals
    openActionRequested = Signal(str)
    approveRequested = Signal(str)
    assignRequested = Signal(str)
    openQueueRequested = Signal()
    acknowledgeAlertsRequested = Signal()
    openSuppliesRequested = Signal()
    openCommsCacheRequested = Signal()
    openDemobBoardRequested = Signal()
    new213RRRequested = Signal()
    newCheckInRequested = Signal()
    open211_218Requested = Signal()
    print204SupportRequested = Signal()
    export214Requested = Signal()
    openFullDashboardRequested = Signal()
    refreshRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Logistics Dashboard")
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self.refreshRequested)

        self._kpi_widgets: Dict[str, _KpiPill] = {}
        self._badges: Dict[str, _Badge] = {}

        self._build_ui()
        self._apply_styles()

    # --------------------- UI Construction ---------------------
    def _build_ui(self) -> None:
        self._stack = QStackedLayout(self)

        # Overlay page
        overlay_page = QWidget()
        ovl_layout = QVBoxLayout(overlay_page)
        ovl_layout.setContentsMargins(20, 20, 20, 20)
        ovl_layout.addStretch(1)
        self._overlay_label = QLabel("No active incident — select or create one.")
        self._overlay_label.setAlignment(Qt.AlignCenter)
        self._overlay_label.setObjectName("overlay_label")
        ovl_layout.addWidget(self._overlay_label)
        ovl_layout.addStretch(1)

        # Main page
        main_page = QWidget()
        root = QVBoxLayout(main_page)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Header row
        header = QHBoxLayout()
        self._title = QLabel("Logistics — Dashboard")
        self._title.setObjectName("title")
        self._context = QLabel("OP: —  Now: —  Role: —")
        self._context.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self._title, 1)
        header.addWidget(self._context, 1)
        root.addLayout(header)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        def add_kpi(key: str, label: str) -> None:
            pill = _KpiPill(label)
            self._kpi_widgets[key] = pill
            kpi_row.addWidget(pill)

        add_kpi("open_requests", "Open Requests")
        add_kpi("approvals_pending", "Approvals Pending")
        add_kpi("low_stock_alerts", "Low Stock Alerts")
        add_kpi("checkins_today", "Check-ins Today")
        add_kpi("vehicles_ready", "Vehicles Ready")
        add_kpi("facilities_ok", "Facilities OK")
        root.addLayout(kpi_row)

        # Alerts bar
        alerts_box = QGroupBox("Alerts (last 30 min)")
        alerts_lay = QVBoxLayout(alerts_box)
        alerts_head = QHBoxLayout()
        self._btn_open_queue = QPushButton("Open Queue ▸")
        self._btn_ack = QPushButton("Acknowledge")
        alerts_head.addStretch(1)
        alerts_head.addWidget(self._btn_open_queue)
        alerts_head.addWidget(self._btn_ack)
        alerts_lay.addLayout(alerts_head)
        self._alerts_list = QListWidget()
        self._alerts_list.setUniformItemSizes(True)
        self._alerts_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._alerts_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._alerts_list.setAlternatingRowColors(True)
        alerts_lay.addWidget(self._alerts_list)
        root.addWidget(alerts_box)

        # Two-column middle
        mid = QHBoxLayout()
        mid.setSpacing(8)

        # Left: Top Logistics Actions
        actions_box = QGroupBox("Top Logistics Actions")
        actions_lay = QVBoxLayout(actions_box)
        self._actions_list = QListWidget()
        self._actions_list.setUniformItemSizes(True)
        self._actions_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._actions_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._actions_list.setAlternatingRowColors(True)
        self._actions_list.itemDoubleClicked.connect(self._on_action_double_clicked)
        self._actions_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._actions_list.customContextMenuRequested.connect(self._on_actions_context_menu)
        actions_lay.addWidget(self._actions_list)
        btn_row = QHBoxLayout()
        self._btn_open = QPushButton("Open")
        self._btn_approve = QPushButton("Approve")
        self._btn_assign = QPushButton("Assign")
        btn_row.addWidget(self._btn_open)
        btn_row.addWidget(self._btn_approve)
        btn_row.addWidget(self._btn_assign)
        btn_row.addStretch(1)
        actions_lay.addLayout(btn_row)

        # Right: Resource/Facility Snapshot
        snap_box = QGroupBox("Resource/Facility Snapshot")
        grid = QGridLayout(snap_box)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        def add_snap(row: int, col: int, title: str, obj: str) -> QLabel:
            lblt = QLabel(title)
            lblt.setObjectName("snap_title")
            lblv = QLabel("—")
            lblv.setObjectName(obj)
            grid.addWidget(lblt, row, col * 2)
            grid.addWidget(lblv, row, col * 2 + 1)
            return lblv

        self._snap_checkins_total = add_snap(0, 0, "Check-ins Total:", "snap_checkins_total")
        self._snap_checkins_pending = add_snap(0, 1, "Check-ins Pending:", "snap_checkins_pending")
        self._snap_missing_serials = add_snap(1, 0, "ICS 218 Missing Serials:", "snap_missing_serials")
        self._snap_veh_ready = add_snap(1, 1, "Vehicles Ready:", "snap_veh_ready")
        self._snap_veh_assigned = add_snap(2, 0, "Vehicles Assigned:", "snap_veh_assigned")
        self._snap_veh_oos = add_snap(2, 1, "Vehicles OOS:", "snap_veh_oos")
        self._snap_facilities = add_snap(3, 0, "Facilities:", "snap_facilities")

        mid.addWidget(actions_box, 1)
        mid.addWidget(snap_box, 1)
        root.addLayout(mid)

        # Lower two-panels
        lower = QHBoxLayout()
        lower.setSpacing(8)

        # Left: Supply & Comms Health
        health_box = QGroupBox("Supply & Comms Health")
        h_lay = QVBoxLayout(health_box)
        # Badges line
        badges_row = QHBoxLayout()
        for key, title in (
            ("ppe", "PPE"),
            ("medical", "Medical"),
            ("water", "Water"),
            ("fuel", "Fuel"),
        ):
            b = _Badge(title)
            self._badges[key] = b
            badges_row.addWidget(b)
        h_lay.addLayout(badges_row)
        # Comms line
        comms_row = QHBoxLayout()
        self._badge_comms_cache = _Badge("Comms Cache")
        self._badge_spare_radios = _Badge("Spare Radios")
        self._badges["comms_cache"] = self._badge_comms_cache
        self._badges["spare_radios"] = self._badge_spare_radios
        comms_row.addWidget(self._badge_comms_cache)
        comms_row.addWidget(self._badge_spare_radios)
        h_lay.addLayout(comms_row)
        # Buttons
        h_btns = QHBoxLayout()
        self._btn_open_supplies = QPushButton("Open Supplies")
        self._btn_open_comms = QPushButton("Open Comms Cache")
        h_btns.addWidget(self._btn_open_supplies)
        h_btns.addWidget(self._btn_open_comms)
        h_btns.addStretch(1)
        h_lay.addLayout(h_btns)

        # Right: Demob / Returns Queue
        demob_box = QGroupBox("Demob / Returns Queue")
        d_lay = QVBoxLayout(demob_box)
        self._demob_list = QListWidget()
        self._demob_list.setUniformItemSizes(True)
        self._demob_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._demob_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._demob_list.setAlternatingRowColors(True)
        d_lay.addWidget(self._demob_list)
        self._btn_open_demob = QPushButton("Open Demob Board")
        d_lay.addWidget(self._btn_open_demob, alignment=Qt.AlignRight)

        lower.addWidget(health_box, 1)
        lower.addWidget(demob_box, 1)
        root.addLayout(lower)

        # Bottom actions row
        bottom = QHBoxLayout()
        self._btn_new_213rr = QPushButton("New 213RR")
        self._btn_new_checkin = QPushButton("New Check-In")
        self._btn_open_211_218 = QPushButton("Open 211/218")
        self._btn_print_204 = QPushButton("Print 204 Support")
        self._btn_export_214 = QPushButton("Export 214")
        self._btn_open_full = QPushButton("Open Full Dashboard")
        for b in (
            self._btn_new_213rr,
            self._btn_new_checkin,
            self._btn_open_211_218,
            self._btn_print_204,
            self._btn_export_214,
            self._btn_open_full,
        ):
            bottom.addWidget(b)
        bottom.addStretch(1)
        root.addLayout(bottom)

        # Wire buttons to signals
        self._btn_open_queue.clicked.connect(self.openQueueRequested)
        self._btn_ack.clicked.connect(self.acknowledgeAlertsRequested)
        self._btn_open.clicked.connect(self._emit_open_selected)
        self._btn_approve.clicked.connect(self._emit_approve_selected)
        self._btn_assign.clicked.connect(self._emit_assign_selected)
        self._btn_open_supplies.clicked.connect(self.openSuppliesRequested)
        self._btn_open_comms.clicked.connect(self.openCommsCacheRequested)
        self._btn_open_demob.clicked.connect(self.openDemobBoardRequested)
        self._btn_new_213rr.clicked.connect(self.new213RRRequested)
        self._btn_new_checkin.clicked.connect(self.newCheckInRequested)
        self._btn_open_211_218.clicked.connect(self.open211_218Requested)
        self._btn_print_204.clicked.connect(self.print204SupportRequested)
        self._btn_export_214.clicked.connect(self.export214Requested)
        self._btn_open_full.clicked.connect(self.openFullDashboardRequested)

        # Add pages to stack
        self._stack.addWidget(overlay_page)
        self._stack.addWidget(main_page)
        self._stack.setCurrentIndex(1)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QLabel#title { font-size: 18px; font-weight: 600; }
            QLabel#pill_value { font-size: 20px; font-weight: 600; }
            QLabel#pill_label { font-size: 11px; color: #555; }
            QFrame[pill="true"] {
                background: white;
                border-radius: 12px;
                border: 1px solid #dcdcdc;
            }
            QGroupBox { font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 2px 4px; }
            QListWidget { background: #fafafa; }
            QLabel#overlay_label { color: #666; font-size: 14px; }

            /* Badges */
            QFrame[badge="true"] {
                border: 1px solid #dcdcdc;
                border-radius: 10px;
                background: #ffffff;
            }
            QFrame[badge="true"][state="ok"] QLabel#badge_dot { color: #1a7f37; }
            QFrame[badge="true"][state="low"] QLabel#badge_dot { color: #b54708; }
            QFrame[badge="true"][state="tight"] QLabel#badge_dot { color: #b42318; }
            QLabel#badge_text { font-size: 12px; }
            """
        )

    # --------------------- Helpers ---------------------
    def _selected_action_id(self) -> Optional[str]:
        item = self._actions_list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _on_action_double_clicked(self, item: QListWidgetItem) -> None:
        action_id = item.data(Qt.UserRole)
        if action_id:
            self.openActionRequested.emit(str(action_id))

    def _on_actions_context_menu(self, pos) -> None:
        item = self._actions_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_open = menu.addAction("Open")
        act_approve = menu.addAction("Approve")
        act_assign = menu.addAction("Assign")
        chosen = menu.exec(self._actions_list.mapToGlobal(pos))
        if chosen == act_open:
            self._on_action_double_clicked(item)
        elif chosen == act_approve:
            action_id = item.data(Qt.UserRole)
            if action_id:
                self.approveRequested.emit(str(action_id))
        elif chosen == act_assign:
            action_id = item.data(Qt.UserRole)
            if action_id:
                self.assignRequested.emit(str(action_id))

    def _emit_open_selected(self) -> None:
        action_id = self._selected_action_id()
        if action_id:
            self.openActionRequested.emit(action_id)

    def _emit_approve_selected(self) -> None:
        action_id = self._selected_action_id()
        if action_id:
            self.approveRequested.emit(action_id)

    def _emit_assign_selected(self) -> None:
        action_id = self._selected_action_id()
        if action_id:
            self.assignRequested.emit(action_id)

    # --------------------- Public API (Slots) ---------------------
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self._context.setText(f"OP: {op_period}  Now: {now_text}  Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict[str, object]) -> None:
        mapping = {
            "open_requests": "open_requests",
            "approvals_pending": "approvals_pending",
            "low_stock_alerts": "low_stock_alerts",
            "checkins_today": "checkins_today",
            "vehicles_ready": "vehicles_ready",
            "facilities_ok": "facilities_ok",
        }
        for key, ref in mapping.items():
            if key in kpis and ref in self._kpi_widgets:
                self._kpi_widgets[ref].set_value(str(kpis[key]))

    @Slot(list)
    def update_alerts(self, alerts: List[Dict[str, str]]) -> None:
        self._alerts_list.clear()
        # newest-first, limit ~8
        for idx, a in enumerate(alerts[:8]):
            ts = a.get("ts", "—")
            text = a.get("text", "")
            item = QListWidgetItem(f"{ts}  —  {text}")
            item.setToolTip(text)
            self._alerts_list.insertItem(idx, item)

    @Slot(list)
    def update_actions(self, actions: List[Dict[str, str]]) -> None:
        self._actions_list.clear()
        for a in actions[:5]:
            aid = a.get("id", "")
            title = a.get("title", "")
            prio = a.get("priority", "")
            item = QListWidgetItem(f"[{prio}] {title}")
            item.setData(Qt.UserRole, aid)
            item.setToolTip(title)
            self._actions_list.addItem(item)

    @Slot(dict)
    def update_resource_snapshot(self, snap: Dict[str, object]) -> None:
        def set_lbl(lbl: QLabel, key: str) -> None:
            if key in snap:
                lbl.setText(str(snap[key]))

        set_lbl(self._snap_checkins_total, "checkins_total")
        set_lbl(self._snap_checkins_pending, "checkins_pending")
        set_lbl(self._snap_missing_serials, "equip_218_missing_serials")
        set_lbl(self._snap_veh_ready, "vehicles_ready")
        set_lbl(self._snap_veh_assigned, "vehicles_assigned")
        set_lbl(self._snap_veh_oos, "vehicles_oos")
        set_lbl(self._snap_facilities, "facilities_status")

    @Slot(dict)
    def update_supply_comms(self, health: Dict[str, object]) -> None:
        for key in ("ppe", "medical", "water", "fuel"):
            if key in health and key in self._badges:
                self._badges[key].set_state(str(health[key]))
        # comms_cache and spare_radios handled too
        if "comms_cache" in health:
            self._badge_comms_cache.set_state(str(health["comms_cache"]))
        if "spare_radios" in health:
            # Show numeric/text value without changing badge color
            self._badge_spare_radios.set_text_value(str(health["spare_radios"]))

    @Slot(list)
    def update_demob_queue(self, items: List[Dict[str, str]]) -> None:
        self._demob_list.clear()
        for it in items[:6]:
            iid = it.get("id", "")
            title = it.get("title", "")
            due = it.get("due", "")
            item = QListWidgetItem(f"{due}  —  {title}")
            item.setData(Qt.UserRole, iid)
            item.setToolTip(title)
            self._demob_list.addItem(item)

    @Slot(bool)
    def setIncidentOverlayVisible(self, visible: bool) -> None:  # noqa: N802 (Qt naming)
        self._stack.setCurrentIndex(0 if visible else 1)

    @Slot(int)
    def setAutoRefresh(self, interval_ms: int) -> None:  # noqa: N802 (Qt naming)
        if interval_ms and interval_ms > 0:
            self._timer.start(int(interval_ms))
        else:
            self._timer.stop()


def make_logistics_dashboard(parent: Optional[QWidget] = None) -> LogisticsDashboardWidget:
    return LogisticsDashboardWidget(parent)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    w = make_logistics_dashboard()

    # Demo data
    kpis = {
        "open_requests": 9,
        "approvals_pending": 3,
        "low_stock_alerts": 4,
        "checkins_today": 12,
        "vehicles_ready": "7/10",
        "facilities_ok": "5/6",
    }
    alerts = [
        {"ts": "14:35", "text": "Med cache 'Alpha' <25% (trauma gauze)"},
        {"ts": "14:28", "text": "V-3 Truck set OOS (engine temp)"},
    ]
    actions = [
        {"id": "213RR-112", "title": "Approve 213RR-112 (Shelter cots)", "priority": "HIGH"},
        {"id": "ASSIGN-RK07", "title": "Assign Radio Kit RK-07 to Team G-2", "priority": "MED"},
        {"id": "FUEL-STAGE", "title": "Schedule fuel drop at Staging", "priority": "HIGH"},
    ]
    snap = {
        "checkins_total": 12,
        "checkins_pending": 3,
        "equip_218_missing_serials": 4,
        "vehicles_ready": 7,
        "vehicles_assigned": 2,
        "vehicles_oos": 1,
        "facilities_status": "Staging OK / ICP OK / Med Tent ⚠",
    }
    health = {"ppe": "OK", "medical": "LOW", "water": "OK", "fuel": "TIGHT", "comms_cache": "OK", "spare_radios": 2}
    demob = [
        {"id": "RET-G4", "title": "G-4 radio kit return", "due": "16:00"},
        {"id": "FUEL-A1", "title": "A-1 fuel top-off", "due": "15:30"},
    ]

    w.update_kpis(kpis)
    w.update_alerts(alerts)
    w.update_actions(actions)
    w.update_resource_snapshot(snap)
    w.update_supply_comms(health)
    w.update_demob_queue(demob)
    w.set_context("3", "14:40", "Logistics Chief")
    w.setAutoRefresh(15000)

    w.resize(QSize(1000, 720))
    w.show()
    sys.exit(app.exec())
