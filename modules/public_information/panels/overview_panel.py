"""PIO Dashboard overview — three-column layout."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.public_information.services import PublicInformationRepository

# ── colour palette ────────────────────────────────────────────────────────────
_STATUS_BG: dict[str, str] = {
    "Draft":                 "#6B7280",
    "Pending Approval":      "#D97706",
    "Returned for Revision": "#7C3AED",
    "Approved":              "#059669",
    "Published":             "#1D4ED8",
    "Needs Corrections":     "#DC2626",
}

_SEVERITY_COLOR: dict[str, str] = {
    "Critical": "#DC2626",
    "High":     "#EA580C",
    "Moderate": "#D97706",
    "Low":      "#6B7280",
}

_GROUP_STYLE = (
    "QGroupBox { font-weight:700; font-size:12px; letter-spacing:0.05em; "
    "border:1px solid #3F3F46; border-radius:6px; margin-top:8px; padding-top:6px; }"
    "QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }"
)
_CARD_STYLE = "QFrame { background:#1C1C1E; border:1px solid #3F3F46; border-radius:6px; }"

_ACTION_STYLE = (
    "QPushButton { background:#1E3A5F; color:#FFFFFF; border:none; border-radius:5px; "
    "font-weight:700; font-size:13px; padding:8px 4px; }"
    "QPushButton:hover { background:#2D5282; }"
)
_ACTION_PRIMARY = (
    "QPushButton { background:#14532D; color:#FFFFFF; border:none; border-radius:5px; "
    "font-weight:700; font-size:13px; padding:8px 4px; }"
    "QPushButton:hover { background:#166534; }"
)
_LINK_STYLE = (
    "QPushButton { border:none; color:#60A5FA; font-size:12px; "
    "text-align:left; padding:2px 0; background:transparent; }"
    "QPushButton:hover { color:#93C5FD; }"
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _card() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.StyledPanel)
    f.setStyleSheet(_CARD_STYLE)
    return f


def _group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    box.setStyleSheet(_GROUP_STYLE)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(8, 16, 8, 8)
    lay.setSpacing(5)
    return box, lay


def _lbl(text: str = "", bold: bool = False, size: int = 13, color: str = "") -> QLabel:
    w = QLabel(text)
    w.setWordWrap(True)
    css = f"font-size:{size}px;"
    if bold:
        css += "font-weight:700;"
    if color:
        css += f"color:{color};"
    w.setStyleSheet(css)
    return w


def _hr() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#3F3F46;")
    return f


def _sev_badge(severity: str) -> QLabel:
    color = _SEVERITY_COLOR.get(severity, "#6B7280")
    w = QLabel(severity.upper())
    w.setStyleSheet(
        f"background:{color}; color:#FFF; border-radius:3px; "
        "padding:1px 6px; font-size:11px; font-weight:700;"
    )
    w.setFixedHeight(20)
    return w


# ── left column panels ────────────────────────────────────────────────────────

class _RumorWatchPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, self._lay = _group("RUMOR WATCH")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        self._placeholder = _lbl("No active rumors.", color="#9CA3AF")
        self._lay.addWidget(self._placeholder)
        link = QPushButton("View All Rumors →")
        link.setStyleSheet(_LINK_STYLE)
        self._lay.addWidget(link)

    def update_items(self, items: list[dict[str, Any]]) -> None:
        lay = self._lay
        while lay.count():
            w = lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        active = [i for i in items if i.get("status") not in ("Closed", "Corrected")][:5]
        if not active:
            lay.addWidget(_lbl("No active rumors.", color="#9CA3AF"))
        else:
            for row in active:
                rw = QWidget()
                rl = QVBoxLayout(rw)
                rl.setContentsMargins(0, 3, 0, 3)
                rl.setSpacing(2)
                top = QHBoxLayout()
                top.addWidget(_sev_badge(row.get("severity", "Low")))
                top.addWidget(_lbl((row.get("claim_rumor") or "")[:70], bold=True, size=12), 1)
                rl.addLayout(top)
                src = row.get("platform") or row.get("source") or ""
                ts = row.get("first_seen") or ""
                meta = _lbl(f"Origin: {src}   {ts}", size=11, color="#9CA3AF")
                rl.addWidget(meta)
                lay.addWidget(rw)
                lay.addWidget(_hr())
        link = QPushButton("View All Rumors →")
        link.setStyleSheet(_LINK_STYLE)
        lay.addWidget(link)


class _MediaInquiriesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, self._lay = _group("MEDIA INQUIRIES")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        # due-soon / overdue row
        counts_row = QHBoxLayout()
        due_card = _card()
        due_in = QVBoxLayout(due_card)
        due_in.setContentsMargins(8, 6, 8, 6)
        self._due_soon = _lbl("0", bold=True, size=24, color="#D97706")
        self._due_soon.setAlignment(Qt.AlignCenter)
        due_in.addWidget(_lbl("DUE SOON (≤2 HRS)", size=10, color="#9CA3AF"))
        due_in.addWidget(self._due_soon)
        over_card = _card()
        over_in = QVBoxLayout(over_card)
        over_in.setContentsMargins(8, 6, 8, 6)
        self._overdue = _lbl("0", bold=True, size=24, color="#DC2626")
        self._overdue.setAlignment(Qt.AlignCenter)
        over_in.addWidget(_lbl("OVERDUE", size=10, color="#9CA3AF"))
        over_in.addWidget(self._overdue)
        counts_row.addWidget(due_card)
        counts_row.addWidget(over_card)
        self._lay.addLayout(counts_row)
        self._list_lay = QVBoxLayout()
        self._lay.addLayout(self._list_lay)
        link = QPushButton("Open Media Log →")
        link.setStyleSheet(_LINK_STYLE)
        self._lay.addWidget(link)

    def update_items(self, items: list[dict], due_soon: int = 0, overdue: int = 0) -> None:
        self._due_soon.setText(str(due_soon))
        self._overdue.setText(str(overdue))
        while self._list_lay.count():
            w = self._list_lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        for row in items[:5]:
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.addWidget(_lbl(row.get("outlet_agency") or "Unknown", bold=True, size=12), 1)
            rl.addWidget(_lbl(row.get("deadline") or "", size=12, color="#DC2626"))
            self._list_lay.addWidget(rw)


class _UpcomingBriefingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, self._lay = _group("UPCOMING BRIEFINGS")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        self._lay.addWidget(_lbl("No briefings scheduled.", color="#9CA3AF"))


# ── center column panels ──────────────────────────────────────────────────────

class _StatusCardsPanel(QWidget):
    """Six large colored status cards — Draft through Needs Corrections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        box, lay = _group("MESSAGE STATUS")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        row = QHBoxLayout()
        row.setSpacing(5)
        self._counts: dict[str, QLabel] = {}
        items = [
            ("Draft",                 "DRAFTS"),
            ("Pending Approval",      "PENDING\nAPPROVAL"),
            ("Returned for Revision", "RETURNED"),
            ("Approved",              "APPROVED"),
            ("Published",             "PUBLISHED"),
            ("Needs Corrections",     "NEEDS\nCORRECTIONS"),
        ]
        for key, label in items:
            bg = _STATUS_BG.get(key, "#6B7280")
            card = QFrame()
            card.setStyleSheet(f"QFrame {{ background:{bg}; border-radius:6px; }}")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card.setFixedHeight(80)
            ci = QVBoxLayout(card)
            ci.setContentsMargins(4, 6, 4, 6)
            ci.setSpacing(2)
            count = QLabel("0")
            count.setStyleSheet(
                "color:#FFFFFF; font-size:30px; font-weight:700; background:transparent;"
            )
            count.setAlignment(Qt.AlignCenter)
            name = QLabel(label)
            name.setStyleSheet(
                "color:#FFFFFF; font-size:10px; font-weight:700; "
                "letter-spacing:0.04em; background:transparent;"
            )
            name.setAlignment(Qt.AlignCenter)
            ci.addWidget(count)
            ci.addWidget(name)
            row.addWidget(card)
            self._counts[key] = count
        lay.addLayout(row)

    def update_counts(self, counts: dict[str, int]) -> None:
        for key, lbl in self._counts.items():
            lbl.setText(str(counts.get(key, 0)))


class _KeyMessagePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, lay = _group("TODAY'S KEY MESSAGE")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        row = QHBoxLayout()
        self._body = _lbl("No key message set.", color="#D1D5DB", size=13)
        self._body.setWordWrap(True)
        row.addWidget(self._body, 1)
        right = QVBoxLayout()
        right.addWidget(_lbl("LAST PUBLISHED", size=10, bold=True, color="#9CA3AF"))
        self._pub_title = _lbl("—", bold=True, size=13, color="#60A5FA")
        self._pub_time = _lbl("", size=11, color="#9CA3AF")
        right.addWidget(self._pub_title)
        right.addWidget(self._pub_time)
        right.addStretch(1)
        row.addLayout(right)
        lay.addLayout(row)
        link = QPushButton("View All Messages →")
        link.setStyleSheet(_LINK_STYLE)
        lay.addWidget(link)

    def update(self, body: str, pub_title: str, pub_time: str) -> None:
        self._body.setText(body or "No key message set.")
        self._pub_title.setText(pub_title or "—")
        self._pub_time.setText(pub_time or "")


class _PipelineBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, lay = _group("MESSAGE PIPELINE")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        self._keys = [
            "Draft", "Pending Approval", "Returned for Revision", "Approved", "Published",
        ]
        labels = ["Draft", "Pending\nApproval", "Returned\nfor Rev.", "Approved", "Published"]
        self._count_labels: list[QLabel] = []
        top_row = QHBoxLayout()
        count_row = QHBoxLayout()
        for label, key in zip(labels, self._keys):
            color = _STATUS_BG.get(key, "#6B7280")
            tl = _lbl(label, size=11, color="#9CA3AF")
            tl.setAlignment(Qt.AlignCenter)
            top_row.addWidget(tl, 1)
            cl = _lbl("0", bold=True, size=15, color=color)
            cl.setAlignment(Qt.AlignCenter)
            count_row.addWidget(cl, 1)
            self._count_labels.append(cl)
        lay.addLayout(top_row)
        lay.addLayout(count_row)
        # segmented bar
        self._bar = QFrame()
        self._bar.setFixedHeight(12)
        self._bar.setStyleSheet("background:#27272A; border-radius:6px;")
        bar_lay = QHBoxLayout(self._bar)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(2)
        self._segs: list[QFrame] = []
        for key in self._keys:
            seg = QFrame()
            seg.setFixedHeight(12)
            seg.setStyleSheet(f"background:{_STATUS_BG.get(key, '#6B7280')}; border-radius:6px;")
            bar_lay.addWidget(seg, 1)
            self._segs.append(seg)
        lay.addWidget(self._bar)

    def update_counts(self, counts: dict[str, int]) -> None:
        values = [counts.get(k, 0) for k in self._keys]
        total = max(sum(values), 1)
        for i, (v, seg) in enumerate(zip(values, self._segs)):
            self._count_labels[i].setText(str(v))
            seg.setVisible(True)


# ── right column panels ───────────────────────────────────────────────────────

class _TalkingPointsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, self._lay = _group("APPROVED TALKING POINTS")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        self._lay.addWidget(_lbl("No approved talking points.", color="#9CA3AF"))

    def update_items(self, items: list[dict]) -> None:
        while self._lay.count():
            w = self._lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        approved = [i for i in items if i.get("status") == "Approved"][:6]
        if not approved:
            self._lay.addWidget(_lbl("No approved talking points.", color="#9CA3AF"))
            return
        for tp in approved:
            rw = QWidget()
            rl = QVBoxLayout(rw)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(1)
            rl.addWidget(_lbl(tp.get("category") or "", size=10, color="#9CA3AF"))
            rl.addWidget(_lbl(tp.get("title") or "", bold=True, size=12))
            self._lay.addWidget(rw)
            self._lay.addWidget(_hr())


class _DistributionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, lay = _group("DISTRIBUTION STATUS")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        hdr = QHBoxLayout()
        hdr.addWidget(_lbl("CHANNEL", size=10, bold=True, color="#9CA3AF"), 2)
        hdr.addWidget(_lbl("SENT / NOT SENT", size=10, bold=True, color="#9CA3AF"), 1)
        hdr.addWidget(_lbl("STATUS", size=10, bold=True, color="#9CA3AF"))
        lay.addLayout(hdr)
        lay.addWidget(_hr())
        self._rows_lay = QVBoxLayout()
        lay.addLayout(self._rows_lay)
        link = QPushButton("View All Channels →")
        link.setStyleSheet(_LINK_STYLE)
        lay.addWidget(link)

    def update_records(self, records: list[dict], channels: list[str]) -> None:
        while self._rows_lay.count():
            w = self._rows_lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        distributed = {r.get("channel") for r in records}
        for ch in channels:
            sent = ch in distributed
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.addWidget(_lbl(ch, size=12, color="#D1D5DB"), 2)
            rl.addWidget(_lbl("1 / 0" if sent else "0 / 1", size=12, color="#9CA3AF"), 1)
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{'#10B981' if sent else '#D97706'}; font-size:16px;")
            rl.addWidget(dot)
            self._rows_lay.addWidget(rw)


class _RecentReleasesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        box, self._lay = _group("RECENT RELEASES")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(box)
        self._lay.addWidget(_lbl("No recent releases.", color="#9CA3AF"))

    def update_items(self, messages: list[dict]) -> None:
        while self._lay.count():
            w = self._lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        published = [m for m in messages if m.get("status") == "Published"][:5]
        if not published:
            self._lay.addWidget(_lbl("No recent releases.", color="#9CA3AF"))
            return
        for msg in published:
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 3, 0, 3)
            title = _lbl(msg.get("title") or f"Release #{msg.get('id')}", bold=True, size=12)
            ts = _lbl(str(msg.get("published_at") or msg.get("updated_at") or ""), size=11, color="#9CA3AF")
            badge = QLabel("PUBLISHED")
            badge.setStyleSheet(
                "background:#1D4ED8; color:#FFF; border-radius:3px; "
                "padding:1px 5px; font-size:10px; font-weight:700;"
            )
            rl.addWidget(title, 1)
            rl.addWidget(ts)
            rl.addWidget(badge)
            self._lay.addWidget(rw)
            self._lay.addWidget(_hr())


# ── main overview ─────────────────────────────────────────────────────────────

class PIOOverviewPanel(QWidget):
    navigate_to = Signal(str)

    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 0)
        root.setSpacing(6)

        # three-column scroll area
        cols = QHBoxLayout()
        cols.setSpacing(8)

        # left column
        left = QVBoxLayout()
        left.setSpacing(6)
        self._rumor = _RumorWatchPanel()
        self._media = _MediaInquiriesPanel()
        self._briefings = _UpcomingBriefingsPanel()
        left.addWidget(self._rumor)
        left.addWidget(self._media)
        left.addWidget(self._briefings)
        left.addStretch(1)
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(290)

        # center column
        center = QVBoxLayout()
        center.setSpacing(6)
        self._status_cards = _StatusCardsPanel()
        self._key_message = _KeyMessagePanel()
        self._pipeline = _PipelineBar()
        center.addWidget(self._status_cards)
        center.addWidget(self._key_message)
        center.addWidget(self._pipeline)
        center.addStretch(1)
        center_w = QWidget()
        center_w.setLayout(center)

        # right column
        right = QVBoxLayout()
        right.setSpacing(6)
        self._talking_points = _TalkingPointsPanel()
        self._distribution = _DistributionPanel()
        self._recent = _RecentReleasesPanel()
        right.addWidget(self._talking_points)
        right.addWidget(self._distribution)
        right.addWidget(self._recent)
        right.addStretch(1)
        right_w = QWidget()
        right_w.setLayout(right)
        right_w.setFixedWidth(310)

        cols.addWidget(left_w)
        cols.addWidget(center_w, 1)
        cols.addWidget(right_w)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setLayout(cols)
        scroll.setWidget(content)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, 1)

        # bottom action bar
        bar = QHBoxLayout()
        bar.setSpacing(4)
        bar.setContentsMargins(0, 4, 0, 6)
        _actions = [
            ("+ NEW RELEASE\nCreate Public Release",             "Messages / Releases", False),
            ("≡ OPEN MEDIA LOG\nTrack Inquiries & Responses",    "Media Log",           False),
            ("✎ DRAFT RESPONSE\nCreate Message / Statement",     "Messages / Releases", False),
            ("✉ PUBLISH UPDATE\nSend to All Channels",           "Distribution Log",    True),
            ("⊞ VIEW APPROVAL QUEUE\nReview & Approve Messages", "Messages / Releases", False),
        ]
        for label, section, primary in _actions:
            btn = QPushButton(label)
            btn.setStyleSheet(_ACTION_PRIMARY if primary else _ACTION_STYLE)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(58)
            btn.clicked.connect(lambda _=False, s=section: self.navigate_to.emit(s))
            bar.addWidget(btn)
        root.addLayout(bar)

        self.refresh()

    def refresh(self) -> None:
        from modules.public_information.models.constants import DISTRIBUTION_CHANNELS

        messages = self.repo.list_messages()
        misinfo = self.repo.list_records("pio_misinformation_items", "last_update DESC, id DESC")
        media = self.repo.list_records("pio_media_log", "time DESC, id DESC")
        talking = self.repo.list_records("pio_talking_points", "updated_at DESC, id DESC")
        dist = self.repo.list_records("pio_distribution_log", "distributed_at DESC, id DESC")

        counts: dict[str, int] = {}
        for m in messages:
            s = m.get("status", "Draft")
            counts[s] = counts.get(s, 0) + 1
        self._status_cards.update_counts(counts)
        self._pipeline.update_counts(counts)

        published = [m for m in messages if m.get("status") == "Published"]
        approved = [m for m in messages if m.get("status") == "Approved"]
        key_source = approved[0] if approved else (published[0] if published else None)
        last_pub = published[0] if published else None
        self._key_message.update(
            (key_source.get("body") or "")[:200] if key_source else "",
            (last_pub or {}).get("title", "—"),
            (last_pub or {}).get("published_at") or (last_pub or {}).get("updated_at") or "",
        )

        self._rumor.update_items(misinfo)
        overdue = [m for m in media if m.get("status") in ("New", "Assigned") and m.get("deadline")]
        self._media.update_items(media, due_soon=len(overdue), overdue=0)
        self._talking_points.update_items(talking)
        self._distribution.update_records(dist[:20], DISTRIBUTION_CHANNELS[:7])
        self._recent.update_items(messages)
