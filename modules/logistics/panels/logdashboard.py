"""
Menu wiring instructions (Logistics Dashboard):

1) In the main window's "Logistics" menu, create a single QAction named:
     "Logistics Dashboard"
   and connect it to a slot: open_logistics_dashboard()

2) open_logistics_dashboard() should create/show LogisticsDashboardWidget (modeless),
   set auto-refresh, and connect refreshRequested to the controller.

3) REMOVE any older placeholders or duplicate menu items for Logistics dashboard.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QToolButton,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QSizePolicy,
    QStackedLayout,
    QApplication,
)

from utils.styles import get_palette, subscribe_theme


def _tone_colors(pal: Dict[str, object]) -> Dict[str, str]:
    """Semantic tone -> hex, sourced entirely from the active palette."""
    return {
        "ok": pal.get("success", pal.get("accent_alt")).name(),
        "low": pal.get("warning").name(),
        "crit": pal.get("danger", pal.get("error")).name(),
        "info": pal.get("info", pal.get("accent")).name(),
        "neutral": pal.get("fg_muted", pal.get("muted")).name(),
    }


class _Card(QFrame):
    """Flat, bordered panel used as the base container for every dashboard block."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setAttribute(Qt.WA_StyledBackground, True)


class _CardHeader(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("cardHeader", True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)
        self._title = QLabel(title)
        self._title.setProperty("cardTitle", True)
        lay.addWidget(self._title)
        lay.addStretch(1)
        self._actions = lay

    def add_action(self, widget: QWidget) -> None:
        self._actions.addWidget(widget)


def _flat_button(text: str, icon: str = "") -> QPushButton:
    label = f"{icon}  {text}" if icon else text
    btn = QPushButton(label)
    btn.setProperty("flatBtn", True)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def _pill(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("pill", True)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class _Kpi(QFrame):
    """A single clickable metric tile in the top KPI strip."""

    clicked = Signal()

    def __init__(self, label_text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("kpi", True)
        self.setProperty("tone", "neutral")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self._value = QLabel("—")
        self._value.setProperty("kpiValue", True)
        self._label = QLabel(label_text)
        self._label.setProperty("kpiLabel", True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        lay.addWidget(self._value)
        lay.addWidget(self._label)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _AlertRow(QFrame):
    acknowledged = Signal(str)

    def __init__(self, alert_id: str, severity: str, text: str, ts: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._alert_id = alert_id
        self.setProperty("row", True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(10)

        stripe = QFrame()
        stripe.setProperty("stripe", True)
        stripe.setProperty("tone", severity)
        stripe.setFixedWidth(4)
        lay.addWidget(stripe)

        text_lbl = QLabel(text)
        text_lbl.setProperty("rowText", True)
        text_lbl.setWordWrap(False)
        lay.addWidget(text_lbl, 1)

        ts_lbl = QLabel(ts)
        ts_lbl.setProperty("rowMeta", True)
        lay.addWidget(ts_lbl)

        self._btn = _flat_button("Acknowledge")
        self._btn.setProperty("small", True)
        self._btn.clicked.connect(self._on_ack)
        lay.addWidget(self._btn)

    def _on_ack(self) -> None:
        self.setEnabled(False)
        self.setProperty("acked", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self._btn.setText("Acknowledged")
        self.acknowledged.emit(self._alert_id)


class _ActionRow(QFrame):
    openRequested = Signal(str)
    approveRequested = Signal(str)
    assignRequested = Signal(str)

    def __init__(
        self,
        action_id: str,
        priority: str,
        title: str,
        subtitle: str,
        kind: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._action_id = action_id
        self.setProperty("row", True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(10)

        tone = {"critical": "crit", "high": "low", "routine": "info"}.get(priority.lower(), "neutral")
        badge = _pill(priority)
        badge.setProperty("tone", tone)
        lay.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setProperty("rowText", True)
        text_col.addWidget(title_lbl)
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setProperty("rowMeta", True)
            text_col.addWidget(sub_lbl)
        lay.addLayout(text_col, 1)

        open_btn = _flat_button("Open")
        open_btn.setProperty("small", True)
        open_btn.clicked.connect(lambda: self.openRequested.emit(self._action_id))
        lay.addWidget(open_btn)

        if kind == "approve":
            approve_btn = _flat_button("Approve")
            approve_btn.setProperty("small", True)
            approve_btn.setProperty("tone", "ok")
            approve_btn.clicked.connect(lambda: self.approveRequested.emit(self._action_id))
            lay.addWidget(approve_btn)
        else:
            assign_btn = _flat_button("Assign")
            assign_btn.setProperty("small", True)
            assign_btn.clicked.connect(lambda: self.assignRequested.emit(self._action_id))
            lay.addWidget(assign_btn)


class _DemobRow(QFrame):
    checkInRequested = Signal(str)

    def __init__(self, item_id: str, title: str, due: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._item_id = item_id
        self.setProperty("row", True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setProperty("rowText", True)
        text_col.addWidget(title_lbl)
        due_lbl = QLabel(due)
        due_lbl.setProperty("rowMeta", True)
        text_col.addWidget(due_lbl)
        lay.addLayout(text_col, 1)

        btn = _flat_button("Check in")
        btn.setProperty("small", True)
        btn.clicked.connect(lambda: self.checkInRequested.emit(self._item_id))
        lay.addWidget(btn)


class _Badge(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("badge", True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._dot = QLabel("●")
        self._dot.setObjectName("badge_dot")
        self._text = QLabel(title + " — —")
        self._text.setObjectName("badge_text")
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(6)
        h.addWidget(self._dot)
        h.addWidget(self._text, 1)

    def set_state(self, state_text: str) -> None:
        st = (state_text or "").strip().lower()
        if st.startswith("ok"):
            self.setProperty("state", "ok")
        elif st.startswith("low"):
            self.setProperty("state", "low")
        else:
            self.setProperty("state", "crit")
        self.style().unpolish(self)
        self.style().polish(self)
        prefix = self._text.text().split(" — ", 1)[0]
        self._text.setText(f"{prefix} — {state_text}")

    def set_text_value(self, value_text: str) -> None:
        prefix = self._text.text().split(" — ", 1)[0]
        self._text.setText(f"{prefix} — {value_text}")


class LogisticsDashboardWidget(QWidget):
    """Logistics section dashboard.

    Card-based operational snapshot for the Logistics Section Chief: open
    requests, alerts, top actions, resource/facility snapshot, supply &
    comms health, and the demob/returns queue.
    """

    # Signals
    openActionRequested = Signal(str)
    approveRequested = Signal(str)
    assignRequested = Signal(str)
    openQueueRequested = Signal()
    acknowledgeAlertsRequested = Signal()
    alertAcknowledged = Signal(str)
    openSuppliesRequested = Signal()
    openCommsCacheRequested = Signal()
    openDemobBoardRequested = Signal()
    demobCheckInRequested = Signal(str)
    bulkImportRequested = Signal()
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
        self.setObjectName("LogisticsDashboardRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self.refreshRequested)

        self._kpi_widgets: Dict[str, _Kpi] = {}
        self._badges: Dict[str, _Badge] = {}
        self._alert_seq = 0
        self._action_seq = 0
        self._demob_seq = 0

        self._build_ui()
        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

    # --------------------- UI Construction ---------------------
    def _build_ui(self) -> None:
        self._stack = QStackedLayout(self)

        overlay_page = QWidget()
        overlay_page.setObjectName("LogisticsOverlayPage")
        overlay_page.setAttribute(Qt.WA_StyledBackground, True)
        ovl_layout = QVBoxLayout(overlay_page)
        ovl_layout.setContentsMargins(20, 20, 20, 20)
        ovl_layout.addStretch(1)
        self._overlay_label = QLabel("No active incident — select or create one.")
        self._overlay_label.setAlignment(Qt.AlignCenter)
        self._overlay_label.setObjectName("overlay_label")
        ovl_layout.addWidget(self._overlay_label)
        ovl_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("LogisticsScroll")

        main_page = QWidget()
        main_page.setObjectName("LogisticsMainPage")
        main_page.setAttribute(Qt.WA_StyledBackground, True)
        root = QVBoxLayout(main_page)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(14)

        # Header row
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        eyebrow = QLabel("Logistics section")
        eyebrow.setObjectName("eyebrow")
        self._title = QLabel("Dashboard")
        self._title.setObjectName("title")
        title_col.addWidget(eyebrow)
        title_col.addWidget(self._title)
        header.addLayout(title_col)
        header.addStretch(1)
        self._context = QLabel("OP: —  Now: —  Role: —")
        self._context.setObjectName("context")
        self._context.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self._context)
        root.addLayout(header)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        def add_kpi(key: str, label: str, click_signal: Optional[Signal] = None) -> None:
            kpi = _Kpi(label)
            self._kpi_widgets[key] = kpi
            if click_signal is not None:
                kpi.clicked.connect(click_signal)
            kpi_row.addWidget(kpi)

        add_kpi("open_requests", "Open requests", self.openQueueRequested)
        add_kpi("approvals_pending", "Approvals pending", self.openQueueRequested)
        add_kpi("low_stock_alerts", "Low stock alerts")
        add_kpi("checkins_today", "Check-ins today")
        add_kpi("vehicles_ready", "Vehicles ready")
        add_kpi("facilities_ok", "Facilities OK")
        root.addLayout(kpi_row)

        # Alerts card
        alerts_card = _Card()
        alerts_lay = QVBoxLayout(alerts_card)
        alerts_lay.setContentsMargins(0, 0, 0, 0)
        alerts_lay.setSpacing(0)
        alerts_header = _CardHeader("Alerts · last 30 min")
        self._btn_open_queue = _flat_button("Open queue")
        alerts_header.add_action(self._btn_open_queue)
        alerts_lay.addWidget(alerts_header)
        self._alerts_col = QVBoxLayout()
        self._alerts_col.setContentsMargins(0, 0, 0, 0)
        self._alerts_col.setSpacing(0)
        alerts_body = QWidget()
        alerts_body.setLayout(self._alerts_col)
        alerts_lay.addWidget(alerts_body)
        root.addWidget(alerts_card)

        # Two-column middle
        mid = QHBoxLayout()
        mid.setSpacing(14)

        actions_card = _Card()
        actions_lay = QVBoxLayout(actions_card)
        actions_lay.setContentsMargins(0, 0, 0, 0)
        actions_lay.setSpacing(0)
        actions_header = _CardHeader("Top logistics actions")
        self._btn_bulk_import = _flat_button("Bulk import")
        actions_header.add_action(self._btn_bulk_import)
        actions_lay.addWidget(actions_header)
        self._actions_col = QVBoxLayout()
        self._actions_col.setContentsMargins(0, 0, 0, 0)
        self._actions_col.setSpacing(0)
        actions_body = QWidget()
        actions_body.setLayout(self._actions_col)
        actions_lay.addWidget(actions_body)

        snap_card = _Card()
        snap_lay = QVBoxLayout(snap_card)
        snap_lay.setContentsMargins(0, 0, 0, 0)
        snap_lay.setSpacing(0)
        snap_lay.addWidget(_CardHeader("Resource & facility snapshot"))
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(14, 10, 14, 12)
        grid.setHorizontalSpacing(1)
        grid.setVerticalSpacing(1)

        def add_snap(row: int, col: int, title: str) -> QLabel:
            tile = QFrame()
            tile.setProperty("statTile", True)
            tile.setAttribute(Qt.WA_StyledBackground, True)
            tlay = QVBoxLayout(tile)
            tlay.setContentsMargins(10, 8, 10, 8)
            tlay.setSpacing(1)
            t_lbl = QLabel(title)
            t_lbl.setProperty("statLabel", True)
            v_lbl = QLabel("—")
            v_lbl.setProperty("statValue", True)
            tlay.addWidget(t_lbl)
            tlay.addWidget(v_lbl)
            grid.addWidget(tile, row, col)
            return v_lbl

        self._snap_checkins_total = add_snap(0, 0, "Personnel checked in")
        self._snap_missing_serials = add_snap(0, 1, "ICS-218 missing serials")
        self._snap_veh_ready = add_snap(1, 0, "Vehicles ready")
        self._snap_veh_assigned = add_snap(1, 1, "Vehicles assigned")
        self._snap_veh_oos = add_snap(2, 0, "Vehicles OOS")
        self._snap_facilities = add_snap(2, 1, "Facilities open")
        snap_lay.addWidget(grid_wrap)

        mid.addWidget(actions_card, 13)
        mid.addWidget(snap_card, 10)
        root.addLayout(mid)

        # Lower two-panels
        lower = QHBoxLayout()
        lower.setSpacing(14)

        health_card = _Card()
        h_lay = QVBoxLayout(health_card)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(0)
        health_header = _CardHeader("Supply & comms health")
        self._btn_open_supplies = _flat_button("Open supplies")
        self._btn_open_comms = _flat_button("Open comms cache")
        health_header.add_action(self._btn_open_supplies)
        health_header.add_action(self._btn_open_comms)
        h_lay.addWidget(health_header)

        badges_wrap = QWidget()
        badges_grid = QGridLayout(badges_wrap)
        badges_grid.setContentsMargins(14, 10, 14, 12)
        badges_grid.setHorizontalSpacing(8)
        badges_grid.setVerticalSpacing(8)
        for idx, (key, title) in enumerate((
            ("ppe", "PPE"),
            ("medical", "Medical"),
            ("water", "Water"),
            ("fuel", "Fuel"),
            ("comms_cache", "Comms cache"),
            ("spare_radios", "Spare radios"),
        )):
            b = _Badge(title)
            self._badges[key] = b
            badges_grid.addWidget(b, idx // 2, idx % 2)
        h_lay.addWidget(badges_wrap)

        demob_card = _Card()
        d_lay = QVBoxLayout(demob_card)
        d_lay.setContentsMargins(0, 0, 0, 0)
        d_lay.setSpacing(0)
        demob_header = _CardHeader("Demob / returns queue")
        self._btn_open_demob = _flat_button("Open demob board")
        demob_header.add_action(self._btn_open_demob)
        d_lay.addWidget(demob_header)
        self._demob_col = QVBoxLayout()
        self._demob_col.setContentsMargins(0, 0, 0, 0)
        self._demob_col.setSpacing(0)
        demob_body = QWidget()
        demob_body.setLayout(self._demob_col)
        d_lay.addWidget(demob_body)

        lower.addWidget(health_card, 1)
        lower.addWidget(demob_card, 1)
        root.addLayout(lower)

        # Quick actions toolbar
        quick = QHBoxLayout()
        quick.setSpacing(8)
        self._btn_new_213rr = _flat_button("New 213RR")
        self._btn_new_checkin = _flat_button("New check-in")
        self._btn_open_211_218 = _flat_button("Open 211/218")
        self._btn_print_204 = _flat_button("Print 204 support")
        self._btn_export_214 = _flat_button("Export 214")
        self._btn_open_full = _flat_button("Open full dashboard")
        for b in (
            self._btn_new_213rr,
            self._btn_new_checkin,
            self._btn_open_211_218,
            self._btn_print_204,
            self._btn_export_214,
        ):
            quick.addWidget(b)
        quick.addStretch(1)
        quick.addWidget(self._btn_open_full)
        root.addLayout(quick)
        root.addStretch(1)

        scroll.setWidget(main_page)

        # Wire buttons to signals
        self._btn_open_queue.clicked.connect(self.openQueueRequested)
        self._btn_bulk_import.clicked.connect(self.bulkImportRequested)
        self._btn_open_supplies.clicked.connect(self.openSuppliesRequested)
        self._btn_open_comms.clicked.connect(self.openCommsCacheRequested)
        self._btn_open_demob.clicked.connect(self.openDemobBoardRequested)
        self._btn_new_213rr.clicked.connect(self.new213RRRequested)
        self._btn_new_checkin.clicked.connect(self.newCheckInRequested)
        self._btn_open_211_218.clicked.connect(self.open211_218Requested)
        self._btn_print_204.clicked.connect(self.print204SupportRequested)
        self._btn_export_214.clicked.connect(self.export214Requested)
        self._btn_open_full.clicked.connect(self.openFullDashboardRequested)

        self._stack.addWidget(overlay_page)
        self._stack.addWidget(scroll)
        self._stack.setCurrentIndex(1)

    def _apply_styles(self) -> None:
        pal = get_palette()
        bg_window = pal.get("bg_window", pal["bg"]).name()
        bg_panel = pal.get("bg_panel", pal["bg"]).name()
        bg_raised = pal.get("bg_raised", pal["bg_panel"]).name()
        ctrl_border = pal.get("ctrl_border", pal["divider"]).name()
        ctrl_hover = pal.get("ctrl_hover", pal["bg_panel"]).name()
        fg_primary = pal.get("fg_primary", pal["fg"]).name()
        fg_muted = pal.get("fg_muted", pal["muted"]).name()
        accent = pal.get("accent").name()
        tones = _tone_colors(pal)

        self.setStyleSheet(
            f"""
            QWidget#LogisticsDashboardRoot,
            QWidget#LogisticsMainPage,
            QWidget#LogisticsOverlayPage,
            QScrollArea#LogisticsScroll {{
                background: {bg_window};
                color: {fg_primary};
                border: none;
            }}
            QScrollArea#LogisticsScroll > QWidget > QWidget {{ background: {bg_window}; }}
            QLabel#eyebrow {{ font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: {fg_muted}; }}
            QLabel#title {{ font-size: 20px; font-weight: 600; }}
            QLabel#context {{ font-size: 12px; color: {fg_muted}; }}
            QLabel#overlay_label {{ color: {fg_muted}; font-size: 14px; }}

            QFrame[card="true"] {{
                background: {bg_panel};
                border: 1px solid {ctrl_border};
                border-radius: 10px;
            }}
            QFrame[cardHeader="true"] {{
                background: transparent;
                border-bottom: 1px solid {ctrl_border};
            }}
            QLabel[cardTitle="true"] {{ font-size: 13px; font-weight: 600; }}

            QFrame[kpi="true"] {{
                background: {bg_panel};
                border: 1px solid {ctrl_border};
                border-radius: 10px;
            }}
            QFrame[kpi="true"]:hover {{ border-color: {accent}; }}
            QLabel[kpiValue="true"] {{ font-size: 22px; font-weight: 600; }}
            QLabel[kpiLabel="true"] {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: .4px; color: {fg_muted}; }}
            QFrame[kpi="true"][tone="low"] {{ background: {tones['low']}22; }}
            QFrame[kpi="true"][tone="low"] QLabel[kpiValue="true"],
            QFrame[kpi="true"][tone="low"] QLabel[kpiLabel="true"] {{ color: {tones['low']}; }}
            QFrame[kpi="true"][tone="crit"] {{ background: {tones['crit']}22; }}
            QFrame[kpi="true"][tone="crit"] QLabel[kpiValue="true"],
            QFrame[kpi="true"][tone="crit"] QLabel[kpiLabel="true"] {{ color: {tones['crit']}; }}
            QFrame[kpi="true"][tone="ok"] {{ background: {tones['ok']}22; }}
            QFrame[kpi="true"][tone="ok"] QLabel[kpiValue="true"],
            QFrame[kpi="true"][tone="ok"] QLabel[kpiLabel="true"] {{ color: {tones['ok']}; }}

            QFrame[row="true"] {{ background: transparent; border-bottom: 1px solid {ctrl_border}; }}
            QFrame[row="true"]:last-child {{ border-bottom: none; }}
            QLabel[rowText="true"] {{ font-size: 12.5px; font-weight: 500; }}
            QLabel[rowMeta="true"] {{ font-size: 11px; color: {fg_muted}; }}
            QFrame[row="true"][acked="true"] {{ background: transparent; }}

            QFrame[stripe="true"][tone="crit"] {{ background: {tones['crit']}; border-radius: 2px; }}
            QFrame[stripe="true"][tone="low"] {{ background: {tones['low']}; border-radius: 2px; }}
            QFrame[stripe="true"][tone="info"] {{ background: {tones['info']}; border-radius: 2px; }}
            QFrame[stripe="true"][tone="neutral"] {{ background: {tones['neutral']}; border-radius: 2px; }}

            QLabel[pill="true"] {{
                font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 8px;
                background: {bg_raised}; color: {fg_muted};
            }}
            QLabel[pill="true"][tone="crit"] {{ background: {tones['crit']}26; color: {tones['crit']}; }}
            QLabel[pill="true"][tone="low"] {{ background: {tones['low']}26; color: {tones['low']}; }}
            QLabel[pill="true"][tone="info"] {{ background: {tones['info']}26; color: {tones['info']}; }}

            QPushButton[flatBtn="true"] {{
                background: transparent;
                border: 1px solid {ctrl_border};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                color: {fg_primary};
            }}
            QPushButton[flatBtn="true"]:hover {{ background: {ctrl_hover}; }}
            QPushButton[flatBtn="true"][small="true"] {{ padding: 3px 10px; font-size: 11.5px; }}
            QPushButton[flatBtn="true"][tone="ok"] {{ border-color: {tones['ok']}; color: {tones['ok']}; }}
            QPushButton[flatBtn="true"]:disabled {{ color: {fg_muted}; border-color: {ctrl_border}; }}

            QFrame[statTile="true"] {{ background: {bg_panel}; }}
            QLabel[statLabel="true"] {{ font-size: 10.5px; color: {fg_muted}; }}
            QLabel[statValue="true"] {{ font-size: 16px; font-weight: 600; }}

            QFrame[badge="true"] {{
                border: 1px solid {ctrl_border};
                border-radius: 8px;
                background: {bg_panel};
            }}
            QFrame[badge="true"][state="ok"] QLabel#badge_dot {{ color: {tones['ok']}; }}
            QFrame[badge="true"][state="low"] QLabel#badge_dot {{ color: {tones['low']}; }}
            QFrame[badge="true"][state="crit"] QLabel#badge_dot {{ color: {tones['crit']}; }}
            QLabel#badge_text {{ font-size: 11.5px; }}
            """
        )

    # --------------------- Public API (Slots) ---------------------
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self._context.setText(f"OP: {op_period}  Now: {now_text}  Role: {role}")

    @Slot(dict)
    def update_kpis(self, kpis: Dict[str, object]) -> None:
        for key, kpi in self._kpi_widgets.items():
            if key in kpis:
                kpi.set_value(str(kpis[key]))
        if "approvals_pending" in self._kpi_widgets:
            try:
                pending = int(str(kpis.get("approvals_pending", 0)).split("/")[0] or 0)
            except ValueError:
                pending = 0
            self._kpi_widgets["approvals_pending"].set_tone("low" if pending else "neutral")
        if "low_stock_alerts" in self._kpi_widgets:
            try:
                low = int(str(kpis.get("low_stock_alerts", 0)).split("/")[0] or 0)
            except ValueError:
                low = 0
            self._kpi_widgets["low_stock_alerts"].set_tone("crit" if low else "neutral")

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    @Slot(list)
    def update_alerts(self, alerts: List[Dict[str, str]]) -> None:
        self._clear_layout(self._alerts_col)
        for a in alerts[:8]:
            self._alert_seq += 1
            alert_id = str(a.get("id") or f"alert-{self._alert_seq}")
            severity = str(a.get("severity") or "neutral").lower()
            row = _AlertRow(alert_id, severity, str(a.get("text", "")), str(a.get("ts", "—")))
            row.acknowledged.connect(self._on_alert_acknowledged)
            self._alerts_col.addWidget(row)
        if not alerts:
            empty = QLabel("No alerts in the last 30 minutes.")
            empty.setProperty("rowMeta", True)
            empty.setContentsMargins(14, 10, 14, 10)
            self._alerts_col.addWidget(empty)

    def _on_alert_acknowledged(self, alert_id: str) -> None:
        self.alertAcknowledged.emit(alert_id)
        self.acknowledgeAlertsRequested.emit()

    @Slot(list)
    def update_actions(self, actions: List[Dict[str, str]]) -> None:
        self._clear_layout(self._actions_col)
        for a in actions[:6]:
            self._action_seq += 1
            action_id = str(a.get("id") or f"action-{self._action_seq}")
            row = _ActionRow(
                action_id,
                str(a.get("priority", "Routine")),
                str(a.get("title", "")),
                str(a.get("subtitle", "")),
                str(a.get("kind", "assign")).lower(),
            )
            row.openRequested.connect(self.openActionRequested)
            row.approveRequested.connect(self.approveRequested)
            row.assignRequested.connect(self.assignRequested)
            self._actions_col.addWidget(row)
        if not actions:
            empty = QLabel("No open logistics actions.")
            empty.setProperty("rowMeta", True)
            empty.setContentsMargins(14, 10, 14, 10)
            self._actions_col.addWidget(empty)

    @Slot(dict)
    def update_resource_snapshot(self, snap: Dict[str, object]) -> None:
        def set_lbl(lbl: QLabel, key: str) -> None:
            if key in snap:
                lbl.setText(str(snap[key]))

        set_lbl(self._snap_checkins_total, "checkins_total")
        set_lbl(self._snap_missing_serials, "equip_218_missing_serials")
        set_lbl(self._snap_veh_ready, "vehicles_ready")
        set_lbl(self._snap_veh_assigned, "vehicles_assigned")
        set_lbl(self._snap_veh_oos, "vehicles_oos")
        set_lbl(self._snap_facilities, "facilities_status")

    @Slot(dict)
    def update_supply_comms(self, health: Dict[str, object]) -> None:
        for key in ("ppe", "medical", "water", "fuel", "comms_cache"):
            if key in health and key in self._badges:
                self._badges[key].set_state(str(health[key]))
        if "spare_radios" in health and "spare_radios" in self._badges:
            self._badges["spare_radios"].set_text_value(str(health["spare_radios"]))

    @Slot(list)
    def update_demob_queue(self, items: List[Dict[str, str]]) -> None:
        self._clear_layout(self._demob_col)
        for it in items[:8]:
            self._demob_seq += 1
            item_id = str(it.get("id") or f"demob-{self._demob_seq}")
            row = _DemobRow(item_id, str(it.get("title", "")), str(it.get("due", "")))
            row.checkInRequested.connect(self.demobCheckInRequested)
            self._demob_col.addWidget(row)
        if not items:
            empty = QLabel("Nothing pending demob or return.")
            empty.setProperty("rowMeta", True)
            empty.setContentsMargins(14, 10, 14, 10)
            self._demob_col.addWidget(empty)

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

    kpis = {
        "open_requests": 18,
        "approvals_pending": 6,
        "low_stock_alerts": 3,
        "checkins_today": 47,
        "vehicles_ready": "11/14",
        "facilities_ok": "5/5",
    }
    alerts = [
        {"id": "a1", "severity": "crit", "ts": "6 min ago", "text": "Fuel cache Bravo below 15% — resupply not yet scheduled"},
        {"id": "a2", "severity": "low", "ts": "14 min ago", "text": "ICS-213RR #REQ-0142 waiting on approval for 2h 10m"},
        {"id": "a3", "severity": "info", "ts": "27 min ago", "text": "Vehicle V-06 returned from field — inspection needed before reassignment"},
    ]
    actions = [
        {"id": "REQ-0139", "priority": "Critical", "title": "REQ-0139 · Class VIII medical resupply — Div C", "subtitle": "Requested by K. Osei · 45 min open", "kind": "approve"},
        {"id": "REQ-0142", "priority": "High", "title": "REQ-0142 · 6x portable radios — Air Ops", "subtitle": "Requested by T. Frayne · 2h 10m open", "kind": "assign"},
        {"id": "REQ-0144", "priority": "Routine", "title": "REQ-0144 · Generator fuel — Base camp", "subtitle": "Requested by M. Vale · 12 min open", "kind": "assign"},
    ]
    snap = {
        "checkins_total": 312,
        "equip_218_missing_serials": 4,
        "vehicles_ready": 11,
        "vehicles_assigned": 9,
        "vehicles_oos": 3,
        "facilities_status": "5/5",
    }
    health = {"ppe": "OK", "medical": "OK", "water": "LOW", "fuel": "TIGHT", "comms_cache": "OK", "spare_radios": "LOW"}
    demob = [
        {"id": "RET-T4", "title": "Team 4 — full return", "due": "ETA base camp 15:40"},
        {"id": "RET-V06", "title": "Vehicle V-06 — inspection pending", "due": "Returned 13:52"},
    ]

    w.update_kpis(kpis)
    w.update_alerts(alerts)
    w.update_actions(actions)
    w.update_resource_snapshot(snap)
    w.update_supply_comms(health)
    w.update_demob_queue(demob)
    w.set_context("7", "14:40", "Logistics Chief")
    w.setAutoRefresh(15000)

    w.resize(1180, 900)
    w.show()
    sys.exit(app.exec())
