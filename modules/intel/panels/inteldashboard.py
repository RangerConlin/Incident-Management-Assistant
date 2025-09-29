"""
Intel — Dashboard widget and factory.

Menu wiring instructions:
1) In the main window’s "Intel" menu, create a single QAction named:
     "Intel Dashboard"
   and connect it to a slot: open_intel_dashboard()
2) open_intel_dashboard() should create/show IntelDashboardWidget (modeless),
   set auto-refresh, and connect refreshRequested to a controller slot.
3) REMOVE any older placeholders or duplicate menu items for Intel dashboards.

Qt Widgets only (PySide6). No QML.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSize, QTimer, QPoint, Signal, Slot
from PySide6.QtGui import QAction
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


class IntelDashboardWidget(QWidget):
    """Intel — Dashboard compact panel.

    Exposes signals for user actions, public slots for data updates,
    and an auto-refresh timer for polling.
    """

    # Signals
    openQueueRequested = Signal()
    acknowledgeAlertsRequested = Signal()

    openLeadRequested = Signal(str)
    triageLeadRequested = Signal(str)
    markLeadVerifiedRequested = Signal(str)
    markLeadFalseRequested = Signal(str)

    openMapRequested = Signal()
    openSubjectFileRequested = Signal()
    openSITREPRequested = Signal()
    openWeatherRequested = Signal()
    newIntelReportRequested = Signal()
    newLeadRequested = Signal()
    exportIntelSummaryRequested = Signal()
    openFullIntelRequested = Signal()

    refreshRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._timer: Optional[QTimer] = None
        self._lead_id_role = Qt.UserRole + 1

        self._root_stack = QStackedLayout(self)

        # Main content widget
        self._content = QWidget()
        self._root_stack.addWidget(self._content)

        # Overlay for no active incident
        self._overlay = self._build_overlay()
        self._root_stack.addWidget(self._overlay)

        self._build_ui(self._content)
        self._apply_styles()

        # Start visible on content
        self._root_stack.setCurrentWidget(self._content)

    # UI construction
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
        self.title_label = QLabel("Intel — Dashboard")
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
            "new_reports": _PillCard("New Reports (24h)"),
            "open_leads": _PillCard("Open Leads"),
            "verified_clues": _PillCard("Verified Clues"),
            "false_pos": _PillCard("False Positives"),
            "priority_areas": _PillCard("Priority Areas"),
            "weather_brief_status": _PillCard("Wx Brief")
        }
        col = 0
        for key in [
            "new_reports",
            "open_leads",
            "verified_clues",
            "false_pos",
            "priority_areas",
            "weather_brief_status",
        ]:
            card = self.kpi_cards[key]
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            kpi_grid.addWidget(card, 0, col)
            col += 1
        outer.addLayout(kpi_grid)

        # Alerts bar
        alerts_box = QGroupBox("Alerts (intel-critical, last 30 min)")
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

        # Left: Leads & Clue Triage
        leads_box = QGroupBox("Leads & Clue Triage")
        leads_lay = QVBoxLayout(leads_box)
        self.leads_list = QListWidget()
        self._tune_list(self.leads_list)
        self.leads_list.itemDoubleClicked.connect(self._on_lead_double_clicked)
        self.leads_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.leads_list.customContextMenuRequested.connect(self._show_leads_context_menu)

        lead_btns = QHBoxLayout()
        self.btn_lead_open = QPushButton("Open")
        self.btn_lead_triage = QPushButton("Triage")
        self.btn_lead_ver = QPushButton("Mark Verified")
        self.btn_lead_false = QPushButton("Mark False")
        for b in (self.btn_lead_open, self.btn_lead_triage, self.btn_lead_ver, self.btn_lead_false):
            b.setAutoDefault(False)
        lead_btns.addWidget(self.btn_lead_open)
        lead_btns.addWidget(self.btn_lead_triage)
        lead_btns.addWidget(self.btn_lead_ver)
        lead_btns.addWidget(self.btn_lead_false)

        self.btn_lead_open.clicked.connect(self._emit_open_selected_lead)
        self.btn_lead_triage.clicked.connect(self._emit_triage_selected_lead)
        self.btn_lead_ver.clicked.connect(self._emit_mark_verified_selected_lead)
        self.btn_lead_false.clicked.connect(self._emit_mark_false_selected_lead)

        leads_lay.addWidget(self.leads_list)
        leads_lay.addLayout(lead_btns)

        # Right: Geospatial Snapshot
        geo_box = QGroupBox("Geospatial Snapshot")
        geo_lay = QVBoxLayout(geo_box)
        self.geo_lkp = QLabel("LKP: — (—)")
        self.geo_grids = QLabel("Priority Grids: —")
        self.geo_layers = QLabel("Layers: —")
        for lab in (self.geo_lkp, self.geo_grids, self.geo_layers):
            lab.setObjectName("GeoBadge")

        geo_btns = QHBoxLayout()
        self.btn_open_map = QPushButton("Open Map")
        geo_btns.addWidget(self.btn_open_map)
        self.btn_open_map.clicked.connect(self.openMapRequested)

        geo_lay.addWidget(self.geo_lkp)
        geo_lay.addWidget(self.geo_grids)
        geo_lay.addWidget(self.geo_layers)
        geo_lay.addLayout(geo_btns)

        mid.addWidget(leads_box, 2)
        mid.addWidget(geo_box, 1)
        outer.addLayout(mid)

        # Lower two-panels
        low = QHBoxLayout()
        low.setSpacing(10)

        subj_box = QGroupBox("Subject & Behavior")
        subj_lay = QVBoxLayout(subj_box)
        self.subj_line = QLabel("Profile: —  — Risk: —  — Model: —  — ISRID: —")
        self.subj_line.setObjectName("SubjectLine")
        self.btn_open_subject = QPushButton("Open Subject File")
        self.btn_open_subject.clicked.connect(self.openSubjectFileRequested)
        subj_lay.addWidget(self.subj_line)
        subj_lay.addWidget(self.btn_open_subject)

        prod_box = QGroupBox("Intel Products & IAP Inputs")
        prod_lay = QVBoxLayout(prod_box)
        self.prod_sitrep = QLabel("SITREP: —")
        self.prod_202 = QLabel("202: —")
        self.prod_215 = QLabel("215: —")
        self.prod_wx = QLabel("Wx Brief: —")
        for lab in (self.prod_sitrep, self.prod_202, self.prod_215, self.prod_wx):
            lab.setObjectName("ProductLine")
        prod_btns = QHBoxLayout()
        self.btn_open_sitrep = QPushButton("Open SITREP")
        self.btn_open_weather = QPushButton("Open Weather")
        self.btn_open_sitrep.clicked.connect(self.openSITREPRequested)
        self.btn_open_weather.clicked.connect(self.openWeatherRequested)
        prod_btns.addWidget(self.btn_open_sitrep)
        prod_btns.addWidget(self.btn_open_weather)
        prod_lay.addWidget(self.prod_sitrep)
        prod_lay.addWidget(self.prod_202)
        prod_lay.addWidget(self.prod_215)
        prod_lay.addWidget(self.prod_wx)
        prod_lay.addLayout(prod_btns)

        low.addWidget(subj_box, 1)
        low.addWidget(prod_box, 1)
        outer.addLayout(low)

        # Bottom actions row
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_new_report = QPushButton("New Intel Report")
        self.btn_new_lead = QPushButton("New Lead")
        self.btn_btm_open_map = QPushButton("Open Map")
        self.btn_btm_open_sitrep = QPushButton("Open SITREP")
        self.btn_export_summary = QPushButton("Export Intel Summary")
        self.btn_open_full = QPushButton("Open Full Intel")

        actions.addWidget(self.btn_new_report)
        actions.addWidget(self.btn_new_lead)
        actions.addWidget(self.btn_btm_open_map)
        actions.addWidget(self.btn_btm_open_sitrep)
        actions.addWidget(self.btn_export_summary)
        actions.addWidget(self.btn_open_full)

        self.btn_new_report.clicked.connect(self.newIntelReportRequested)
        self.btn_new_lead.clicked.connect(self.newLeadRequested)
        self.btn_btm_open_map.clicked.connect(self.openMapRequested)
        self.btn_btm_open_sitrep.clicked.connect(self.openSITREPRequested)
        self.btn_export_summary.clicked.connect(self.exportIntelSummaryRequested)
        self.btn_open_full.clicked.connect(self.openFullIntelRequested)

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
            QLabel#GeoBadge, QLabel#ProductLine, QLabel#SubjectLine {
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

    # Context menu for leads
    def _selected_lead_id(self) -> Optional[str]:
        it = self.leads_list.currentItem()
        if not it:
            return None
        return it.data(self._lead_id_role)

    def _show_leads_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        act_open = menu.addAction("Open")
        act_triage = menu.addAction("Triage")
        act_ver = menu.addAction("Mark Verified")
        act_false = menu.addAction("Mark False")
        act = menu.exec_(self.leads_list.mapToGlobal(pos))
        lead_id = self._selected_lead_id()
        if not lead_id:
            return
        if act == act_open:
            self.openLeadRequested.emit(lead_id)
        elif act == act_triage:
            self.triageLeadRequested.emit(lead_id)
        elif act == act_ver:
            self.markLeadVerifiedRequested.emit(lead_id)
        elif act == act_false:
            self.markLeadFalseRequested.emit(lead_id)

    def _on_lead_double_clicked(self, item: QListWidgetItem) -> None:
        lead_id = item.data(self._lead_id_role)
        if lead_id:
            self.openLeadRequested.emit(str(lead_id))

    def _emit_open_selected_lead(self) -> None:
        lead_id = self._selected_lead_id()
        if lead_id:
            self.openLeadRequested.emit(lead_id)

    def _emit_triage_selected_lead(self) -> None:
        lead_id = self._selected_lead_id()
        if lead_id:
            self.triageLeadRequested.emit(lead_id)

    def _emit_mark_verified_selected_lead(self) -> None:
        lead_id = self._selected_lead_id()
        if lead_id:
            self.markLeadVerifiedRequested.emit(lead_id)

    def _emit_mark_false_selected_lead(self) -> None:
        lead_id = self._selected_lead_id()
        if lead_id:
            self.markLeadFalseRequested.emit(lead_id)

    # Public slots / methods
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self.context_label.setText(f"OP: {op_period}  Now: {now_text}  Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict) -> None:
        mapping = {
            "new_reports": kpis.get("new_reports", "—"),
            "open_leads": kpis.get("open_leads", "—"),
            "verified_clues": kpis.get("verified_clues", "—"),
            "false_pos": kpis.get("false_pos", "—"),
            "priority_areas": kpis.get("priority_areas", "—"),
            "weather_brief_status": kpis.get("weather_brief_status", "—"),
        }
        for key, val in mapping.items():
            self.kpi_cards[key].set_value(val)

    @Slot(list)
    def update_alerts(self, alerts: List[Dict]) -> None:
        # Newest-first, limit to ~8
        self.alerts_list.clear()
        for a in alerts[:8]:
            ts = str(a.get("ts", "—"))
            text = str(a.get("text", ""))
            item = QListWidgetItem(f"{ts}  —  {text}")
            item.setToolTip(text)
            self.alerts_list.addItem(item)

    @Slot(list)
    def update_leads(self, leads: List[Dict]) -> None:
        self.leads_list.clear()
        for lead in leads[:6]:
            lid = str(lead.get("id", ""))
            title = str(lead.get("title", ""))
            src = str(lead.get("src", ""))
            prio = str(lead.get("priority", ""))
            status = str(lead.get("status", ""))
            text = f"{lid}  {title} — {prio} — {status}"
            tip = f"{lid}: {title}\nSource: {src}\nPriority: {prio}\nStatus: {status}"
            item = QListWidgetItem(text)
            item.setData(self._lead_id_role, lid)
            item.setToolTip(tip)
            self.leads_list.addItem(item)

    @Slot(dict)
    def update_geo_snapshot(self, geo: Dict) -> None:
        lkp = str(geo.get("lkp", "—"))
        last_update = str(geo.get("last_update", "—"))
        self.geo_lkp.setText(f"LKP: {lkp} ({last_update})")
        self.geo_grids.setText(f"Priority Grids: {geo.get('priority_grids', '—')}")
        layers = geo.get("layers", []) or []
        if isinstance(layers, list):
            layers_text = "  ".join(f"{name} ✓" for name in layers)
        else:
            layers_text = str(layers)
        self.geo_layers.setText(f"Layers: {layers_text if layers_text else '—'}")

    @Slot(dict)
    def update_subject(self, subject: Dict) -> None:
        profile = str(subject.get("subject_profile", "—"))
        risk = subject.get("risk_factors", "—")
        model = str(subject.get("behavior_model", "—"))
        isrid = str(subject.get("isrid_profile", "—"))
        self.subj_line.setText(
            f"Profile: {profile} — Risk: {risk} — Model: {model} — ISRID: {isrid}"
        )

    @Slot(dict)
    def update_products(self, prod: Dict) -> None:
        self.prod_sitrep.setText(f"SITREP: {prod.get('sitrep', '—')}")
        self.prod_202.setText(f"202: {prod.get('202_objectives', '—')} new objectives")
        self.prod_215.setText(f"215: {prod.get('215_risks', '—')} unresolved hazard(s)")
        self.prod_wx.setText(f"Wx Brief: {prod.get('weather', '—')}")

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


def make_intel_dashboard(parent: Optional[QWidget] = None) -> IntelDashboardWidget:
    return IntelDashboardWidget(parent)


if __name__ == "__main__":
    # Testing harness with demo data
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    w = IntelDashboardWidget()

    # Demo data
    kpis = {
        "new_reports": 5,
        "open_leads": 7,
        "verified_clues": 12,
        "false_pos": 4,
        "priority_areas": 3,
        "weather_brief_status": "Ready",
    }
    alerts = [
        {"ts": "14:18", "text": "New public sighting near East Lot (needs triage)"},
        {"ts": "14:10", "text": "Priority grid v7 published"},
    ]
    leads = [
        {
            "id": "CL-143",
            "title": "Footprint cast near East Gate",
            "src": "Team G-3",
            "priority": "HIGH",
            "status": "UNTRIAGED",
        },
        {
            "id": "LD-221",
            "title": "Drone thermal hit NW woodline",
            "src": "A-1",
            "priority": "CRITICAL",
            "status": "REVIEW",
        },
        {
            "id": "REP-090",
            "title": "Witness saw subject at 12:30",
            "src": "Public tip",
            "priority": "MED",
            "status": "OPEN",
        },
    ]
    geo = {
        "lkp": "42.54510, -111.49430",
        "last_update": "13:50",
        "priority_grids": "v7 (OP3)",
        "layers": ["Teams", "Tasks", "Hazards", "ADS-B"],
    }
    subject = {
        "subject_profile": "Adult hiker",
        "risk_factors": 2,
        "behavior_model": "Lost",
        "isrid_profile": "Class 2 / Forest",
    }
    prod = {
        "sitrep": "Draft ready",
        "202_objectives": 3,
        "215_risks": 1,
        "weather": "Ready (14:10)",
    }

    # Apply demo state
    w.update_kpis(kpis)
    w.update_alerts(alerts)
    w.update_leads(leads)
    w.update_geo_snapshot(geo)
    w.update_subject(subject)
    w.update_products(prod)
    w.set_context("3", "14:22", "Intel Chief")
    w.setAutoRefresh(15000)

    w.resize(QSize(1100, 800))
    w.show()

    sys.exit(app.exec())
