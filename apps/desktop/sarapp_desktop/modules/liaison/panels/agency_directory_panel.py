"""Agency Directory — primary agency list: stat cards, filter sidebar,
table, and a right-hand detail pane. Data-wired via modules/liaison/repository.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QStandardItem

from modules.liaison import repository as liaison_repo
from modules.liaison.models import AGENCY_STATUSES
from modules.liaison.panels._common import (
    action_bar,
    build_filter_sidebar,
    build_table,
    detail_placeholder,
    stat_row,
    tint_stat_card,
)
from utils.styles import liaison_agency_status_colors, subscribe_theme

_HEADERS = [
    "Agency", "Type", "Primary Contact", "Phone", "Radio/Channel",
    "Status", "Last Contact", "Assigned Liaison",
]

_STAT_TITLES = [
    "TOTAL\nAGENCIES", "ACTIVE\nPARTNERS", "PENDING\nCONTACT",
    "OPEN\nISSUES", "AGREEMENTS\nEXPIRING",
]

_ACTIVE_STATUSES = {"Standby", "Supporting", "Active"}
_PENDING_STATUSES = {"Not Contacted", "Awaiting Response"}


class AgencyDirectoryPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self._rows: list[dict[str, Any]] = []

        root = QVBoxLayout(self)

        row, self._stat_cards = stat_row(_STAT_TITLES)
        root.addLayout(row)

        body = QSplitter(Qt.Horizontal, self)

        self._sidebar = build_filter_sidebar([
            ("Agency Type", ["Law Enforcement", "Fire/EMS", "Government", "NGO", "Private", "Military"]),
            ("Status", list(AGENCY_STATUSES)),
            ("Operational Area", []),
            ("Capabilities", []),
        ])
        body.addWidget(self._sidebar)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.table, self.model = build_table(_HEADERS)
        self.model.setHorizontalHeaderLabels(_HEADERS)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.clicked.connect(lambda _idx: self._show_detail())
        self.table.doubleClicked.connect(lambda _idx: self._open_full_detail())
        center_lay.addWidget(self.table)
        body.addWidget(center)

        detail_wrap = QScrollArea()
        detail_wrap.setWidgetResizable(True)
        detail_wrap.setMinimumWidth(280)
        self._detail = detail_placeholder("Select an agency to view details.")
        detail_wrap.setWidget(self._detail)
        body.addWidget(detail_wrap)

        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setStretchFactor(2, 0)
        root.addWidget(body, 1)

        bottom, self._bottom_buttons = action_bar(["Add Agency", "Import Contacts"])
        self._bottom_buttons["Add Agency"].clicked.connect(self._add_agency)
        root.addLayout(bottom)

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass
        self.reload()

    def _on_theme_changed(self, _name: str) -> None:
        self.reload()

    def reload(self) -> None:
        try:
            self._rows = liaison_repo.fetch_agency_rows(self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Agency Directory", f"Failed to load agencies:\n{exc}")
            self._rows = []
        self._render_table()
        self._render_stats()

    def _render_table(self) -> None:
        self.model.removeRows(0, self.model.rowCount())
        status_colors = liaison_agency_status_colors()
        for row in self._rows:
            values = [
                row.get("agency_name", ""),
                row.get("agency_type", ""),
                row.get("primary_contact", row.get("assigned_liaison", "")),
                row.get("phone", ""),
                row.get("radio_channel", ""),
                row.get("current_status", ""),
                row.get("last_contact", ""),
                row.get("assigned_liaison", ""),
            ]
            items = [QStandardItem(str(v or "")) for v in values]
            items[0].setData(int(row["id"]), Qt.UserRole)
            status = str(row.get("current_status") or "")
            brushes = status_colors.get(status)
            if brushes:
                items[5].setBackground(brushes["bg"])
                items[5].setForeground(brushes["fg"])
            self.model.appendRow(items)
        self.table.resizeColumnsToContents()

    def _render_stats(self) -> None:
        total = len(self._rows)
        active = sum(1 for r in self._rows if r.get("current_status") in _ACTIVE_STATUSES)
        pending = sum(1 for r in self._rows if r.get("current_status") in _PENDING_STATUSES)
        open_issues = sum(int(r.get("open_feedback_items") or 0) for r in self._rows)
        status_colors = liaison_agency_status_colors()
        self._set_stat("TOTAL\nAGENCIES", total, status_colors.get("Contacted"))
        self._set_stat("ACTIVE\nPARTNERS", active, status_colors.get("Active"))
        self._set_stat("PENDING\nCONTACT", pending, status_colors.get("Not Contacted"))
        self._set_stat("OPEN\nISSUES", open_issues, status_colors.get("Awaiting Response"))
        # Agreements expiring — no Agreement backend yet; reported as 0 until wired.
        self._set_stat("AGREEMENTS\nEXPIRING", 0, None)

    def _set_stat(self, key: str, value: int, brushes: dict | None) -> None:
        frame, label = self._stat_cards[key]
        label.setText(str(value))
        tint_stat_card(frame, label, brushes)

    def _selected_row(self) -> dict[str, Any] | None:
        indexes = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.model.item(row, 0)
        agency_id = item.data(Qt.UserRole) if item else None
        return next((r for r in self._rows if int(r.get("id", -1)) == agency_id), None)

    def _show_detail(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        widget = QWidget()
        lay = QVBoxLayout(widget)
        name = QLabel(str(row.get("agency_name") or ""))
        name.setStyleSheet("font-size:16px; font-weight:700;")
        lay.addWidget(name)
        for label, key in [
            ("Type", "agency_type"),
            ("Status", "current_status"),
            ("Assigned Liaison", "assigned_liaison"),
            ("Last Contact", "last_contact"),
            ("Next Contact Due", "next_contact_due"),
            ("Priority", "priority"),
            ("Open Requests", "open_requests"),
            ("Resource Offers", "resource_offers"),
            ("Open Feedback Items", "open_feedback_items"),
        ]:
            lay.addWidget(QLabel(f"{label}: {row.get(key, '')}"))
        actions, _btns = action_bar(["Call", "Email", "Log Contact", "Create Request", "Link Task"])
        lay.addLayout(actions)
        lay.addStretch(1)
        self._detail = widget
        scroll = self.findChild(QScrollArea)
        if scroll is not None:
            scroll.setWidget(widget)

    def _open_full_detail(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        from modules.liaison.windows import AgencyDetailDialog

        dialog = AgencyDetailDialog(int(row["id"]), self.incident_id, self)
        dialog.exec()
        self.reload()

    def _add_agency(self) -> None:
        from modules.liaison.windows import AgencyEditDialog

        dialog = AgencyEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            liaison_repo.create_agency(dialog.values(), self.incident_id)
            self.reload()


def get_agency_directory_panel(incident_id: object | None = None) -> QWidget:
    return AgencyDirectoryPanel(incident_id)
