"""Liaison Log — empty-state scaffold for the chronological activity log.

Distinct from reporting_board.py (reporting digests) and customer_board.py
(customer requests/feedback) — this is a time-ordered log of liaison
activity (contacts, status updates, issues, follow-ups).

TODO: there is no LiaisonLogEntry repository/schema yet. Once one exists,
wire reload() to fetch real rows (and add a color vocabulary for the entry
Type badges — Contact Made/Request Sent/Status Update/etc — following the
liaison_agency_status_colors pattern) before coloring the Type column.
Never fabricate rows here in the meantime.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from modules.liaison.panels._common import (
    action_bar,
    build_filter_sidebar,
    build_table,
    detail_placeholder,
    stat_row,
)

_HEADERS = [
    "Time", "Type", "Agency/Contact", "Summary", "Linked Item", "Priority", "Entered By",
]

_STAT_TITLES = [
    "ENTRIES\nTODAY", "CONTACTS\nMADE", "REQUESTS\nUPDATED",
    "ISSUES\nLOGGED", "FOLLOW-UPS\nCREATED", "EXPORT\nREADY",
]

_EXPORT_SECTIONS = [
    "Liaison Log", "Agency Contact List", "Agreements Summary",
    "Open Requests Report", "Issues Summary",
]


class LiaisonLogPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id

        root = QVBoxLayout(self)
        row, self._stat_cards = stat_row(_STAT_TITLES)
        root.addLayout(row)

        toolbar, self._toolbar_buttons = action_bar(["+ Add Log Entry", "Export Log", "Print Log"])
        for btn in self._toolbar_buttons.values():
            btn.setEnabled(False)
        root.addLayout(toolbar)

        body = QSplitter(Qt.Horizontal, self)
        sidebar = build_filter_sidebar([
            ("Date Range", ["Custom From/To"]),
            ("Agency", []),
            ("Contact", []),
            ("Entry Type", [
                "Contact Made", "Request Sent", "Status Update", "Issue Noted",
                "Agreement Reviewed", "Agency Rep Arrived", "Follow-Up Created",
            ]),
            ("Priority", ["Low", "Medium", "High", "Critical"]),
            ("Entered By", []),
            ("Flags", ["Show Follow-Up Required Only"]),
        ])
        body.addWidget(sidebar)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.table, self.model = build_table(_HEADERS)
        center_lay.addWidget(self.table)

        bottom_row = QHBoxLayout()
        followup_box = QGroupBox("Follow-Up Queue")
        followup_lay = QVBoxLayout(followup_box)
        self.followup_table, self.followup_model = build_table(["Entry", "Due", "Assigned To"])
        followup_lay.addWidget(self.followup_table)
        bottom_row.addWidget(followup_box, 1)

        export_box = QGroupBox("Export Checklist")
        export_lay = QVBoxLayout(export_box)
        self._export_checks: dict[str, QCheckBox] = {}
        for section in _EXPORT_SECTIONS:
            cb = QCheckBox(section, export_box)
            export_lay.addWidget(cb)
            self._export_checks[section] = cb
        export_actions, self._export_buttons = action_bar(
            ["Export Selected", "Save Export Plan", "Schedule Export"]
        )
        for btn in self._export_buttons.values():
            btn.setEnabled(False)
        export_lay.addLayout(export_actions)
        bottom_row.addWidget(export_box, 1)

        center_lay.addLayout(bottom_row)
        body.addWidget(center)

        detail_wrap = QScrollArea()
        detail_wrap.setWidgetResizable(True)
        detail_wrap.setMinimumWidth(280)
        detail_wrap.setWidget(detail_placeholder(
            "Select a log entry to view details.\n\n"
            "The Liaison Log has no backing data yet — this tab needs a "
            "LiaisonLogEntry repository/schema before it can load real records."
        ))
        body.addWidget(detail_wrap)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        root.addWidget(body, 1)

        self.reload()

    def reload(self) -> None:
        for _title, (_frame, label) in self._stat_cards.items():
            label.setText("0")


def get_liaison_log_panel(incident_id: object | None = None) -> QWidget:
    return LiaisonLogPanel(incident_id)
