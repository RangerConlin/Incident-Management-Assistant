"""Incident personnel view for Logistics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.checkin.models import RESOURCE_STATUSES, RosterFilters
from modules.logistics.checkin.repository import fetch_roster, list_history
from utils import incident_context
from utils.api_client import api_client
from utils.styles import get_palette, subscribe_theme


@dataclass(slots=True)
class _PersonnelRow:
    person_record: int
    person_id: str
    name: str
    role: str
    team: str
    callsign: str
    phone: str
    status: str
    updated_at: str

    @classmethod
    def from_roster(cls, row: Any) -> "_PersonnelRow":
        return cls(
            person_record=int(getattr(row, "person_record", 0) or 0),
            person_id=str(getattr(row, "person_id", "") or ""),
            name=str(getattr(row, "name", "") or ""),
            role=str(getattr(row, "role", "") or ""),
            team=str(getattr(row, "team", "") or ""),
            callsign=str(getattr(row, "callsign", "") or ""),
            phone=str(getattr(row, "phone", "") or ""),
            status=str(getattr(row, "ci_status", "") or ""),
            updated_at=str(getattr(row, "updated_at", "") or ""),
        )


class LogisticsPersonnelManagerPanel(QWidget):
    """Logistics-facing roster built from incident resource-status personnel rows."""

    _HEADERS = ("Name", "ID", "Role", "Team", "Callsign", "Phone", "Status", "Updated")

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if incident_id is not None:
            incident_context.set_active_incident(str(incident_id))
        self.setObjectName("LogisticsPersonnelManagerPanel")
        self.setWindowTitle("Personnel Manager")
        self._rows: list[_PersonnelRow] = []
        self._build_ui()
        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Personnel Manager")
        title.setObjectName("panelTitle")
        self._context = QLabel("")
        self._context.setObjectName("panelContext")
        title_col.addWidget(title)
        title_col.addWidget(self._context)
        header.addLayout(title_col, 1)

        self._summary = QLabel("")
        self._summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._summary.setObjectName("panelSummary")
        header.addWidget(self._summary)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name, ID, callsign, or phone")
        self._search.returnPressed.connect(self.refresh)
        self._status = QComboBox()
        self._status.addItem("All")
        for status in RESOURCE_STATUSES:
            self._status.addItem(status)
        self._status.currentIndexChanged.connect(self.refresh)
        self._include_inactive = QComboBox()
        self._include_inactive.addItem("Active only", False)
        self._include_inactive.addItem("Include not coming", True)
        self._include_inactive.currentIndexChanged.connect(self.refresh)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        checkin_btn = QPushButton("Open Check-In")
        checkin_btn.clicked.connect(self._open_checkin)
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self._open_selected_person)
        history_btn = QPushButton("History")
        history_btn.clicked.connect(self._show_selected_history)

        filters.addWidget(self._search, 2)
        filters.addWidget(self._status)
        filters.addWidget(self._include_inactive)
        filters.addWidget(refresh_btn)
        filters.addWidget(checkin_btn)
        filters.addWidget(open_btn)
        filters.addWidget(history_btn)
        layout.addLayout(filters)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        available_btn = QPushButton("Available")
        available_btn.clicked.connect(lambda: self._set_selected_status("Available"))
        assigned_btn = QPushButton("Assigned")
        assigned_btn.clicked.connect(lambda: self._set_selected_status("Assigned"))
        prep_demob_btn = QPushButton("Prep Demob")
        prep_demob_btn.clicked.connect(lambda: self._set_selected_status("Preparing for Demobilization"))
        demob_btn = QPushButton("Demobilized")
        demob_btn.clicked.connect(lambda: self._set_selected_status("Demobilized"))
        for button in (available_btn, assigned_btn, prep_demob_btn, demob_btn):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._table = QTableWidget(0, len(self._HEADERS), self)
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._open_selected_person)
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setStretchLastSection(True)
        layout.addWidget(self._table, 1)

    def _apply_styles(self) -> None:
        pal = get_palette()
        bg = pal.get("bg_panel", pal["bg"]).name()
        fg = pal.get("fg_primary", pal["fg"]).name()
        muted = pal.get("fg_muted", pal["muted"]).name()
        border = pal.get("ctrl_border", pal["divider"]).name()
        selection = pal.get("selection_bg", pal.get("accent")).name()
        self.setStyleSheet(
            f"""
            QWidget#LogisticsPersonnelManagerPanel {{
                background: {pal.get("bg_window", pal["bg"]).name()};
                color: {fg};
            }}
            QLabel#panelTitle {{
                font-size: 18px;
                font-weight: 600;
            }}
            QLabel#panelContext,
            QLabel#panelSummary {{
                color: {muted};
            }}
            QTableWidget {{
                background: {bg};
                color: {fg};
                gridline-color: {border};
                border: 1px solid {border};
                selection-background-color: {selection};
            }}
            QTableWidget::item:selected {{
                border: 1px solid {fg};
            }}
            """
        )

    def refresh(self) -> None:
        incident_id = incident_context.get_active_incident_id()
        self._context.setText(f"Incident: {incident_id or 'No active incident'}")
        if not incident_id:
            self._rows = []
            self._populate()
            return

        status = self._status.currentText()
        filters = RosterFilters(
            q=self._search.text().strip() or None,
            ci_status=status if status != "All" else None,
            include_no_show=bool(self._include_inactive.currentData()),
        )
        self._rows = [_PersonnelRow.from_roster(row) for row in fetch_roster(filters)]
        self._populate()

    def _populate(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            values = (
                row.name,
                row.person_id,
                row.role,
                row.team,
                row.callsign,
                row.phone,
                row.status,
                row.updated_at,
            )
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row.person_record)
                self._table.setItem(row_index, col_index, item)
        self._table.setSortingEnabled(True)
        self._summary.setText(self._summary_text())
        self._table.resizeRowsToContents()

    def _summary_text(self) -> str:
        total = len(self._rows)
        assigned = sum(1 for row in self._rows if row.status == "Assigned")
        available = sum(1 for row in self._rows if row.status in {"Available", "Checked In"})
        demob = sum(1 for row in self._rows if row.status == "Demobilized")
        return f"{total} personnel | {available} available | {assigned} assigned | {demob} demobilized"

    def _selected_person_record(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        value = items[0].data(Qt.UserRole)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _open_selected_person(self) -> None:
        person_record = self._selected_person_record()
        if person_record is None:
            QMessageBox.information(self, "Personnel Manager", "Select a person first.")
            return
        try:
            from ui.personnel import PersonnelDetailDialog

            dialog = PersonnelDetailDialog(self, person_record=person_record)
            dialog.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Personnel Manager", f"Could not open personnel detail.\n{exc}")

    def _open_checkin(self) -> None:
        try:
            from modules.logistics.checkin import CheckInPanel

            panel = CheckInPanel()
            panel.setAttribute(Qt.WA_DeleteOnClose, True)
            panel.show()
        except Exception as exc:
            QMessageBox.warning(self, "Personnel Manager", f"Could not open Check-In.\n{exc}")

    def _set_selected_status(self, status: str) -> None:
        person_record = self._selected_person_record()
        incident_id = incident_context.get_active_incident_id()
        if person_record is None:
            QMessageBox.information(self, "Personnel Manager", "Select a person first.")
            return
        if not incident_id:
            QMessageBox.information(self, "Personnel Manager", "Open an incident before changing status.")
            return
        try:
            api_client.patch(
                f"/api/incidents/{incident_id}/checkin/{person_record}/status",
                json={"status": status},
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Personnel Manager", f"Could not update status.\n{exc}")

    def _show_selected_history(self) -> None:
        person_record = self._selected_person_record()
        if person_record is None:
            QMessageBox.information(self, "Personnel Manager", "Select a person first.")
            return
        items = list_history(person_record)
        dialog = QDialog(self)
        dialog.setWindowTitle("Personnel Status History")
        dialog.resize(640, 420)
        layout = QVBoxLayout(dialog)
        title = QLabel(self._selected_person_label(person_record))
        title.setObjectName("historyTitle")
        layout.addWidget(title)
        table = QTableWidget(0, 4, dialog)
        table.setHorizontalHeaderLabels(("Time", "Event", "Actor", "Details"))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setRowCount(len(items))
        for row_index, item in enumerate(items):
            payload = item.payload or {}
            detail = payload.get("status") or ", ".join(f"{k}: {v}" for k, v in payload.items())
            values = (item.ts, item.event_type, item.actor, str(detail or ""))
            for col_index, value in enumerate(values):
                table.setItem(row_index, col_index, QTableWidgetItem(str(value or "")))
        table.resizeRowsToContents()
        layout.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _selected_person_label(self, person_record: int) -> str:
        for row in self._rows:
            if row.person_record == person_record:
                visible_id = f" ({row.person_id})" if row.person_id else ""
                return f"{row.name or person_record}{visible_id}"
        return str(person_record)


__all__ = ["LogisticsPersonnelManagerPanel"]
