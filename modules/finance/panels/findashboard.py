"""
Finance/Admin — Dashboard widget and factory.

Menu wiring instructions:
1) In the main window’s "Finance/Admin" menu, create a single QAction named:
     "Finance/Admin Dashboard"
   and connect it to a slot: open_finance_admin_dashboard()
2) open_finance_admin_dashboard() should create/show FinanceAdminDashboardWidget (modeless),
   call setAutoRefresh(15000), and connect refreshRequested to a controller slot that populates data.
3) REMOVE any older placeholders or duplicate menu items for finance/admin dashboards.

Qt Widgets only (PySide6). No QML. Pure presentation (no DB/network calls).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSize, QTimer, QPoint, Signal, Slot
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
    QAbstractItemView,
    QStackedLayout,
    QSizePolicy,
)


class _PillCard(QFrame):
    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PillCard")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("PillValue")
        self.text_label = QLabel(label)
        self.text_label.setObjectName("PillText")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(2)
        lay.addWidget(self.value_label)
        lay.addWidget(self.text_label)

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))


class FinanceAdminDashboardWidget(QWidget):
    """Finance/Admin — Dashboard compact panel.

    Pure presentation widget. Exposes signals for user actions, public slots for
    data updates, and an auto-refresh timer for polling.
    """

    # Signals
    openQueueRequested = Signal()
    acknowledgeAlertsRequested = Signal()

    openActionRequested = Signal(str)
    approveRequested = Signal(str)
    holdRequested = Signal(str)

    openTimekeepingRequested = Signal()
    openEquipmentUseRequested = Signal()
    openReimbursementsRequested = Signal()

    newPurchaseOrderRequested = Signal()
    newTimeEntryRequested = Signal()
    newEquipmentRecordRequested = Signal()
    openBudgetRequested = Signal()
    exportCostSummaryRequested = Signal()
    openFullFinanceAdminRequested = Signal()

    refreshRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._timer: Optional[QTimer] = None
        self._action_id_role = Qt.UserRole + 1

        self._root_stack = QStackedLayout(self)
        self._content = QWidget()
        self._root_stack.addWidget(self._content)
        self._overlay = self._build_overlay()
        self._root_stack.addWidget(self._overlay)

        self._build_ui(self._content)
        self._apply_styles()
        self._root_stack.setCurrentWidget(self._content)

    def _build_overlay(self) -> QWidget:
        overlay = QFrame()
        overlay.setObjectName("IncidentOverlay")
        v = QVBoxLayout(overlay)
        v.setContentsMargins(24, 24, 24, 24)
        lab = QLabel("No active incident — select or create one.")
        lab.setAlignment(Qt.AlignCenter)
        lab.setObjectName("OverlayLabel")
        v.addStretch(1)
        v.addWidget(lab)
        v.addStretch(1)
        return overlay

    def _build_ui(self, w: QWidget) -> None:
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel("Finance/Admin — Dashboard")
        self.title_label.setObjectName("HeaderTitle")
        self.context_label = QLabel("OP: —  Now: —  Role: —")
        self.context_label.setObjectName("HeaderContext")
        header.addWidget(self.title_label, 1)
        header.addWidget(self.context_label, 0, Qt.AlignRight)
        outer.addLayout(header)

        # KPI row (6 pills)
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(8)
        kpi_grid.setVerticalSpacing(8)
        self.kpi_cards: Dict[str, _PillCard] = {
            "pos_open": _PillCard("POs Open"),
            "invoices_pending": _PillCard("Invoices Pending"),
            "reimburse_pending": _PillCard("Reimburse Pending"),
            "budget_remaining": _PillCard("Budget Remaining"),
            "cost_op_today": _PillCard("Cost (OP)"),
            "overtime_hours": _PillCard("Overtime")
        }
        col = 0
        for key in [
            "pos_open",
            "invoices_pending",
            "reimburse_pending",
            "budget_remaining",
            "cost_op_today",
            "overtime_hours",
        ]:
            card = self.kpi_cards[key]
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            kpi_grid.addWidget(card, 0, col)
            col += 1
        outer.addLayout(kpi_grid)

        # Alerts bar
        alerts_box = QGroupBox("Alerts (finance-critical, last 30 min)")
        alerts_lay = QVBoxLayout(alerts_box)
        alerts_top = QHBoxLayout()
        self.btn_open_queue = QPushButton("Open Queue ▸")
        self.btn_ack = QPushButton("Acknowledge")
        alerts_top.addStretch(1)
        alerts_top.addWidget(self.btn_open_queue)
        alerts_top.addWidget(self.btn_ack)
        self.alerts_list = QListWidget()
        self._tune_list(self.alerts_list)
        alerts_lay.addLayout(alerts_top)
        alerts_lay.addWidget(self.alerts_list)
        outer.addWidget(alerts_box)

        # Two-column middle
        mid = QHBoxLayout()
        mid.setSpacing(10)

        # Left: Finance Actions
        actions_box = QGroupBox("Finance Actions")
        actions_lay = QVBoxLayout(actions_box)
        self.actions_list = QListWidget()
        self._tune_list(self.actions_list)
        self.actions_list.itemDoubleClicked.connect(self._on_action_double_clicked)
        self.actions_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.actions_list.customContextMenuRequested.connect(self._show_actions_context_menu)

        act_btns = QHBoxLayout()
        self.btn_action_open = QPushButton("Open")
        self.btn_action_approve = QPushButton("Approve")
        self.btn_action_hold = QPushButton("Hold")
        for b in (self.btn_action_open, self.btn_action_approve, self.btn_action_hold):
            b.setAutoDefault(False)
        act_btns.addWidget(self.btn_action_open)
        act_btns.addWidget(self.btn_action_approve)
        act_btns.addWidget(self.btn_action_hold)

        self.btn_action_open.clicked.connect(self._emit_open_selected_action)
        self.btn_action_approve.clicked.connect(self._emit_approve_selected_action)
        self.btn_action_hold.clicked.connect(self._emit_hold_selected_action)

        actions_lay.addWidget(self.actions_list)
        actions_lay.addLayout(act_btns)

        # Right: Finance Snapshot
        snap_box = QGroupBox("Finance Snapshot")
        snap_lay = QVBoxLayout(snap_box)
        self.snap_ops_today = QLabel("Ops Cost Today: —")
        self.snap_ops_to_date = QLabel("Ops Cost To Date: —")
        self.snap_budget_total = QLabel("Budget Total: —")
        self.snap_budget_used = QLabel("Budget Used: —")
        self.snap_budget_remaining = QLabel("Budget Remaining: —")
        self.snap_sections_over = QLabel("Sections Over Cap: —")
        for lab in (
            self.snap_ops_today,
            self.snap_ops_to_date,
            self.snap_budget_total,
            self.snap_budget_used,
            self.snap_budget_remaining,
            self.snap_sections_over,
        ):
            lab.setObjectName("SnapBadge")

        snap_lay.addWidget(self.snap_ops_today)
        snap_lay.addWidget(self.snap_ops_to_date)
        snap_lay.addWidget(self.snap_budget_total)
        snap_lay.addWidget(self.snap_budget_used)
        snap_lay.addWidget(self.snap_budget_remaining)
        snap_lay.addWidget(self.snap_sections_over)

        mid.addWidget(actions_box, 2)
        mid.addWidget(snap_box, 1)
        outer.addLayout(mid)

        # Lower two-panels
        low = QHBoxLayout()
        low.setSpacing(10)

        te_box = QGroupBox("Timekeeping & Equipment Use")
        te_lay = QVBoxLayout(te_box)
        self.te_line = QLabel("Time entries today: — (crews pending: —)  — Equip hours today: — (pending: —)")
        self.te_line.setObjectName("TELine")
        self.btn_open_timekeeping = QPushButton("Open Timekeeping")
        self.btn_open_equipment = QPushButton("Open Equipment Use")
        self.btn_open_timekeeping.clicked.connect(self.openTimekeepingRequested)
        self.btn_open_equipment.clicked.connect(self.openEquipmentUseRequested)
        te_btns = QHBoxLayout()
        te_btns.addWidget(self.btn_open_timekeeping)
        te_btns.addWidget(self.btn_open_equipment)
        te_lay.addWidget(self.te_line)
        te_lay.addLayout(te_btns)

        rb_box = QGroupBox("Claims & Reimbursements")
        rb_lay = QVBoxLayout(rb_box)
        self.rb_list = QListWidget()
        self._tune_list(self.rb_list)
        self.btn_open_reimburse = QPushButton("Open Reimbursements")
        self.btn_open_reimburse.clicked.connect(self.openReimbursementsRequested)
        rb_lay.addWidget(self.rb_list)
        rb_lay.addWidget(self.btn_open_reimburse)

        low.addWidget(te_box, 1)
        low.addWidget(rb_box, 1)
        outer.addLayout(low)

        # Bottom actions row
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_new_po = QPushButton("New Purchase Order")
        self.btn_new_time = QPushButton("New Time Entry")
        self.btn_new_equipment = QPushButton("New Equipment Record")
        self.btn_open_budget = QPushButton("Open Budget")
        self.btn_export_cost = QPushButton("Export Cost Summary")
        self.btn_open_full = QPushButton("Open Full Finance/Admin")

        for b in (
            self.btn_new_po,
            self.btn_new_time,
            self.btn_new_equipment,
            self.btn_open_budget,
            self.btn_export_cost,
            self.btn_open_full,
        ):
            actions.addWidget(b)

        self.btn_new_po.clicked.connect(self.newPurchaseOrderRequested)
        self.btn_new_time.clicked.connect(self.newTimeEntryRequested)
        self.btn_new_equipment.clicked.connect(self.newEquipmentRecordRequested)
        self.btn_open_budget.clicked.connect(self.openBudgetRequested)
        self.btn_export_cost.clicked.connect(self.exportCostSummaryRequested)
        self.btn_open_full.clicked.connect(self.openFullFinanceAdminRequested)

        outer.addLayout(actions)

        # Wire alerts buttons
        self.btn_open_queue.clicked.connect(self.openQueueRequested)
        self.btn_ack.clicked.connect(self.acknowledgeAlertsRequested)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QLabel#HeaderTitle {
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#HeaderContext {
                color: #444;
            }
            QFrame#PillCard {
                background: white;
                border: 1px solid #dcdcdc;
                border-radius: 12px;
            }
            QLabel#PillValue {
                font-size: 20px;
                font-weight: 600;
            }
            QLabel#PillText {
                color: #555;
            }
            QLabel#SnapBadge, QLabel#TELine {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px 8px;
                background: #fafafa;
            }
            QGroupBox {
                font-weight: 600;
            }
            QFrame#IncidentOverlay {
                background: rgba(245,245,245,0.9);
                border: 0px;
            }
            QLabel#OverlayLabel {
                font-size: 16px;
                color: #555;
            }
            """
        )

    def _tune_list(self, lst: QListWidget) -> None:
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lst.setUniformItemSizes(True)
        lst.setAlternatingRowColors(True)
        lst.setWordWrap(False)
        lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # Context menu for actions
    def _selected_action_id(self) -> Optional[str]:
        it = self.actions_list.currentItem()
        if not it:
            return None
        return it.data(self._action_id_role)

    def _show_actions_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        act_open = menu.addAction("Open")
        act_approve = menu.addAction("Approve")
        act_hold = menu.addAction("Hold")
        act = menu.exec_(self.actions_list.mapToGlobal(pos))
        action_id = self._selected_action_id()
        if not action_id:
            return
        if act == act_open:
            self.openActionRequested.emit(action_id)
        elif act == act_approve:
            self.approveRequested.emit(action_id)
        elif act == act_hold:
            self.holdRequested.emit(action_id)

    def _on_action_double_clicked(self, item: QListWidgetItem) -> None:
        action_id = item.data(self._action_id_role)
        if action_id:
            self.openActionRequested.emit(str(action_id))

    def _emit_open_selected_action(self) -> None:
        action_id = self._selected_action_id()
        if action_id:
            self.openActionRequested.emit(action_id)

    def _emit_approve_selected_action(self) -> None:
        action_id = self._selected_action_id()
        if action_id:
            self.approveRequested.emit(action_id)

    def _emit_hold_selected_action(self) -> None:
        action_id = self._selected_action_id()
        if action_id:
            self.holdRequested.emit(action_id)

    # Public slots / methods
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self.context_label.setText(f"OP: {op_period}  Now: {now_text}  Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict) -> None:
        mapping = {
            "pos_open": kpis.get("pos_open", "—"),
            "invoices_pending": kpis.get("invoices_pending", "—"),
            "reimburse_pending": kpis.get("reimburse_pending", "—"),
            "budget_remaining": kpis.get("budget_remaining", "—"),
            "cost_op_today": kpis.get("cost_op_today", "—"),
            "overtime_hours": kpis.get("overtime_hours", "—"),
        }
        for key, val in mapping.items():
            self.kpi_cards[key].set_value(val)

    @Slot(list)
    def update_alerts(self, alerts: List[Dict]) -> None:
        self.alerts_list.clear()
        for a in alerts[:8]:
            ts = str(a.get("ts", "—"))
            text = str(a.get("text", ""))
            item = QListWidgetItem(f"{ts}  —  {text}")
            item.setToolTip(text)
            self.alerts_list.addItem(item)

    @Slot(list)
    def update_actions(self, actions: List[Dict]) -> None:
        self.actions_list.clear()
        for a in actions[:6]:
            aid = str(a.get("id", ""))
            title = str(a.get("title", ""))
            prio = str(a.get("priority", ""))
            text = f"{title} — {prio}"
            tip = f"{aid}: {title}\nPriority: {prio}"
            item = QListWidgetItem(text)
            item.setData(self._action_id_role, aid)
            item.setToolTip(tip)
            self.actions_list.addItem(item)

    @Slot(dict)
    def update_finance_snapshot(self, snap: Dict) -> None:
        self.snap_ops_today.setText(f"Ops Cost Today: {snap.get('ops_cost_today', '—')}")
        self.snap_ops_to_date.setText(f"Ops Cost To Date: {snap.get('ops_cost_to_date', '—')}")
        self.snap_budget_total.setText(f"Budget Total: {snap.get('budget_total', '—')}")
        self.snap_budget_used.setText(f"Budget Used: {snap.get('budget_used', '—')}")
        self.snap_budget_remaining.setText(f"Budget Remaining: {snap.get('budget_remaining', '—')}")
        sections = snap.get("sections_over_cap", []) or []
        if isinstance(sections, list) and sections:
            sec_text = ", ".join(sections)
        elif isinstance(sections, list):
            sec_text = "—"
        else:
            sec_text = str(sections)
        self.snap_sections_over.setText(f"Sections Over Cap: {sec_text}")

    @Slot(dict)
    def update_time_equip(self, te: Dict) -> None:
        entries = te.get("time_entries_today", "—")
        crews = te.get("crews_pending", "—")
        eq_hours = te.get("equipment_hours_today", "—")
        eq_pending = te.get("equipment_pending", "—")
        self.te_line.setText(
            f"Time entries today: {entries} (crews pending: {crews})  — Equip hours today: {eq_hours} (pending: {eq_pending})"
        )

    @Slot(list)
    def update_reimburse_queue(self, items: List[Dict]) -> None:
        self.rb_list.clear()
        for it in items[:6]:
            rid = str(it.get("id", ""))
            title = str(it.get("title", ""))
            amount = str(it.get("amount", ""))
            status = str(it.get("status", ""))
            text = f"{rid}  {title}  {amount}  — {status}"
            tip = f"{rid}: {title}\nAmount: {amount}\nStatus: {status}"
            item = QListWidgetItem(text)
            item.setToolTip(tip)
            self.rb_list.addItem(item)

    @Slot(bool)
    def setIncidentOverlayVisible(self, visible: bool) -> None:
        self._root_stack.setCurrentWidget(self._overlay if visible else self._content)

    @Slot(int)
    def setAutoRefresh(self, interval_ms: int) -> None:
        if interval_ms and interval_ms > 0:
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self.refreshRequested)
            self._timer.start(interval_ms)
        else:
            if self._timer is not None:
                self._timer.stop()


def make_finance_admin_dashboard(parent: Optional[QWidget] = None) -> FinanceAdminDashboardWidget:
    return FinanceAdminDashboardWidget(parent)


if __name__ == "__main__":
    # Testing harness with demo placeholder data
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    w = FinanceAdminDashboardWidget()

    kpis = {
        "pos_open": 7,
        "invoices_pending": 5,
        "reimburse_pending": 3,
        "budget_remaining": "$124,500",
        "cost_op_today": "$8,430",
        "overtime_hours": "26.5h (today)",
    }
    alerts = [
        {"ts": "14:50", "text": "Invoice V-7781 overdue 5 days"},
        {"ts": "14:42", "text": "Ops section trending 12% over daily burn"},
    ]
    actions = [
        {"id": "PO-2143", "title": "Approve PO #2143 (Med tent supplies)", "priority": "HIGH"},
        {"id": "INV-7781", "title": "Review Invoice V-7781 (Vendor Alpha)", "priority": "MED"},
        {"id": "HOLD-991", "title": "Place hold on PO #1991 (radio cache)", "priority": "LOW"},
    ]
    snap = {
        "ops_cost_today": "$8,430",
        "ops_cost_to_date": "$64,220",
        "budget_total": "$200,000",
        "budget_used": "$75,500",
        "budget_remaining": "$124,500",
        "sections_over_cap": ["Ops"],
    }
    te = {"time_entries_today": 43, "crews_pending": 3, "equipment_hours_today": "56.0h", "equipment_pending": 2}
    reimburse = [
        {"id": "RB-102", "title": "Team G-2 fuel", "amount": "$145.60", "status": "PENDING"},
        {"id": "RB-099", "title": "A-1 oil & filter", "amount": "$87.20", "status": "UNDER REVIEW"},
    ]

    # Apply demo state
    w.update_kpis(kpis)
    w.update_alerts(alerts)
    w.update_actions(actions)
    w.update_finance_snapshot(snap)
    w.update_time_equip(te)
    w.update_reimburse_queue(reimburse)
    w.set_context("3", "14:52", "Finance/Admin Chief")
    w.setAutoRefresh(15000)

    w.resize(QSize(1100, 800))
    w.show()

    sys.exit(app.exec())

