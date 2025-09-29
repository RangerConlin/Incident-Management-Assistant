"""
Menu wiring instructions for adding Public Affairs — Dashboard

1) In the main window’s “Public Affairs” menu, create a single QAction named:
     "Public Affairs Dashboard"
   and connect it to a slot: open_public_affairs_dashboard()

2) open_public_affairs_dashboard() should create/show PublicAffairsDashboardWidget (modeless),
   call setAutoRefresh(15000), and connect refreshRequested to a controller slot.

3) REMOVE any older placeholders or duplicate menu items for Public Affairs dashboards.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QFrame,
    QMenu,
    QSizePolicy,
    QSpacerItem,
)


class PublicAffairsDashboardWidget(QWidget):
    """Public Affairs — Dashboard main presentation widget (no I/O).

    Purely a UI presentation component. Exposes signals for user actions and
    public methods (slots) to update contents from external controllers.
    """

    # Top-level action signals
    openQueueRequested = Signal()
    acknowledgeAlertsRequested = Signal()

    # Inquiry actions
    openInquiryRequested = Signal(str)
    assignInquiryRequested = Signal(str)
    respondInquiryRequested = Signal(str)

    # Release actions
    openDraftRequested = Signal(str)
    approveReleaseRequested = Signal(str)
    publishReleaseRequested = Signal(str)

    # Lower panel actions
    openSocialSchedulerRequested = Signal()
    openWebsiteCMSRequested = Signal()
    openRumorBoardRequested = Signal()

    # Bottom actions row
    newPressReleaseRequested = Signal()
    newMediaResponseRequested = Signal()
    scheduleSocialPostRequested = Signal()
    openBriefingPlannerRequested = Signal()
    exportPublicInfoSummaryRequested = Signal()
    openFullPublicAffairsRequested = Signal()

    # Auto-refresh
    refreshRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PublicAffairsDashboardWidget")
        self._kpi_values: dict[str, QLabel] = {}
        self._refreshTimer = QTimer(self)
        self._refreshTimer.setSingleShot(False)
        self._refreshTimer.timeout.connect(self.refreshRequested)

        self._build_ui()
        self._apply_styles()

    # ----- UI construction -----
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)
        self.titleLabel = QLabel("Public Affairs — Dashboard", self)
        self.titleLabel.setObjectName("dashboardTitle")

        self.contextLabel = QLabel("OP: —  Now: —  Role: —", self)
        self.contextLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.contextLabel.setObjectName("contextLabel")

        header.addWidget(self.titleLabel, 1)
        header.addWidget(self.contextLabel, 0)
        root.addLayout(header)

        # Incident overlay banner (shown when no active incident)
        self.overlayBanner = QFrame(self)
        self.overlayBanner.setObjectName("overlayBanner")
        overlay_layout = QHBoxLayout(self.overlayBanner)
        overlay_layout.setContentsMargins(10, 8, 10, 8)
        overlay_layout.setSpacing(8)
        overlay_msg = QLabel("No active incident — select or create one.", self.overlayBanner)
        overlay_layout.addWidget(overlay_msg)
        self.overlayBanner.setVisible(False)
        root.addWidget(self.overlayBanner)

        # KPI row (6 pills)
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(8)
        kpi_grid.setVerticalSpacing(8)

        kpis = [
            ("releases_pending", "Releases Pending"),
            ("media_inquiries", "Media Inquiries"),
            ("social_queued", "Social Queued"),
            ("rumors_to_address", "Rumors To Address"),
            ("briefings_today", "Briefings Today"),
            ("jic_status", "JIC Status"),
        ]

        for i, (key, label) in enumerate(kpis):
            pill = self._make_kpi_pill(label)
            self._kpi_values[key] = pill.findChild(QLabel, "kpiValue")
            kpi_grid.addWidget(pill, 0, i)
        root.addLayout(kpi_grid)

        # Alerts bar
        alerts_frame = QFrame(self)
        alerts_layout = QVBoxLayout(alerts_frame)
        alerts_layout.setContentsMargins(8, 8, 8, 8)
        alerts_layout.setSpacing(6)

        alerts_top = QHBoxLayout()
        alerts_label = QLabel("Alerts (public-affairs, last 30 min)", alerts_frame)
        self.alertsOpenBtn = QPushButton("Open Queue ▸", alerts_frame)
        self.alertsAckBtn = QPushButton("Acknowledge", alerts_frame)
        self.alertsOpenBtn.clicked.connect(self.openQueueRequested)
        self.alertsAckBtn.clicked.connect(self.acknowledgeAlertsRequested)

        alerts_top.addWidget(alerts_label)
        alerts_top.addStretch(1)
        alerts_top.addWidget(self.alertsOpenBtn)
        alerts_top.addWidget(self.alertsAckBtn)

        self.alertsList = QListWidget(alerts_frame)
        self._prepare_listwidget(self.alertsList)

        alerts_layout.addLayout(alerts_top)
        alerts_layout.addWidget(self.alertsList)
        root.addWidget(alerts_frame)

        # Two-column middle
        middle = QHBoxLayout()
        middle.setSpacing(10)

        # Left panel: Media Inquiries
        self.inquiriesPanel = self._make_panel("Media Inquiries Queue")
        inquiries_v = self.inquiriesPanel.layout()  # type: ignore[assignment]
        self.inquiriesList = QListWidget(self.inquiriesPanel)
        self._prepare_listwidget(self.inquiriesList)
        self.inquiriesList.itemDoubleClicked.connect(self._on_inquiry_double_clicked)
        self.inquiriesList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.inquiriesList.customContextMenuRequested.connect(self._on_inquiries_context_menu)

        inquiries_buttons = QHBoxLayout()
        self.inquiriesOpenBtn = QPushButton("Open", self.inquiriesPanel)
        self.inquiriesAssignBtn = QPushButton("Assign", self.inquiriesPanel)
        self.inquiriesRespondBtn = QPushButton("Respond", self.inquiriesPanel)
        self.inquiriesOpenBtn.clicked.connect(lambda: self._emit_for_selected(self.inquiriesList, self.openInquiryRequested))
        self.inquiriesAssignBtn.clicked.connect(lambda: self._emit_for_selected(self.inquiriesList, self.assignInquiryRequested))
        self.inquiriesRespondBtn.clicked.connect(lambda: self._emit_for_selected(self.inquiriesList, self.respondInquiryRequested))
        inquiries_buttons.addWidget(self.inquiriesOpenBtn)
        inquiries_buttons.addWidget(self.inquiriesAssignBtn)
        inquiries_buttons.addWidget(self.inquiriesRespondBtn)

        inquiries_v.addWidget(self.inquiriesList)
        inquiries_v.addLayout(inquiries_buttons)

        # Right panel: Public Information Releases
        self.releasesPanel = self._make_panel("Public Information Releases")
        releases_v = self.releasesPanel.layout()  # type: ignore[assignment]
        self.releasesList = QListWidget(self.releasesPanel)
        self._prepare_listwidget(self.releasesList)
        self.releasesList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.releasesList.customContextMenuRequested.connect(self._on_releases_context_menu)

        releases_buttons = QHBoxLayout()
        self.releasesOpenDraftBtn = QPushButton("Open Draft", self.releasesPanel)
        self.releasesApproveBtn = QPushButton("Approve", self.releasesPanel)
        self.releasesPublishBtn = QPushButton("Publish", self.releasesPanel)
        self.releasesOpenDraftBtn.clicked.connect(lambda: self._emit_for_selected(self.releasesList, self.openDraftRequested))
        self.releasesApproveBtn.clicked.connect(lambda: self._emit_for_selected(self.releasesList, self.approveReleaseRequested))
        self.releasesPublishBtn.clicked.connect(lambda: self._emit_for_selected(self.releasesList, self.publishReleaseRequested))
        releases_buttons.addWidget(self.releasesOpenDraftBtn)
        releases_buttons.addWidget(self.releasesApproveBtn)
        releases_buttons.addWidget(self.releasesPublishBtn)

        releases_v.addWidget(self.releasesList)
        releases_v.addLayout(releases_buttons)

        middle.addWidget(self.inquiriesPanel, 1)
        middle.addWidget(self.releasesPanel, 1)
        root.addLayout(middle)

        # Lower two-panels
        lower = QHBoxLayout()
        lower.setSpacing(10)

        # Left: Social & Channels Snapshot
        self.socialPanel = self._make_panel("Social & Channels Snapshot")
        social_v = self.socialPanel.layout()  # type: ignore[assignment]
        self.socialSnapshot = QFrame(self.socialPanel)
        self.socialSnapshot.setProperty("badge", True)
        snap_h = QHBoxLayout(self.socialSnapshot)
        snap_h.setContentsMargins(8, 6, 8, 6)
        snap_h.setSpacing(6)
        self.socialSnapshotLabel = QLabel("", self.socialSnapshot)
        self.socialSnapshotLabel.setObjectName("socialSnapshotLabel")
        snap_h.addWidget(self.socialSnapshotLabel, 1)
        social_buttons = QHBoxLayout()
        self.openSocialSchedulerBtn = QPushButton("Open Social Scheduler", self.socialPanel)
        self.openWebsiteCMSBtn = QPushButton("Open Website CMS", self.socialPanel)
        self.openSocialSchedulerBtn.clicked.connect(self.openSocialSchedulerRequested)
        self.openWebsiteCMSBtn.clicked.connect(self.openWebsiteCMSRequested)
        social_buttons.addWidget(self.openSocialSchedulerBtn)
        social_buttons.addWidget(self.openWebsiteCMSBtn)
        social_v.addWidget(self.socialSnapshot)
        social_v.addLayout(social_buttons)

        # Right: Rumor Control & Monitoring
        self.rumorPanel = self._make_panel("Rumor Control & Monitoring")
        rumor_v = self.rumorPanel.layout()  # type: ignore[assignment]
        self.rumorList = QListWidget(self.rumorPanel)
        self._prepare_listwidget(self.rumorList)
        rumor_btns = QHBoxLayout()
        self.openRumorBoardBtn = QPushButton("Open Rumor Board", self.rumorPanel)
        self.openRumorBoardBtn.clicked.connect(self.openRumorBoardRequested)
        rumor_btns.addWidget(self.openRumorBoardBtn)
        rumor_v.addWidget(self.rumorList)
        rumor_v.addLayout(rumor_btns)

        lower.addWidget(self.socialPanel, 1)
        lower.addWidget(self.rumorPanel, 1)
        root.addLayout(lower)

        # Bottom actions row
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.newPressReleaseBtn = QPushButton("New Press Release", self)
        self.newMediaResponseBtn = QPushButton("New Media Response", self)
        self.scheduleSocialPostBtn = QPushButton("Schedule Social Post", self)
        self.openBriefingPlannerBtn = QPushButton("Open Briefing Planner", self)
        self.exportPublicInfoSummaryBtn = QPushButton("Export Public Info Summary", self)
        self.openFullPublicAffairsBtn = QPushButton("Open Full Public Affairs", self)

        self.newPressReleaseBtn.clicked.connect(self.newPressReleaseRequested)
        self.newMediaResponseBtn.clicked.connect(self.newMediaResponseRequested)
        self.scheduleSocialPostBtn.clicked.connect(self.scheduleSocialPostRequested)
        self.openBriefingPlannerBtn.clicked.connect(self.openBriefingPlannerRequested)
        self.exportPublicInfoSummaryBtn.clicked.connect(self.exportPublicInfoSummaryRequested)
        self.openFullPublicAffairsBtn.clicked.connect(self.openFullPublicAffairsRequested)

        for b in (
            self.newPressReleaseBtn,
            self.newMediaResponseBtn,
            self.scheduleSocialPostBtn,
            self.openBriefingPlannerBtn,
            self.exportPublicInfoSummaryBtn,
            self.openFullPublicAffairsBtn,
        ):
            actions.addWidget(b)
        actions.addStretch(1)

        root.addLayout(actions)

    def _prepare_listwidget(self, lw: QListWidget) -> None:
        lw.setAlternatingRowColors(False)
        lw.setSelectionMode(QListWidget.SingleSelection)
        lw.setUniformItemSizes(True)
        lw.setWordWrap(False)
        lw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lw.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        lw.setEditTriggers(QListWidget.NoEditTriggers)

    def _make_panel(self, title: str) -> QFrame:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        lbl = QLabel(title, frame)
        lbl.setObjectName("sectionTitle")
        layout.addWidget(lbl)
        return frame

    def _make_kpi_pill(self, label_text: str) -> QFrame:
        pill = QFrame(self)
        pill.setProperty("kpi", True)
        v = QVBoxLayout(pill)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(0)
        value = QLabel("—", pill)
        value.setObjectName("kpiValue")
        value.setProperty("kpiValue", True)
        label = QLabel(label_text, pill)
        label.setProperty("kpiLabel", True)
        v.addWidget(value)
        v.addWidget(label)
        return pill

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            #PublicAffairsDashboardWidget { background: #f6f7f9; }

            QLabel#dashboardTitle { font-size: 18px; font-weight: 600; }
            QLabel#contextLabel { color: #444; }

            QFrame[kpi="true"] {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #dddddd;
            }
            QLabel[kpiValue="true"] {
                font-size: 20px;
                font-weight: 600;
                color: #1a1a1a;
            }
            QLabel[kpiLabel="true"] {
                color: #666666;
                font-size: 11px;
            }

            QLabel#sectionTitle, QLabel#sectionTitle QLabel {
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#sectionTitle { /* fallback selector if used */ }
            QLabel[objectName="sectionTitle"] { /* ensure consistent title style */ }

            QFrame[badge="true"] {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }

            QFrame#overlayBanner {
                background: #fff7da;
                border: 1px solid #f0d47c;
                border-radius: 8px;
            }
        """
        )

    # ----- Slots / public methods -----
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self.contextLabel.setText(f"OP: {op_period}  Now: {now_text}  Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict[str, Any]) -> None:
        for key, lbl in self._kpi_values.items():
            val = kpis.get(key, "—")
            lbl.setText(str(val))

    @Slot(list)
    def update_alerts(self, alerts: List[Dict[str, str]]) -> None:
        self.alertsList.clear()
        # newest-first, limit ~8
        for a in list(alerts)[-8:][::-1]:
            ts = a.get("ts", "—")
            text = a.get("text", "")
            s = f"[{ts}] {text}"
            item = QListWidgetItem(s)
            item.setToolTip(s)
            self.alertsList.addItem(item)

    @Slot(list)
    def update_inquiries(self, items: List[Dict[str, str]]) -> None:
        self.inquiriesList.clear()
        for d in items[:6]:
            iid = d.get("id", "")
            outlet = d.get("outlet", "")
            topic = d.get("topic", "")
            priority = d.get("priority", "")
            status = d.get("status", "")
            text = f"{iid}  {outlet} — {topic} — {priority} — {status}"
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, iid)
            it.setToolTip(text)
            self.inquiriesList.addItem(it)

    @Slot(list)
    def update_releases(self, items: List[Dict[str, str]]) -> None:
        self.releasesList.clear()
        for d in items[:6]:
            rid = d.get("id", "")
            title = d.get("title", "")
            rtype = d.get("type", "")
            status = d.get("status", "")
            text = f"{rid}  {title} — {rtype} — {status}"
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, rid)
            it.setToolTip(text)
            self.releasesList.addItem(it)

    @Slot(dict)
    def update_social_snapshot(self, snap: Dict[str, Any]) -> None:
        channels = snap.get("channels", [])
        scheduled = snap.get("scheduled", "—")
        last_post = snap.get("last_post", "—")
        reach_today = snap.get("reach_today", "—")
        ch_txt = " / ".join(map(str, channels)) if isinstance(channels, list) else str(channels)
        txt = (
            f"Channels: {ch_txt} — Scheduled: {scheduled} — "
            f"Last post {last_post} — Reach: {reach_today}"
        )
        self.socialSnapshotLabel.setText(txt)
        self.socialSnapshot.setToolTip(txt)

    @Slot(list)
    def update_rumors(self, items: List[Dict[str, str]]) -> None:
        self.rumorList.clear()
        for d in items[:6]:
            rid = d.get("id", "")
            text = d.get("text", "")
            status = d.get("status", "")
            s = f"{rid}  {text} — {status}"
            it = QListWidgetItem(s)
            it.setData(Qt.UserRole, rid)
            it.setToolTip(s)
            self.rumorList.addItem(it)

    @Slot(bool)
    def setIncidentOverlayVisible(self, visible: bool) -> None:  # noqa: N802 (Qt naming)
        self.overlayBanner.setVisible(bool(visible))

    @Slot(int)
    def setAutoRefresh(self, interval_ms: int) -> None:  # noqa: N802 (Qt naming)
        if isinstance(interval_ms, int) and interval_ms > 0:
            self._refreshTimer.start(int(interval_ms))
        else:
            self._refreshTimer.stop()

    # ----- Event handlers / helpers -----
    def _emit_for_selected(self, lw: QListWidget, sig: Signal) -> None:
        it = lw.currentItem()
        if it is None:
            return
        ident = it.data(Qt.UserRole)
        if isinstance(ident, str):
            sig.emit(ident)

    def _on_inquiry_double_clicked(self, item: QListWidgetItem) -> None:
        ident = item.data(Qt.UserRole)
        if isinstance(ident, str):
            self.openInquiryRequested.emit(ident)

    def _on_inquiries_context_menu(self, pos: QPoint) -> None:
        item = self.inquiriesList.itemAt(pos)
        if item is None:
            return
        ident = item.data(Qt.UserRole)
        if not isinstance(ident, str):
            return
        menu = QMenu(self)
        act_open = menu.addAction("Open")
        act_assign = menu.addAction("Assign")
        act_respond = menu.addAction("Respond")
        act = menu.exec_(self.inquiriesList.mapToGlobal(pos))
        if act is act_open:
            self.openInquiryRequested.emit(ident)
        elif act is act_assign:
            self.assignInquiryRequested.emit(ident)
        elif act is act_respond:
            self.respondInquiryRequested.emit(ident)

    def _on_releases_context_menu(self, pos: QPoint) -> None:
        item = self.releasesList.itemAt(pos)
        if item is None:
            return
        ident = item.data(Qt.UserRole)
        if not isinstance(ident, str):
            return
        menu = QMenu(self)
        act_open = menu.addAction("Open Draft")
        act_approve = menu.addAction("Approve")
        act_publish = menu.addAction("Publish")
        act = menu.exec_(self.releasesList.mapToGlobal(pos))
        if act is act_open:
            self.openDraftRequested.emit(ident)
        elif act is act_approve:
            self.approveReleaseRequested.emit(ident)
        elif act is act_publish:
            self.publishReleaseRequested.emit(ident)


def make_public_affairs_dashboard(parent: Optional[QWidget] = None) -> PublicAffairsDashboardWidget:
    return PublicAffairsDashboardWidget(parent)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    w = PublicAffairsDashboardWidget()
    w.resize(1100, 800)

    # Demo data
    kpis = {
        "releases_pending": 2,
        "media_inquiries": 4,
        "social_queued": 5,
        "rumors_to_address": 3,
        "briefings_today": 1,
        "jic_status": "Active",
    }
    alerts = [
        {"ts": "15:05", "text": "Channel 7 request for on-camera at 16:00"},
        {"ts": "14:58", "text": "Rumor trending: ‘teams blocked hospital access’"},
    ]
    inquiries = [
        {"id": "MI-204", "outlet": "Channel 7", "topic": "status update request", "priority": "HIGH", "status": "UNASSIGNED"},
        {"id": "MI-205", "outlet": "County Press", "topic": "road closures", "priority": "MED", "status": "ASSIGNED"},
    ]
    releases = [
        {"id": "PR-017", "title": "OP3 morning update", "type": "PRESS RELEASE", "status": "DRAFT"},
        {"id": "ST-004", "title": "Situation Status", "type": "SITSTAT", "status": "READY"},
    ]
    social = {"channels": ["X", "Facebook", "Website"], "scheduled": 5, "last_post": "14:10", "reach_today": "12.4k"}
    rumors = [
        {"id": "RU-033", "text": "‘Helicopters caused the fire’", "status": "NEEDS RESPONSE"},
        {"id": "RU-029", "text": "‘Incident near water supply’", "status": "MONITORING"},
    ]

    # Wire demo
    w.update_kpis(kpis)
    w.update_alerts(alerts)
    w.update_inquiries(inquiries)
    w.update_releases(releases)
    w.update_social_snapshot(social)
    w.update_rumors(rumors)
    w.set_context("3", "15:06", "Public Information Officer")
    w.setAutoRefresh(15000)
    w.show()

    sys.exit(app.exec())

