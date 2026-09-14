"""
Planning — At-a-Glance dashboard widget (Qt Widgets, PySide6).

Redesigned around the Planning Section Chief's actual quick-glance needs:
where the planning cycle stands right now, what is blocking the next IAP,
what is waiting on the chief's own approval, where resource/safety gaps are
concentrated (keyed by Strategy — not Division/Group, since not every
incident stands up that tier), objective-to-strategy planning momentum, and
IAP package completeness.

Wiring instructions (Planning menu action -> `MainWindow.open_planning_glance`):

    from modules.planning.panels.plandashboard import make_planning_glance_widget

    def open_planning_glance():
        if not hasattr(self, "_planning_glance_widget") or self._planning_glance_widget is None:
            self._planning_glance_widget = make_planning_glance_widget(self)
        w = self._planning_glance_widget
        w.setAutoRefresh(30_000)
        w.show()
        w.raise_()
        w.activateWindow()

This widget is purely presentational: no DB or network calls. Use the public
slots to push data in from your controllers/services. `openFullPlannerRequested`
is meant to be connected to `MainWindow.open_tactics_resources_planner`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from utils.styles import get_palette, subscribe_theme


# --------------------------------------------------------------------------
# Small painted widgets
# --------------------------------------------------------------------------
class CycleTrackWidget(QWidget):
    """Horizontal stepper showing the planning (P) cycle and current stage."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._stages: List[str] = []
        self._current_index: int = -1
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_stages(self, stages: List[str], current_index: int) -> None:
        self._stages = list(stages)
        self._current_index = current_index
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._stages:
            return
        pal = get_palette()
        border = pal.get("ctrl_border", pal.get("divider"))
        success = pal.get("success", pal.get("accent_alt"))
        accent = pal.get("accent")
        muted = pal.get("fg_muted", pal.get("muted"))
        fg = pal.get("fg_primary", pal.get("fg"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        n = len(self._stages)
        w = self.width()
        margin = 16
        usable = max(1, w - 2 * margin)
        step = usable / max(1, n - 1) if n > 1 else 0
        cy = 14
        radius = 6

        # connecting line
        painter.setPen(QPen(border, 2))
        painter.drawLine(QPointF(margin, cy), QPointF(w - margin, cy))

        label_font = QFont(self.font())
        label_font.setPointSize(8)
        current_font = QFont(label_font)
        current_font.setBold(True)

        for i, label in enumerate(self._stages):
            cx = margin + step * i
            if i < self._current_index:
                color = success
            elif i == self._current_index:
                color = accent
            else:
                color = pal.get("ctrl_bg", pal.get("bg_panel"))
            painter.setPen(QPen(color if i <= self._current_index else border, 2))
            painter.setBrush(color if i <= self._current_index else pal.get("bg_panel"))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)
            if i == self._current_index:
                halo = QColor(accent)
                halo.setAlpha(60)
                painter.setPen(Qt.NoPen)
                painter.setBrush(halo)
                painter.drawEllipse(QPointF(cx, cy), radius + 5, radius + 5)

            painter.setPen(fg if i == self._current_index else muted)
            painter.setFont(current_font if i == self._current_index else label_font)
            text_rect = QRectF(cx - step / 2 + 2, cy + 12, max(step - 4, 70), 34)
            painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, label)

        painter.end()


class DonutGauge(QWidget):
    """Small ring gauge for IAP form completeness (percent or OK/blocked)."""

    def __init__(self, name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._fraction: float = 0.0
        self._ok: bool = False
        self._text: str = "—"
        self.setFixedSize(72, 92)

    def set_state(self, fraction: float, ok: bool, text: str) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self._ok = ok
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        pal = get_palette()
        track = pal.get("ctrl_bg", pal.get("bg_panel"))
        fg = pal.get("fg_primary", pal.get("fg"))
        muted = pal.get("fg_muted", pal.get("muted"))
        if self._ok:
            ring_color = pal.get("success", pal.get("accent_alt"))
        elif self._fraction >= 0.7:
            ring_color = pal.get("warning")
        else:
            ring_color = pal.get("danger", pal.get("error"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        size = 58
        rect = QRectF((self.width() - size) / 2, 4, size, size)
        thickness = 7

        pen_track = QPen(track, thickness)
        pen_track.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_track)
        painter.drawArc(rect.adjusted(thickness / 2, thickness / 2, -thickness / 2, -thickness / 2), 0, 360 * 16)

        fraction = 1.0 if self._ok else self._fraction
        pen_val = QPen(ring_color, thickness)
        pen_val.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_val)
        span = int(360 * 16 * fraction)
        painter.drawArc(rect.adjusted(thickness / 2, thickness / 2, -thickness / 2, -thickness / 2), 90 * 16, -span)

        painter.setPen(fg)
        f = QFont(self.font())
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(rect, Qt.AlignCenter, self._text)

        painter.setPen(muted)
        f2 = QFont(self.font())
        f2.setPointSize(8)
        f2.setBold(True)
        painter.setFont(f2)
        painter.drawText(QRectF(0, size + 6, self.width(), 18), Qt.AlignHCenter | Qt.AlignTop, self._name)
        painter.end()


# --------------------------------------------------------------------------
# Layout helpers
# --------------------------------------------------------------------------
def _make_section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    f = lbl.font()
    f.setBold(True)
    f.setPointSize(10)
    lbl.setFont(f)
    lbl.setProperty("role", "section-title")
    return lbl


def _severity_color(pal: Dict[str, QColor], severity: str) -> QColor:
    severity = (severity or "").strip().lower()
    if severity in ("crit", "critical"):
        return pal.get("danger", pal.get("error"))
    if severity == "high":
        return pal.get("warning")
    if severity == "med":
        return pal.get("info")
    return pal.get("fg_muted", pal.get("muted"))


def _gap_bucket(count: Optional[int]) -> str:
    if count is None:
        return "none"
    if count <= 0:
        return "ok"
    if count == 1:
        return "info"
    if count == 2:
        return "warning"
    return "danger"


class PlanningGlanceWidget(QWidget):
    """Compact Planning — At-a-Glance widget (Planning Section Chief view).

    Public slots/methods:
    - set_context(op_period, now_text, role)
    - update_cycle(stages, current_index, countdown_text, milestone_name, milestone_meta, op_number, op_total)
    - update_blockers(items: list[dict])           # id, title, meta, severity, owed
    - update_approvals(items: list[dict])          # id, title, who, waited
    - update_gaps(rows: list[dict])                # strategy_id, strategy_name, org_label, resources, personnel, equipment, hazards, comms
    - update_objectives(items: list[dict])         # id, tag, name, planned, total, linked
    - update_doc_rings(forms: dict)                # e.g. {"202": {"ok": True}, "204": {"fraction": 0.3}}
    - setIncidentOverlayVisible(visible: bool)
    - setAutoRefresh(interval_ms: int)
    """

    # Signals
    openBlockerRequested = Signal(str)
    approveRequested = Signal(str)
    openApprovalRequested = Signal(str)
    viewObjectiveRequested = Signal(str)
    openFullPlannerRequested = Signal()
    refreshRequested = Signal()

    _GAP_COLUMNS = [
        ("resources", "Resources"),
        ("personnel", "Personnel"),
        ("equipment", "Equipment"),
        ("hazards", "Hazards"),
        ("comms", "Comms"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlanningGlanceWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(False)
        self._auto_timer.timeout.connect(self.refreshRequested)
        self._doc_rings: Dict[str, DonutGauge] = {}
        self._gap_cells: List[QLabel] = []

        self._stack = QStackedLayout(self)
        self._content = QWidget(self)
        self._content.setObjectName("PlanningGlanceContent")
        self._content.setAttribute(Qt.WA_StyledBackground, True)
        self._stack.addWidget(self._content)
        self._overlay = QLabel("No active incident — select or create one.")
        self._overlay.setObjectName("OverlayMessage")
        self._overlay.setAttribute(Qt.WA_StyledBackground, True)
        self._overlay.setAlignment(Qt.AlignCenter)
        of = self._overlay.font()
        of.setPointSize(12)
        of.setBold(True)
        self._overlay.setFont(of)
        self._stack.addWidget(self._overlay)
        self._stack.setCurrentIndex(0)

        self._build_ui(self._content)
        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

    # ------------------------------- UI ---------------------------------
    def _build_ui(self, root: QWidget) -> None:
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        self._title = QLabel("Planning Section Chief — Dashboard", self)
        tf = self._title.font()
        tf.setPointSize(15)
        tf.setBold(True)
        self._title.setFont(tf)
        header_row.addWidget(self._title)
        header_row.addStretch(1)
        self._context_label = QLabel("OP —  Now —  Role —", self)
        header_row.addWidget(self._context_label)
        self._btn_full_planner = QPushButton("Full Planner ▸", self)
        self._btn_full_planner.clicked.connect(self.openFullPlannerRequested)
        header_row.addWidget(self._btn_full_planner)
        root_layout.addLayout(header_row)

        # -------- Hero: planning cycle position + countdown --------
        hero = QFrame(self)
        hero.setObjectName("HeroBox")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(10)

        hero_top = QHBoxLayout()
        hero_top.setSpacing(20)

        count_col = QVBoxLayout()
        count_col.setSpacing(2)
        lbl_count_cap = QLabel("TIME TO NEXT MILESTONE", self)
        lbl_count_cap.setProperty("role", "eyebrow")
        self._lbl_countdown = QLabel("—", self)
        f = self._lbl_countdown.font()
        f.setPointSize(24)
        f.setBold(True)
        self._lbl_countdown.setFont(f)
        self._lbl_countdown.setProperty("role", "countdown")
        count_col.addWidget(lbl_count_cap)
        count_col.addWidget(self._lbl_countdown)
        hero_top.addLayout(count_col)

        divider1 = QFrame(self)
        divider1.setFrameShape(QFrame.VLine)
        divider1.setObjectName("HeroDivider")
        hero_top.addWidget(divider1)

        next_col = QVBoxLayout()
        next_col.setSpacing(2)
        lbl_next_cap = QLabel("NEXT MILESTONE", self)
        lbl_next_cap.setProperty("role", "eyebrow")
        self._lbl_milestone_name = QLabel("—", self)
        f2 = self._lbl_milestone_name.font()
        f2.setPointSize(12)
        f2.setBold(True)
        self._lbl_milestone_name.setFont(f2)
        self._lbl_milestone_meta = QLabel("—", self)
        self._lbl_milestone_meta.setProperty("role", "muted")
        next_col.addWidget(lbl_next_cap)
        next_col.addWidget(self._lbl_milestone_name)
        next_col.addWidget(self._lbl_milestone_meta)
        hero_top.addLayout(next_col)

        hero_top.addStretch(1)

        op_col = QVBoxLayout()
        op_col.setSpacing(2)
        lbl_op_cap = QLabel("OPERATIONAL PERIOD", self)
        lbl_op_cap.setProperty("role", "eyebrow")
        lbl_op_cap.setAlignment(Qt.AlignRight)
        self._lbl_op = QLabel("—", self)
        f3 = self._lbl_op.font()
        f3.setPointSize(18)
        f3.setBold(True)
        self._lbl_op.setFont(f3)
        self._lbl_op.setAlignment(Qt.AlignRight)
        op_col.addWidget(lbl_op_cap)
        op_col.addWidget(self._lbl_op)
        hero_top.addLayout(op_col)

        hero_layout.addLayout(hero_top)

        self._cycle_track = CycleTrackWidget(self)
        hero_layout.addWidget(self._cycle_track)
        root_layout.addWidget(hero)

        # -------- Attention row: blockers + approvals --------
        attn_row = QHBoxLayout()
        attn_row.setSpacing(12)

        blockers_box = QFrame(self)
        blockers_box.setObjectName("SectionBox")
        blockers_layout = QVBoxLayout(blockers_box)
        blockers_layout.setContentsMargins(12, 10, 12, 10)
        blockers_layout.setSpacing(6)
        b_head = QHBoxLayout()
        b_head.addWidget(_make_section_header("Blocking the IAP — ranked by time-to-deadline"))
        b_head.addStretch(1)
        self._lbl_blocker_count = QLabel("0", self)
        self._lbl_blocker_count.setProperty("role", "count-danger")
        b_head.addWidget(self._lbl_blocker_count)
        blockers_layout.addLayout(b_head)
        self._blockers_list = QListWidget(self)
        self._configure_list(self._blockers_list)
        self._blockers_list.itemDoubleClicked.connect(self._emit_open_selected_blocker)
        blockers_layout.addWidget(self._blockers_list)
        btn_row = QHBoxLayout()
        self._btn_open_blocker = QPushButton("Open", self)
        self._btn_open_blocker.clicked.connect(self._emit_open_selected_blocker)
        btn_row.addWidget(self._btn_open_blocker)
        btn_row.addStretch(1)
        blockers_layout.addLayout(btn_row)
        attn_row.addWidget(blockers_box, 7)

        approvals_box = QFrame(self)
        approvals_box.setObjectName("SectionBox")
        approvals_layout = QVBoxLayout(approvals_box)
        approvals_layout.setContentsMargins(12, 10, 12, 10)
        approvals_layout.setSpacing(6)
        a_head = QHBoxLayout()
        a_head.addWidget(_make_section_header("Waiting on You"))
        a_head.addStretch(1)
        self._lbl_approval_count = QLabel("0", self)
        self._lbl_approval_count.setProperty("role", "count-neutral")
        a_head.addWidget(self._lbl_approval_count)
        approvals_layout.addLayout(a_head)
        self._approvals_list = QListWidget(self)
        self._configure_list(self._approvals_list)
        self._approvals_list.itemDoubleClicked.connect(self._emit_open_selected_approval)
        approvals_layout.addWidget(self._approvals_list)
        a_btn_row = QHBoxLayout()
        self._btn_approve = QPushButton("Approve", self)
        self._btn_approve.clicked.connect(self._emit_approve_selected)
        a_btn_row.addWidget(self._btn_approve)
        a_btn_row.addStretch(1)
        approvals_layout.addLayout(a_btn_row)
        attn_row.addWidget(approvals_box, 5)

        root_layout.addLayout(attn_row)

        # -------- Gap heat grid (keyed by Strategy) --------
        gap_box = QFrame(self)
        gap_box.setObjectName("SectionBox")
        gap_outer = QVBoxLayout(gap_box)
        gap_outer.setContentsMargins(12, 10, 12, 10)
        gap_outer.setSpacing(8)
        g_head = QHBoxLayout()
        g_head.addWidget(_make_section_header("Resource & Safety Gaps by Strategy"))
        g_head.addStretch(1)
        g_head.addWidget(QLabel("cell = unresolved gap count", self))
        gap_outer.addLayout(g_head)

        self._gap_grid = QGridLayout()
        self._gap_grid.setHorizontalSpacing(6)
        self._gap_grid.setVerticalSpacing(6)
        for col, (_key, label) in enumerate(self._GAP_COLUMNS, start=1):
            head = QLabel(label, self)
            head.setAlignment(Qt.AlignCenter)
            head.setProperty("role", "eyebrow")
            self._gap_grid.addWidget(head, 0, col)
        self._gap_grid.setColumnStretch(0, 0)
        for col in range(1, len(self._GAP_COLUMNS) + 1):
            self._gap_grid.setColumnStretch(col, 1)
        gap_outer.addLayout(self._gap_grid)
        root_layout.addWidget(gap_box)

        # -------- Bottom row: objective momentum + doc rings --------
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        obj_box = QFrame(self)
        obj_box.setObjectName("SectionBox")
        obj_layout = QVBoxLayout(obj_box)
        obj_layout.setContentsMargins(12, 10, 12, 10)
        obj_layout.setSpacing(6)
        o_head = QHBoxLayout()
        o_head.addWidget(_make_section_header("Objective → Strategy Momentum"))
        o_head.addStretch(1)
        o_head.addWidget(QLabel("planned ÷ linked strategies", self))
        obj_layout.addLayout(o_head)
        self._obj_container = QVBoxLayout()
        self._obj_container.setSpacing(6)
        obj_layout.addLayout(self._obj_container)
        obj_layout.addStretch(1)
        bottom_row.addWidget(obj_box, 3)

        rings_box = QFrame(self)
        rings_box.setObjectName("SectionBox")
        rings_layout = QVBoxLayout(rings_box)
        rings_layout.setContentsMargins(12, 10, 12, 10)
        rings_layout.setSpacing(6)
        rings_layout.addWidget(_make_section_header("IAP Package Completeness"))
        self._rings_row = QHBoxLayout()
        self._rings_row.setSpacing(6)
        for key in ("202", "203", "204", "205", "205A", "206"):
            ring = DonutGauge(key, self)
            self._doc_rings[key] = ring
            self._rings_row.addWidget(ring)
        rings_layout.addLayout(self._rings_row)
        rings_layout.addStretch(1)
        bottom_row.addWidget(rings_box, 2)

        root_layout.addLayout(bottom_row)
        root_layout.addStretch(1)

    def _apply_styles(self) -> None:
        pal = get_palette()
        bg_window = pal.get("bg_window", pal["bg"]).name()
        bg_raised = pal.get("bg_raised", pal["bg_panel"]).name()
        ctrl_bg = pal.get("ctrl_bg", pal["bg_panel"]).name()
        ctrl_border = pal.get("ctrl_border", pal["divider"]).name()
        fg_primary = pal.get("fg_primary", pal["fg"]).name()
        fg_muted = pal.get("fg_muted", pal["muted"]).name()
        accent = pal.get("accent").name()
        danger = pal.get("danger", pal.get("error")).name()

        self.setStyleSheet(
            f"""
            QWidget#PlanningGlanceWidget,
            QWidget#PlanningGlanceContent {{
                background: {bg_window};
                color: {fg_primary};
            }}
            QLabel#OverlayMessage {{
                background: {bg_window};
                color: {fg_primary};
                font-weight: 600;
            }}
            QFrame#HeroBox {{
                background: {bg_raised};
                border: 1px solid {ctrl_border};
                border-radius: 12px;
            }}
            QFrame#HeroDivider {{
                color: {ctrl_border};
            }}
            QFrame#SectionBox {{
                background: {bg_raised};
                border: 1px solid {ctrl_border};
                border-radius: 10px;
            }}
            QLabel[role="eyebrow"] {{
                color: {fg_muted};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QLabel[role="muted"] {{
                color: {fg_muted};
            }}
            QLabel[role="countdown"] {{
                color: {accent};
            }}
            QLabel[role="count-danger"] {{
                color: {danger};
                font-weight: 700;
                background: {ctrl_bg};
                border-radius: 8px;
                padding: 1px 8px;
            }}
            QLabel[role="count-neutral"] {{
                color: {fg_muted};
                font-weight: 700;
                background: {ctrl_bg};
                border-radius: 8px;
                padding: 1px 8px;
            }}
            QListWidget {{
                background: {ctrl_bg};
                border: 1px solid {ctrl_border};
                border-radius: 6px;
            }}
            QPushButton {{
                padding: 4px 10px;
            }}
            """
        )
        for cell in self._gap_cells:
            self._style_gap_cell(cell)
        if hasattr(self, "_gaps_cache"):
            self.update_gaps(self._gaps_cache)
        if hasattr(self, "_obj_cache"):
            self.update_objectives(self._obj_cache)

    def _configure_list(self, lst: QListWidget) -> None:
        lst.setSelectionMode(QAbstractItemView.SingleSelection)
        lst.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lst.setUniformItemSizes(False)
        lst.setAlternatingRowColors(False)
        lst.setSpacing(2)

    # ---------------------------- Public slots ---------------------------
    @Slot(str, str, str)
    def set_context(self, op_period: str, now_text: str, role: str) -> None:
        self._context_label.setText(f"OP {op_period}  ·  {now_text}  ·  {role}")

    @Slot(list, int, str, str, str, str, str)
    def update_cycle(
        self,
        stages: List[str],
        current_index: int,
        countdown_text: str,
        milestone_name: str,
        milestone_meta: str,
        op_number: str = "",
        op_total: str = "",
    ) -> None:
        self._cycle_track.set_stages(stages, current_index)
        self._lbl_countdown.setText(countdown_text)
        self._lbl_milestone_name.setText(milestone_name)
        self._lbl_milestone_meta.setText(milestone_meta)
        if op_total:
            self._lbl_op.setText(f"{op_number} of {op_total}")
        else:
            self._lbl_op.setText(str(op_number))

    @Slot(list)
    def update_blockers(self, items: List[Dict[str, Any]]) -> None:
        self._blockers_list.clear()
        pal = get_palette()
        for entry in list(items)[:8]:
            bid = str(entry.get("id", ""))
            title = str(entry.get("title", ""))
            meta = str(entry.get("meta", ""))
            severity = str(entry.get("severity", ""))
            owed = str(entry.get("owed", ""))
            text = f"{title}\n{meta}" + (f"   ·   owed {owed}" if owed else "")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, bid)
            item.setToolTip(f"{title} — {meta}")
            color = _severity_color(pal, severity)
            item.setForeground(color)
            self._blockers_list.addItem(item)
        self._lbl_blocker_count.setText(str(len(items)))

    @Slot(list)
    def update_approvals(self, items: List[Dict[str, Any]]) -> None:
        self._approvals_list.clear()
        for entry in list(items)[:8]:
            aid = str(entry.get("id", ""))
            what = str(entry.get("title", ""))
            who = str(entry.get("who", ""))
            waited = str(entry.get("waited", ""))
            text = f"{what}\n{who}" + (f"   ·   waiting {waited}" if waited else "")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, aid)
            item.setToolTip(f"{what} — {who}")
            self._approvals_list.addItem(item)
        self._lbl_approval_count.setText(str(len(items)))

    @Slot(list)
    def update_gaps(self, rows: List[Dict[str, Any]]) -> None:
        self._gaps_cache = list(rows)
        # Clear existing body rows (keep header row 0)
        for cell in self._gap_cells:
            cell.setParent(None)
        self._gap_cells = []
        pal = get_palette()
        for r, row in enumerate(rows, start=1):
            strategy_id = str(row.get("strategy_id", ""))
            strategy_name = str(row.get("strategy_name", ""))
            org_label = str(row.get("org_label", ""))
            head_text = strategy_id
            head = QLabel(head_text if not org_label else f"{head_text}\n{org_label}", self)
            head.setToolTip(strategy_name)
            head.setProperty("role", "muted")
            self._gap_grid.addWidget(head, r, 0)
            self._gap_cells.append(head)
            for c, (key, _label) in enumerate(self._GAP_COLUMNS, start=1):
                count = row.get(key)
                cell = QLabel("—" if count is None else str(count), self)
                cell.setAlignment(Qt.AlignCenter)
                cell.setProperty("gap_bucket", _gap_bucket(count))
                self._style_gap_cell(cell)
                self._gap_grid.addWidget(cell, r, c)
                self._gap_cells.append(cell)

    def _style_gap_cell(self, cell: QLabel) -> None:
        bucket = cell.property("gap_bucket")
        if bucket is None:
            return
        pal = get_palette()
        ctrl_bg = pal.get("ctrl_bg", pal.get("bg_panel"))
        border = pal.get("ctrl_border", pal.get("divider"))
        muted = pal.get("fg_muted", pal.get("muted"))
        mapping = {
            "none": (ctrl_bg, border, muted),
            "ok": (pal.get("success", pal.get("accent_alt")), pal.get("success", pal.get("accent_alt")), pal.get("bg_window")),
            "info": (pal.get("info"), pal.get("info"), pal.get("bg_window")),
            "warning": (pal.get("warning"), pal.get("warning"), pal.get("bg_window")),
            "danger": (pal.get("danger", pal.get("error")), pal.get("danger", pal.get("error")), pal.get("bg_window")),
        }
        bg, border_c, fg = mapping.get(bucket, (ctrl_bg, border, muted))
        cell.setStyleSheet(
            f"background: {bg.name()}; border: 1px solid {border_c.name()}; border-radius: 6px; "
            f"color: {fg.name()}; font-weight: 700; padding: 4px 2px;"
        )

    @Slot(list)
    def update_objectives(self, items: List[Dict[str, Any]]) -> None:
        self._obj_cache = list(items)
        while self._obj_container.count():
            child = self._obj_container.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
        pal = get_palette()
        for obj in list(items)[:6]:
            tag = str(obj.get("tag", ""))
            name = str(obj.get("name", ""))
            planned = int(obj.get("planned", 0) or 0)
            total = int(obj.get("total", 0) or 0)
            linked = bool(obj.get("linked", total > 0))

            row_widget = QWidget(self)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            tag_label = QLabel(tag, self)
            tag_label.setStyleSheet(f"color: {pal.get('accent').name()}; font-weight: 700;")
            tag_label.setFixedWidth(56)
            row_layout.addWidget(tag_label)

            mid_col = QVBoxLayout()
            mid_col.setSpacing(3)
            name_label = QLabel(name, self)
            mid_col.addWidget(name_label)
            bar = QProgressBar(self)
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setRange(0, max(total, 1))
            bar.setValue(planned if linked else 0)
            if not linked:
                bar_color = pal.get("danger", pal.get("error"))
            elif planned >= total and total > 0:
                bar_color = pal.get("success", pal.get("accent_alt"))
            else:
                bar_color = pal.get("accent")
            bar.setStyleSheet(
                f"QProgressBar {{ background: {pal.get('ctrl_bg', pal.get('bg_panel')).name()}; "
                f"border: none; border-radius: 3px; }} "
                f"QProgressBar::chunk {{ background: {bar_color.name()}; border-radius: 3px; }}"
            )
            mid_col.addWidget(bar)
            row_layout.addLayout(mid_col, 1)

            stat_text = f"{planned} / {total} planned" if linked else "Not yet linked"
            stat_label = QLabel(stat_text, self)
            stat_label.setProperty("role", "muted")
            row_layout.addWidget(stat_label)

            self._obj_container.addWidget(row_widget)

    @Slot(dict)
    def update_doc_rings(self, forms: Dict[str, Dict[str, Any]]) -> None:
        for key, ring in self._doc_rings.items():
            spec = forms.get(key, {})
            ok = bool(spec.get("ok", False))
            fraction = float(spec.get("fraction", 1.0 if ok else 0.0) or 0.0)
            text = "OK" if ok else f"{int(round(fraction * 100))}%"
            ring.set_state(fraction, ok, text)

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
    def _emit_open_selected_blocker(self) -> None:
        item = self._blockers_list.currentItem()
        if item:
            bid = item.data(Qt.UserRole)
            if bid:
                self.openBlockerRequested.emit(str(bid))

    def _emit_open_selected_approval(self) -> None:
        item = self._approvals_list.currentItem()
        if item:
            aid = item.data(Qt.UserRole)
            if aid:
                self.openApprovalRequested.emit(str(aid))

    def _emit_approve_selected(self) -> None:
        item = self._approvals_list.currentItem()
        if item:
            aid = item.data(Qt.UserRole)
            if aid:
                self.approveRequested.emit(str(aid))


def make_planning_glance_widget(parent: Optional[QWidget] = None) -> PlanningGlanceWidget:
    """Factory for PlanningGlanceWidget."""
    return PlanningGlanceWidget(parent)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    w = PlanningGlanceWidget()
    w.resize(1180, 820)
    w.set_context("3", "18:30", "Planning Section Chief")
    w.update_cycle(
        ["Objectives Meeting", "Strategy Meeting", "Tactics Meeting", "Prep for Ops Briefing", "Ops Briefing", "Execute OP 4"],
        2,
        "1h 42m",
        "Tactics Meeting — OP 4",
        "IAP package due to Command by 20:00",
        "3",
        "96",
    )
    w.update_blockers(
        [
            {"id": "B-1", "title": "ICS-215A safety sign-off missing — Strategy 3 (Div. Bravo)",
             "meta": "Blocks 204 approval · owner: J. Alvarez, Safety Officer", "severity": "critical", "owed": "50m"},
            {"id": "B-2", "title": "Air Ops Recon (Strategy 5) — 2 of 4 aircraft still unassigned",
             "meta": "Logistics has not confirmed availability", "severity": "critical", "owed": "1h 10m"},
            {"id": "B-3", "title": "Division Charlie hasty extension has no approved objective link",
             "meta": "OBJ-08 still in draft — needs Command sign-off", "severity": "high", "owed": "1h 40m"},
            {"id": "B-4", "title": "ICS-205 comms plan not yet reissued for OP 4 channel changes",
             "meta": "Comms Unit — awaiting Tac-3 assignment", "severity": "med", "owed": "2h 5m"},
        ]
    )
    w.update_approvals(
        [
            {"id": "A-1", "title": "Resource Request RR-1142 — 4x ground teams", "who": "Logistics · for Strategy 5", "waited": "38m"},
            {"id": "A-2", "title": "Promote OBJ-09 to OP 4", "who": "Situation Unit", "waited": "22m"},
            {"id": "A-3", "title": "County EM agency request — reunification staffing", "who": "Liaison Officer", "waited": "1h 05m"},
            {"id": "A-4", "title": "Demobilization check-out — Strike Team 2", "who": "Demob Unit", "waited": "15m"},
        ]
    )
    w.update_gaps(
        [
            {"strategy_id": "STR-03", "strategy_name": "Div. Bravo Search Strategy", "org_label": "Div. Bravo",
             "resources": 2, "personnel": 1, "equipment": 0, "hazards": 1, "comms": None},
            {"strategy_id": "STR-06", "strategy_name": "Div. Charlie Hasty Extension", "org_label": "Div. Charlie",
             "resources": 0, "personnel": 0, "equipment": 0, "hazards": 0, "comms": None},
            {"strategy_id": "STR-02", "strategy_name": "Reunification Point Ops", "org_label": "Div. Delta",
             "resources": 0, "personnel": 1, "equipment": 0, "hazards": 0, "comms": None},
            {"strategy_id": "STR-05", "strategy_name": "Air Ops Recon", "org_label": "",
             "resources": 2, "personnel": 1, "equipment": 1, "hazards": None, "comms": 1},
            {"strategy_id": "STR-01", "strategy_name": "Base Camp Logistics Support", "org_label": "",
             "resources": 0, "personnel": 0, "equipment": 0, "hazards": None, "comms": None},
        ]
    )
    w.update_objectives(
        [
            {"tag": "OBJ-04", "name": "Clear eastern drainage corridor", "planned": 1, "total": 2, "linked": True},
            {"tag": "OBJ-07", "name": "Reunification point at Gate 3 staging", "planned": 1, "total": 1, "linked": True},
            {"tag": "OBJ-08", "name": "Extend Div. Charlie hasty search to river corridor", "planned": 0, "total": 1, "linked": True},
            {"tag": "OBJ-09", "name": "Stand up air ops recon window, OP 4", "planned": 0, "total": 0, "linked": False},
        ]
    )
    w.update_doc_rings(
        {
            "202": {"ok": True},
            "203": {"fraction": 0.85},
            "204": {"fraction": 0.30},
            "205": {"ok": True},
            "205A": {"fraction": 0.10},
            "206": {"ok": True},
        }
    )
    w.setAutoRefresh(10_000)
    w.show()
    sys.exit(app.exec())
