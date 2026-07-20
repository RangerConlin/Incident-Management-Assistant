"""Agency Status — live operational posture view built around the existing
AgencyStatusBoard table (modules/liaison/windows.py). Adds the stat-card row,
filter sidebar, detail pane, and Status Timeline / Follow-Up Queue sub-tabs
called for in the mockup, without forking the table model.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.liaison.models import AGENCY_STATUSES
from modules.liaison.panels._common import (
    action_bar,
    build_filter_sidebar,
    detail_placeholder,
    stat_row,
    tint_stat_card,
)
from modules.liaison.windows import AgencyDetailDialog, AgencyStatusBoard
from utils.styles import liaison_agency_status_colors, liaison_priority_colors, subscribe_theme

_STAT_TITLES = [
    "NOT\nCONTACTED", "CONTACTED", "MONITORING", "ACTIVE\nPARTNERS",
    "ISSUES", "FOLLOW-UPS\nDUE",
]

_FOLLOWUP_PRIORITIES = {"High", "Critical"}


class AgencyStatusPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id

        root = QVBoxLayout(self)

        row, self._stat_cards = stat_row(_STAT_TITLES)
        root.addLayout(row)

        body = QSplitter(Qt.Horizontal, self)

        self._sidebar = build_filter_sidebar([
            ("Status", list(AGENCY_STATUSES)),
            ("Priority", ["Low", "Medium", "High", "Critical"]),
        ])
        body.addWidget(self._sidebar)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.board = AgencyStatusBoard(incident_id, center)
        self.board.table.clicked.connect(lambda _idx: self._show_detail())
        center_lay.addWidget(self.board)
        body.addWidget(center)

        detail_wrap = QScrollArea()
        detail_wrap.setWidgetResizable(True)
        detail_wrap.setMinimumWidth(280)
        self._detail = detail_placeholder("Select an agency to view its current posture.")
        detail_wrap.setWidget(self._detail)
        body.addWidget(detail_wrap)

        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        root.addWidget(body, 1)

        sub_tabs = QTabWidget(self)
        sub_tabs.addTab(detail_placeholder("Status Timeline — no entries yet."), "Status Timeline")
        sub_tabs.addTab(detail_placeholder("Follow-Up Queue — no follow-ups due."), "Follow-Up Queue")
        sub_tabs.setMaximumHeight(160)
        root.addWidget(sub_tabs)

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass
        self.reload()

    def _on_theme_changed(self, _name: str) -> None:
        self.reload()

    def reload(self) -> None:
        self.board.reload()
        self._render_stats(self._fetch_rows())

    def _fetch_rows(self) -> list[dict[str, Any]]:
        from modules.liaison import repository as liaison_repo

        try:
            return liaison_repo.fetch_agency_rows(self.incident_id)
        except Exception:
            return []

    def _render_stats(self, rows: list[dict[str, Any]]) -> None:
        not_contacted = sum(1 for r in rows if r.get("current_status") == "Not Contacted")
        contacted = sum(1 for r in rows if r.get("current_status") == "Contacted")
        monitoring = sum(1 for r in rows if r.get("current_status") == "Awaiting Response")
        active = sum(1 for r in rows if r.get("current_status") in ("Standby", "Supporting", "Active"))
        issues = sum(int(r.get("open_feedback_items") or 0) for r in rows)
        followups_due = sum(1 for r in rows if r.get("priority") in _FOLLOWUP_PRIORITIES)

        status_colors = liaison_agency_status_colors()
        priority_colors = liaison_priority_colors()
        self._set_stat("NOT\nCONTACTED", not_contacted, status_colors.get("Not Contacted"))
        self._set_stat("CONTACTED", contacted, status_colors.get("Contacted"))
        self._set_stat("MONITORING", monitoring, status_colors.get("Awaiting Response"))
        self._set_stat("ACTIVE\nPARTNERS", active, status_colors.get("Active"))
        self._set_stat("ISSUES", issues, priority_colors.get("Medium"))
        self._set_stat("FOLLOW-UPS\nDUE", followups_due, priority_colors.get("High"))

    def _set_stat(self, key: str, value: int, brushes: dict | None) -> None:
        frame, label = self._stat_cards[key]
        label.setText(str(value))
        tint_stat_card(frame, label, brushes)

    def _show_detail(self) -> None:
        agency_id = self.board._selected_id()
        if agency_id is None:
            return
        from modules.liaison import repository as liaison_repo

        try:
            detail = liaison_repo.fetch_agency_detail(agency_id, self.incident_id)
        except Exception:
            return
        agency = detail.get("agency", {})
        widget = QWidget()
        lay = QVBoxLayout(widget)
        name = QLabel(str(agency.get("name") or ""))
        name.setStyleSheet("font-size:16px; font-weight:700;")
        lay.addWidget(name)
        for label, key in [
            ("Current Status", "current_status"),
            ("Assigned Liaison", "assigned_liaison"),
            ("Last Contact", "last_contact"),
            ("Next Follow-Up", "next_contact_due"),
            ("Priority", "priority"),
            ("Notes", "notes"),
        ]:
            lay.addWidget(QLabel(f"{label}: {agency.get(key, '')}"))
        actions, _btns = action_bar(["Update Status", "Log Contact", "Create Request", "Escalate Issue"])
        lay.addLayout(actions)
        lay.addStretch(1)
        self._detail = widget
        scroll = self.findChild(QScrollArea)
        if scroll is not None:
            scroll.setWidget(widget)

    def open_full_detail(self, agency_id: int) -> None:
        dialog = AgencyDetailDialog(agency_id, self.incident_id, self)
        dialog.exec()
        self.reload()


def get_agency_status_panel(incident_id: object | None = None) -> QWidget:
    return AgencyStatusPanel(incident_id)
