"""DashboardTab — high-level Intel overview modelled on the Option 2 mockup layout."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal

from modules.intel.widgets.card_widget import CardWidget
from modules.intel.services.intel_service import IntelService


# ── helpers ──────────────────────────────────────────────────────────────────

def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: palette(mid);")
    return f


def _view_link(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setFlat(True)
    btn.setStyleSheet(
        "QPushButton { color: #4a9eff; font-size: 11px; text-align: left; padding: 0; }"
        "QPushButton:hover { color: #79b8ff; text-decoration: underline; }"
    )
    btn.setCursor(Qt.PointingHandCursor)
    return btn


# ── summary card (top row) ────────────────────────────────────────────────────

class _SummaryCard(CardWidget):
    """Metric card with icon emoji, large count, label, and 'View >' link."""

    clicked_view = Signal()

    def __init__(
        self,
        icon: str,
        title: str,
        accent: str,
        view_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, padding=14, accent_left=accent)
        self._accent = accent
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(100)

        lyt = self.layout()

        # Icon + count row
        top = QHBoxLayout()
        top.setSpacing(10)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setStyleSheet(f"font-size: 28px; color: {accent};")
        self._icon_lbl.setFixedWidth(36)
        self._icon_lbl.setAlignment(Qt.AlignCenter)

        count_col = QVBoxLayout()
        count_col.setSpacing(0)
        self._count_lbl = QLabel("0")
        self._count_lbl.setStyleSheet(
            f"font-size: 32px; font-weight: 700; color: {accent};"
        )
        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: palette(placeholderText); letter-spacing: 1px;"
        )
        self._title_lbl.setWordWrap(True)
        count_col.addWidget(self._count_lbl)
        count_col.addWidget(self._title_lbl)

        top.addWidget(self._icon_lbl)
        top.addLayout(count_col)
        top.addStretch()
        lyt.addLayout(top)

        # View link
        self._view_btn = _view_link(f"{view_label}  ›")
        self._view_btn.clicked.connect(self.clicked_view)
        lyt.addWidget(self._view_btn)

    def set_count(self, count: int, accent: str | None = None) -> None:
        self._count_lbl.setText(str(count))
        a = accent or self._accent
        if accent:
            self._accent = accent
            self._count_lbl.setStyleSheet(
                f"font-size: 32px; font-weight: 700; color: {a};"
            )
            self._icon_lbl.setStyleSheet(f"font-size: 28px; color: {a};")
            self.set_accent(a)


# ── activity row ──────────────────────────────────────────────────────────────

_ENTITY_ICONS = {
    "subject": "👤",
    "lead": "🔍",
    "item": "📋",
    "assessment": "📊",
    "report": "📄",
}

_ENTITY_COLORS = {
    "subject":    "#cf4444",
    "lead":       "#d29922",
    "item":       "#4a9eff",
    "assessment": "#2da44e",
    "report":     "#8b949e",
}


class _ActivityRow(QWidget):
    def __init__(self, entry: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        ts = entry.get("timestamp", "")
        time_str = ts[11:16] if len(ts) >= 16 else ""
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("color: #4a9eff; font-size: 11px; font-weight: 600; min-width: 38px;")
        time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        entity = entry.get("entity_type", "")
        icon_lbl = QLabel(_ENTITY_ICONS.get(entity, "•"))
        icon_lbl.setStyleSheet(f"font-size: 13px; color: {_ENTITY_COLORS.get(entity, '#8b949e')};")
        icon_lbl.setFixedWidth(18)
        icon_lbl.setAlignment(Qt.AlignCenter)

        summary_lbl = QLabel(entry.get("summary", ""))
        summary_lbl.setStyleSheet("font-size: 12px; color: palette(windowText);")
        summary_lbl.setWordWrap(False)

        layout.addWidget(time_lbl)
        layout.addWidget(icon_lbl)
        layout.addWidget(summary_lbl, 1)


# ── critical item row ─────────────────────────────────────────────────────────

_PRIORITY_COLORS = {
    "critical": ("#cf222e", "#3d1414"),
    "high":     ("#d29922", "#3d2c08"),
    "medium":   ("#338eda", "#0d2a42"),
    "low":      ("#6e7781", "#1c2128"),
}

_TREND_LABELS = {
    "worsening": ("Worsening", "#cf4444"),
    "improving": ("Improving", "#2da44e"),
    "stable":    ("Stable",    "#8b949e"),
    "unknown":   ("Unknown",   "#8b949e"),
}


class _CriticalItemRow(QWidget):
    def __init__(self, item: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        num_lbl = QLabel(str(item.get("number", "")))
        num_lbl.setStyleSheet("font-size: 11px; color: palette(placeholderText); min-width: 32px;")
        num_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        title_lbl = QLabel(item.get("title", ""))
        title_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: palette(windowText);")
        type_lbl = QLabel(item.get("item_type", ""))
        type_lbl.setStyleSheet("font-size: 10px; color: palette(placeholderText);")
        info_col.addWidget(title_lbl)
        info_col.addWidget(type_lbl)

        priority = (item.get("priority") or "").lower()
        fg, bg = _PRIORITY_COLORS.get(priority, ("#8b949e", "#1c2128"))
        chip = QLabel(priority.upper())
        chip.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {fg}; background: {bg};"
            f"border: 1px solid {fg}; border-radius: 3px; padding: 1px 5px;"
        )
        chip.setFixedHeight(18)
        chip.setAlignment(Qt.AlignCenter)

        ts = item.get("updated_at", "")
        time_str = ts[11:16] if len(ts) >= 16 else ""
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("font-size: 11px; color: palette(placeholderText); min-width: 38px;")
        time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        trend = (item.get("trend") or "unknown").lower()
        trend_text, trend_color = _TREND_LABELS.get(trend, ("Unknown", "#8b949e"))
        trend_lbl = QLabel(trend_text)
        trend_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {trend_color}; min-width: 60px;")
        trend_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(num_lbl)
        layout.addLayout(info_col, 1)
        layout.addWidget(chip)
        layout.addWidget(time_lbl)
        layout.addWidget(trend_lbl)


# ── lead snapshot row ─────────────────────────────────────────────────────────

_LEAD_PRIORITY_COLORS = {
    "critical": "#cf4444",
    "high":     "#d29922",
    "medium":   "#4a9eff",
    "low":      "#8b949e",
}


class _LeadSnapshotRow(QWidget):
    def __init__(self, lead: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        priority = (lead.get("priority") or "").lower()
        dot_color = _LEAD_PRIORITY_COLORS.get(priority, "#8b949e")
        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 10px; color: {dot_color};")
        dot.setFixedWidth(14)
        dot.setAlignment(Qt.AlignCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        title_lbl = QLabel(lead.get("title", ""))
        title_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: palette(windowText);")
        assigned = lead.get("assigned_to") or "Unassigned"
        source = lead.get("source_type") or ""
        sub_text = f"{assigned}  •  {source}" if source else assigned
        sub_lbl = QLabel(sub_text)
        sub_lbl.setStyleSheet("font-size: 10px; color: palette(placeholderText);")
        info_col.addWidget(title_lbl)
        info_col.addWidget(sub_lbl)

        status = lead.get("status") or ""
        status_color = "#d29922" if status.lower() == "new" else "#4a9eff" if status.lower() == "assigned" else "#8b949e"
        status_lbl = QLabel(status)
        status_lbl.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {status_color};")
        status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(dot)
        layout.addLayout(info_col, 1)
        layout.addWidget(status_lbl)


# ── main tab ──────────────────────────────────────────────────────────────────

class DashboardTab(QWidget):
    navigate_to_tab = Signal(str)   # emitted when user clicks a "View >" link

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # ── title bar ────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_lbl = QLabel("Intel Dashboard")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")
        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self.refresh)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(refresh_btn)
        root.addLayout(title_row)

        # ── summary cards row — fixed height so all cards are always equal ──
        cards_container = QWidget()
        cards_container.setFixedHeight(120)
        cards_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cards_row = QHBoxLayout(cards_container)
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(10)

        self._card_critical    = _SummaryCard("⚠️", "Critical Intel Items", "#cf222e", "View Items")
        self._card_assessments = _SummaryCard("📋", "Open Assessments",     "#2da44e", "View Assessments")
        self._card_worsening   = _SummaryCard("📉", "Worsening Trends",     "#d29922", "View Trends")
        self._card_leads       = _SummaryCard("🔍", "Open Leads",           "#4a9eff", "View Leads")

        self._card_critical.clicked_view.connect(lambda: self.navigate_to_tab.emit("items"))
        self._card_assessments.clicked_view.connect(lambda: self.navigate_to_tab.emit("assessments"))
        self._card_worsening.clicked_view.connect(lambda: self.navigate_to_tab.emit("items"))
        self._card_leads.clicked_view.connect(lambda: self.navigate_to_tab.emit("leads"))

        for card in (self._card_critical, self._card_assessments,
                     self._card_worsening, self._card_leads):
            cards_row.addWidget(card)
        root.addWidget(cards_container)

        # ── middle three-column row ──────────────────────────────────────────
        mid = QHBoxLayout()
        mid.setSpacing(12)

        # Left — Recent Activity
        self._activity_card = CardWidget(padding=14)
        self._activity_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        act_hdr = QHBoxLayout()
        act_title = QLabel("RECENT ACTIVITY")
        act_title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: palette(placeholderText); letter-spacing: 1px;"
        )
        self._act_view_btn = _view_link("View Intel Log  ›")
        self._act_view_btn.clicked.connect(lambda: self.navigate_to_tab.emit("log"))
        act_hdr.addWidget(act_title)
        act_hdr.addStretch()
        act_hdr.addWidget(self._act_view_btn)
        self._activity_card.layout().addLayout(act_hdr)
        self._activity_card.layout().addWidget(_divider())
        self._activity_container = QVBoxLayout()
        self._activity_container.setSpacing(0)
        self._activity_card.layout().addLayout(self._activity_container)
        self._activity_card.layout().addStretch()
        mid.addWidget(self._activity_card, 2)

        # Centre — Critical Intel Items
        self._critical_card = CardWidget(padding=14)
        self._critical_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        crit_hdr = QHBoxLayout()
        crit_title = QLabel("CRITICAL INTEL ITEMS")
        crit_title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: palette(placeholderText); letter-spacing: 1px;"
        )
        self._crit_view_btn = _view_link("Go to Information Board  ›")
        self._crit_view_btn.clicked.connect(lambda: self.navigate_to_tab.emit("items"))
        crit_hdr.addWidget(crit_title)
        crit_hdr.addStretch()
        crit_hdr.addWidget(self._crit_view_btn)
        self._critical_card.layout().addLayout(crit_hdr)
        self._critical_card.layout().addWidget(_divider())
        self._critical_container = QVBoxLayout()
        self._critical_container.setSpacing(0)
        self._critical_card.layout().addLayout(self._critical_container)
        self._critical_card.layout().addStretch()
        mid.addWidget(self._critical_card, 3)

        # Right — Leads Snapshot
        self._leads_snap_card = CardWidget(padding=14)
        self._leads_snap_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        leads_hdr = QHBoxLayout()
        leads_title = QLabel("OPEN LEADS")
        leads_title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: palette(placeholderText); letter-spacing: 1px;"
        )
        self._leads_view_btn = _view_link("View All Leads  ›")
        self._leads_view_btn.clicked.connect(lambda: self.navigate_to_tab.emit("leads"))
        leads_hdr.addWidget(leads_title)
        leads_hdr.addStretch()
        leads_hdr.addWidget(self._leads_view_btn)
        self._leads_snap_card.layout().addLayout(leads_hdr)
        self._leads_snap_card.layout().addWidget(_divider())
        self._leads_snap_container = QVBoxLayout()
        self._leads_snap_container.setSpacing(0)
        self._leads_snap_card.layout().addLayout(self._leads_snap_container)
        self._leads_snap_card.layout().addStretch()
        mid.addWidget(self._leads_snap_card, 2)

        root.addLayout(mid, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self.refresh()

    # ── refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        if self._service is None:
            return
        data = self._service.get_dashboard()

        critical   = data.get("critical_items", 0)
        assessments = data.get("open_assessments", 0)
        worsening  = data.get("worsening_items", 0)
        leads      = data.get("open_leads", 0)
        self._card_critical.set_count(critical,
            accent="#cf222e" if critical > 0 else "#6e7781")
        self._card_assessments.set_count(assessments,
            accent="#2da44e" if assessments > 0 else "#6e7781")
        self._card_worsening.set_count(worsening,
            accent="#d29922" if worsening > 0 else "#6e7781")
        self._card_leads.set_count(leads,
            accent="#4a9eff" if leads > 0 else "#6e7781")

        # Recent Activity
        self._clear_layout(self._activity_container)
        for entry in data.get("recent_activity", [])[:8]:
            self._activity_container.addWidget(_ActivityRow(entry))
            self._activity_container.addWidget(_divider())

        if not data.get("recent_activity"):
            lbl = QLabel("No recent activity.")
            lbl.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
            self._activity_container.addWidget(lbl)

        # Critical Intel Items
        self._clear_layout(self._critical_container)
        for item in data.get("critical_item_list", [])[:6]:
            self._critical_container.addWidget(_CriticalItemRow(item))
            self._critical_container.addWidget(_divider())

        if not data.get("critical_item_list"):
            lbl = QLabel("No critical items.")
            lbl.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
            self._critical_container.addWidget(lbl)

        # Leads Snapshot
        self._clear_layout(self._leads_snap_container)
        lead_list = data.get("open_lead_list", [])
        for lead in lead_list[:8]:
            self._leads_snap_container.addWidget(_LeadSnapshotRow(lead))
            self._leads_snap_container.addWidget(_divider())

        if not lead_list:
            lbl = QLabel("No open leads.")
            lbl.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
            self._leads_snap_container.addWidget(lbl)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
