"""
LinkedAgencyRequestsPanel
=========================
Tab widget for linking Liaison agency requests (customer / external
requests) to a Work Assignment (Strategy), so the LOFR can see which
strategies are servicing a given request.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository


class LinkedAgencyRequestsPanel(QWidget):
    """Displays and manages Liaison agency request links for one Work Assignment."""

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_bar = QHBoxLayout()
        self._link_btn = QPushButton("Link Agency Request")
        self._unlink_btn = QPushButton("Unlink")
        self._refresh_btn = QPushButton("Refresh")
        for btn in (self._link_btn, self._unlink_btn, self._refresh_btn):
            btn_bar.addWidget(btn)
        btn_bar.addStretch(1)
        layout.addLayout(btn_bar)

        columns = ["Agency", "Request Summary", "Status", "Linked"]
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._table)

        self._link_btn.clicked.connect(self._link_existing)
        self._unlink_btn.clicked.connect(self._unlink)
        self._refresh_btn.clicked.connect(self.reload)

        self.reload()

    def reload(self) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            links = repo.list_linked_agency_requests(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Agency Requests", f"Failed to load links:\n{exc}")
            return
        agencies = self._fetch_agencies()
        self._table.setRowCount(0)
        for link in links:
            row = self._table.rowCount()
            self._table.insertRow(row)
            agency_name = agencies.get(link.get("agency_id"), "")
            self._table.setItem(row, 0, QTableWidgetItem(agency_name))
            self._table.setItem(row, 1, QTableWidgetItem(link.get("request_summary", "")))
            self._table.setItem(row, 2, QTableWidgetItem(link.get("status", "")))
            self._table.setItem(row, 3, QTableWidgetItem(link.get("created_at", "")))
            self._table.item(row, 0).setData(Qt.UserRole, link.get("link_id"))

    def _fetch_agencies(self) -> dict:
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return {}
            rows = api_client.get(f"/api/incidents/{iid}/liaison/agencies") or []
            return {r.get("int_id"): r.get("name", "") for r in rows}
        except Exception:
            return {}

    def _current_link_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        return int(data) if data is not None else None

    def _link_existing(self) -> None:
        dialog = _LinkAgencyRequestDialog(self._work_assignment_id, self._db_path, parent=self)
        dialog.exec()
        self.reload()

    def _unlink(self) -> None:
        link_id = self._current_link_id()
        if link_id is None:
            QMessageBox.information(self, "Unlink", "Select a linked request first.")
            return
        if QMessageBox.question(
            self, "Unlink Request", "Remove this agency request link from the strategy?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.unlink_agency_request(self._work_assignment_id, link_id)
        except Exception as exc:
            QMessageBox.critical(self, "Unlink", f"Failed to unlink request:\n{exc}")
            return
        self.reload()


class _LinkAgencyRequestDialog(QDialog):
    """Simple dialog to search and link an existing Liaison agency request."""

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Agency Request")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path

        layout = QVBoxLayout(self)

        search_bar = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search requests by agency or description…")
        search_btn = QPushButton("Search")
        search_bar.addWidget(self._search_edit)
        search_bar.addWidget(search_btn)
        layout.addLayout(search_bar)

        columns = ["Agency", "Description", "Priority", "Status"]
        self._req_table = QTableWidget(0, len(columns))
        self._req_table.setHorizontalHeaderLabels(columns)
        self._req_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._req_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._req_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._req_table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._link_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        search_btn.clicked.connect(self._search_requests)
        self._search_requests()

    def _search_requests(self) -> None:
        search_text = self._search_edit.text().strip().lower()
        self._req_table.setRowCount(0)
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return
            requests = api_client.get(f"/api/incidents/{iid}/liaison/agency-requests") or []
            agencies = {r.get("int_id"): r.get("name", "") for r in (api_client.get(f"/api/incidents/{iid}/liaison/agencies") or [])}
        except Exception:
            return
        for r in requests:
            agency_name = agencies.get(r.get("agency_id"), "")
            description = r.get("description", "")
            if search_text and search_text not in agency_name.lower() and search_text not in description.lower():
                continue
            row_idx = self._req_table.rowCount()
            self._req_table.insertRow(row_idx)
            self._req_table.setItem(row_idx, 0, QTableWidgetItem(agency_name))
            self._req_table.setItem(row_idx, 1, QTableWidgetItem(description))
            self._req_table.setItem(row_idx, 2, QTableWidgetItem(r.get("priority", "")))
            self._req_table.setItem(row_idx, 3, QTableWidgetItem(r.get("status", "")))
            self._req_table.item(row_idx, 0).setData(Qt.UserRole, r.get("int_id"))

    def _link_selected(self) -> None:
        row = self._req_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Link Request", "Select a request to link.")
            return
        item = self._req_table.item(row, 0)
        request_id = item.data(Qt.UserRole) if item else None
        if request_id is None:
            QMessageBox.warning(self, "Link Request", "Select a request to link.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            result = repo.link_agency_request(self._work_assignment_id, int(request_id))
        except Exception as exc:
            QMessageBox.critical(self, "Link Request", f"Failed to link request:\n{exc}")
            return
        if result is None:
            QMessageBox.information(self, "Link Request", "That request is already linked to this strategy.")
        else:
            QMessageBox.information(self, "Link Request", "Agency request linked successfully.")
        self.accept()
