"""Liaison dashboard overview — bold status-at-a-glance and quick actions."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.liaison import repository as liaison_repo
from utils.styles import (
    liaison_agency_status_colors,
    liaison_priority_colors,
    liaison_report_state_colors,
    subscribe_theme,
)

OPEN_REQUEST_STATUSES = {"Open", "In Progress"}
OPEN_FEEDBACK_STATUSES = {"Open", "Under Review", "Routed", "Action Required"}
ENGAGED_AGENCY_STATUSES = {"Standby", "Supporting", "Active"}
FOLLOWUP_PRIORITIES = {"High", "Critical"}


def _group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(8, 16, 8, 8)
    lay.setSpacing(5)
    return box, lay


def _stat_card(title: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    frame.setFixedHeight(84)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(6, 8, 6, 8)
    lay.setSpacing(2)
    count = QLabel("0")
    count.setStyleSheet("font-size:30px; font-weight:800; background:transparent;")
    count.setAlignment(Qt.AlignCenter)
    name = QLabel(title)
    name.setStyleSheet("font-size:11px; font-weight:700; letter-spacing:0.05em; background:transparent;")
    name.setAlignment(Qt.AlignCenter)
    name.setWordWrap(True)
    lay.addWidget(count)
    lay.addWidget(name)
    return frame, count


class LiaisonOverviewPanel(QWidget):
    """At-a-glance summary of Liaison activity with links into the working boards."""

    navigate_to = Signal(str)
    action_requested = Signal(str)

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 0)
        root.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(8)

        stats_box, stats_lay = _group("LIAISON STATUS AT A GLANCE")
        stats_row = QHBoxLayout()
        stats_row.setSpacing(6)
        self._stat_cards: dict[str, tuple[QFrame, QLabel]] = {}
        for key, title in [
            ("total_agencies", "AGENCIES\nTRACKED"),
            ("engaged_agencies", "ENGAGED\n(STANDBY+)"),
            ("open_requests", "OPEN CUSTOMER\nREQUESTS"),
            ("priority_followups", "PRIORITY\nFOLLOW-UPS"),
            ("ready_to_report", "READY TO\nREPORT"),
            ("pending_report", "PENDING\nREVIEW"),
        ]:
            card, count_label = _stat_card(title)
            stats_row.addWidget(card)
            self._stat_cards[key] = (card, count_label)
        stats_lay.addLayout(stats_row)
        content_lay.addWidget(stats_box)

        attention_box, attention_lay = _group("AGENCIES NEEDING ATTENTION")
        self._attention_lay = QVBoxLayout()
        attention_lay.addLayout(self._attention_lay)
        content_lay.addWidget(attention_box)

        content_lay.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        bar.setContentsMargins(0, 4, 0, 6)
        for label, action in [
            ("+ Add Agency", "add_agency"),
            ("Log Interaction", "log_interaction"),
            ("Open Agency Directory", "open_agencies"),
            ("Open Reporting Board", "open_reporting"),
            ("Open Customer Requests", "open_customer"),
        ]:
            btn = QPushButton(label)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _=False, a=action: self._handle_action(a))
            bar.addWidget(btn)
        root.addLayout(bar)

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass
        self.refresh()

    def _handle_action(self, action: str) -> None:
        if action == "open_agencies":
            self.navigate_to.emit("Agency Directory")
            return
        if action == "open_reporting":
            self.navigate_to.emit("Reporting Board")
            return
        if action == "open_customer":
            self.navigate_to.emit("Customer Requests & Feedback")
            return
        self.action_requested.emit(action)

    def _on_theme_changed(self, _name: str) -> None:
        self.refresh()

    def refresh(self) -> None:
        try:
            agencies = liaison_repo.fetch_agency_rows(self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Liaison Overview", f"Failed to load agencies:\n{exc}")
            agencies = []
        try:
            requests = liaison_repo.fetch_agency_requests(incident_id=self.incident_id)
        except Exception:
            requests = []
        try:
            feedback = liaison_repo.fetch_feedback_rows(self.incident_id)
        except Exception:
            feedback = []
        try:
            digests = liaison_repo.fetch_reporting_digests(self.incident_id)
        except Exception:
            digests = []

        engaged = [a for a in agencies if a.get("current_status") in ENGAGED_AGENCY_STATUSES]
        open_requests = [r for r in requests if r.get("status") in OPEN_REQUEST_STATUSES]
        open_feedback = [f for f in feedback if f.get("status") in OPEN_FEEDBACK_STATUSES]
        priority_followups = [f for f in open_feedback if f.get("priority") in FOLLOWUP_PRIORITIES]
        ready = [d for d in digests if d.get("ready_to_report")]
        pending = [d for d in digests if not d.get("ready_to_report")]

        agency_colors = liaison_agency_status_colors()
        priority_colors = liaison_priority_colors()
        report_colors = liaison_report_state_colors()

        self._set_card("total_agencies", len(agencies), agency_colors.get("Contacted"))
        self._set_card("engaged_agencies", len(engaged), agency_colors.get("Active"))
        self._set_card("open_requests", len(open_requests), priority_colors.get("Medium"))
        self._set_card("priority_followups", len(priority_followups), priority_colors.get("Critical"))
        self._set_card("ready_to_report", len(ready), report_colors.get("ready"))
        self._set_card("pending_report", len(pending), report_colors.get("not_ready"))

        self._update_attention(agencies)

    def _set_card(self, key: str, value: int, brushes: dict | None) -> None:
        frame, label = self._stat_cards[key]
        label.setText(str(value))
        if brushes:
            bg = brushes["bg"].color().name()
            fg = brushes["fg"].color().name()
            frame.setStyleSheet(f"QFrame {{ background:{bg}; border-radius:6px; }}")
            label.setStyleSheet(f"font-size:30px; font-weight:800; background:transparent; color:{fg};")

    def _update_attention(self, agencies: list[dict[str, Any]]) -> None:
        lay = self._attention_lay
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        needing_attention = [
            a for a in agencies
            if a.get("current_status") in ("Not Contacted", "Awaiting Response")
            or a.get("priority") in FOLLOWUP_PRIORITIES
        ][:8]

        if not needing_attention:
            lay.addWidget(QLabel("No agencies currently flagged for attention."))
            return

        agency_colors = liaison_agency_status_colors()
        priority_colors = liaison_priority_colors()
        for row in needing_attention:
            line = QHBoxLayout()
            name = QLabel(str(row.get("agency_name") or "Unnamed Agency"))
            name.setStyleSheet("font-weight:600;")
            status_text = str(row.get("current_status") or "")
            priority_text = str(row.get("priority") or "")
            status = QLabel(status_text)
            status_brushes = agency_colors.get(status_text)
            if status_brushes:
                status.setStyleSheet(
                    f"background:{status_brushes['bg'].color().name()};"
                    f"color:{status_brushes['fg'].color().name()};"
                    "padding:2px 8px; border-radius:4px; font-weight:700;"
                )
            priority = QLabel(priority_text)
            priority_brushes = priority_colors.get(priority_text)
            if priority_brushes:
                priority.setStyleSheet(
                    f"background:{priority_brushes['bg'].color().name()};"
                    f"color:{priority_brushes['fg'].color().name()};"
                    "padding:2px 8px; border-radius:4px; font-weight:700;"
                )
            line.addWidget(name, 1)
            line.addWidget(status)
            line.addWidget(priority)
            wrapper = QWidget()
            wrapper.setLayout(line)
            lay.addWidget(wrapper)
