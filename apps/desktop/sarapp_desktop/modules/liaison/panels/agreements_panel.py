"""Agreements — empty-state scaffold.

TODO: there is no Agreement repository/schema yet. Once one exists, wire
reload() to fetch real rows and add an AGREEMENT_STATUSES color vocabulary
to modules/liaison/models.py + styles/styles.py + styles/profiles/*.py
(same pattern as AGENCY_STATUSES/liaison_agency_status_colors) before
coloring the Status column. Never fabricate rows here in the meantime.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QSplitter, QVBoxLayout, QWidget

from modules.liaison.panels._common import (
    action_bar,
    build_filter_sidebar,
    build_table,
    detail_placeholder,
    stat_row,
)

_HEADERS = [
    "Agreement ID", "Agency", "Type", "Scope", "Status",
    "Effective Date", "Expiration", "Owner", "Document",
]

_STAT_TITLES = [
    "ACTIVE\nAGREEMENTS", "EXPIRING\nSOON", "EXPIRED", "DRAFT/\nPENDING",
    "FACILITY\nUSE", "MUTUAL\nAID",
]

_QUEUE_CHIPS = ["Needs Review", "Missing Signatures", "Expiring 30 Days", "Expiring 60 Days", "Expiring 90 Days"]


class AgreementsPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id

        root = QVBoxLayout(self)
        row, self._stat_cards = stat_row(_STAT_TITLES)
        root.addLayout(row)

        body = QSplitter(Qt.Horizontal, self)
        sidebar = build_filter_sidebar([
            ("Agreement Type", ["Mutual Aid", "Facility Use", "MOU", "Contract"]),
            ("Status", ["Active", "Expiring Soon", "Expired", "Draft", "Pending", "Superseded"]),
            ("Agency", []),
            ("Expiration Window", ["30 Days", "60 Days", "90 Days"]),
            ("Operational Area", []),
            ("Document", ["Attached", "Missing"]),
            ("Show Superseded", []),
        ])
        body.addWidget(sidebar)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.table, self.model = build_table(_HEADERS)
        center_lay.addWidget(self.table)

        center_lay.addWidget(QLabel("Renewal / Compliance Queue"))
        chip_row, self._chip_buttons = action_bar(_QUEUE_CHIPS)
        for btn in self._chip_buttons.values():
            btn.setCheckable(True)
        center_lay.addLayout(chip_row)
        queue_table, self.queue_model = build_table(["Agreement", "Agency", "Issue", "Action"])
        queue_table.setMaximumHeight(140)
        center_lay.addWidget(queue_table)
        body.addWidget(center)

        detail_wrap = QScrollArea()
        detail_wrap.setWidgetResizable(True)
        detail_wrap.setMinimumWidth(280)
        detail_wrap.setWidget(detail_placeholder(
            "Select an agreement to view details.\n\n"
            "Agreements have no backing data yet — this tab needs an "
            "Agreement repository/schema before it can load real records."
        ))
        body.addWidget(detail_wrap)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        root.addWidget(body, 1)

        bottom, self._buttons = action_bar(
            ["Open Document", "Add Note", "Start Renewal", "Link Request", "Mark Reviewed"]
        )
        for btn in self._buttons.values():
            btn.setEnabled(False)
        root.addLayout(bottom)

        self.reload()

    def reload(self) -> None:
        for _title, (_frame, label) in self._stat_cards.items():
            label.setText("0")


def get_agreements_panel(incident_id: object | None = None) -> QWidget:
    return AgreementsPanel(incident_id)
