"""Contacts — empty-state scaffold.

TODO: there is no standalone Contact repository/schema yet (only the
Agency.assigned_liaison string field). Once a Contact collection/API exists,
wire reload() to fetch real rows the same way agency_directory_panel does.
Never fabricate rows here in the meantime.
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
    "Name", "Title/Role", "Agency", "Phone", "Email",
    "Radio/Channel", "Availability", "Verified", "Last Contact",
]

_STAT_TITLES = [
    "TOTAL\nCONTACTS", "DUTY\nOFFICERS", "AFTER-HOURS\nCONTACTS",
    "NEEDS\nVERIFICATION", "RECENT\nUPDATES",
]


class ContactsPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id

        root = QVBoxLayout(self)
        row, self._stat_cards = stat_row(_STAT_TITLES)
        root.addLayout(row)

        body = QSplitter(Qt.Horizontal, self)
        sidebar = build_filter_sidebar([
            ("Role/Title", []),
            ("Availability", ["Business Hours", "After-Hours", "24/7"]),
            ("Contact Method", ["Phone", "Email", "Radio"]),
            ("Flags", ["After-Hours Only", "Needs Verification"]),
            ("Saved Views", []),
        ])
        body.addWidget(sidebar)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.table, self.model = build_table(_HEADERS)
        center_lay.addWidget(self.table)
        recent = detail_placeholder("Recent Contact Activity — no data yet.")
        recent.setMaximumHeight(120)
        center_lay.addWidget(QLabel("Recent Contact Activity"))
        center_lay.addWidget(recent)
        body.addWidget(center)

        detail_wrap = QScrollArea()
        detail_wrap.setWidgetResizable(True)
        detail_wrap.setMinimumWidth(280)
        detail_wrap.setWidget(detail_placeholder(
            "Select a contact to view details.\n\n"
            "Contacts have no backing data yet — this tab needs a Contact "
            "repository/schema before it can load real records."
        ))
        body.addWidget(detail_wrap)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        root.addWidget(body, 1)

        bottom, self._buttons = action_bar(["Call", "Email", "Log Contact", "Create Request", "Open Agency"])
        for btn in self._buttons.values():
            btn.setEnabled(False)
        root.addLayout(bottom)

        self.reload()

    def reload(self) -> None:
        for _title, (_frame, label) in self._stat_cards.items():
            label.setText("0")


def get_contacts_panel(incident_id: object | None = None) -> QWidget:
    return ContactsPanel(incident_id)
