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
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import get_palette


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
        layout.setSpacing(12)

        btn_bar = QHBoxLayout()
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        self._link_btn = QPushButton("Link Request")
        btn_bar.addWidget(self._summary_label)
        btn_bar.addStretch(1)
        btn_bar.addWidget(self._link_btn)
        layout.addLayout(btn_bar)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch(1)
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, 1)

        self._link_btn.clicked.connect(self._link_existing)

        self.reload()

    def reload(self) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            links = repo.list_linked_agency_requests(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Agency Requests", f"Failed to load links:\n{exc}")
            return
        agencies = self._fetch_agencies()
        self._render_cards(links, agencies)

    def _render_cards(self, links: list[dict], agencies: dict) -> None:
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._summary_label.setText(f"{len(links)} linked agency request{'s' if len(links) != 1 else ''}")
        if not links:
            empty = QLabel("No agency requests linked to this strategy.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{get_palette().get('fg_muted').name()}; padding:24px;")
            self._card_layout.insertWidget(0, empty)
            return
        for link in links:
            agency_id = link.get("agency_id")
            agency_name = agencies.get(agency_id, "")
            if not agency_name and agency_id is not None:
                agency_name = agencies.get(str(agency_id), "")
            self._card_layout.insertWidget(
                self._card_layout.count() - 1,
                self._build_card(link, agency_name),
            )

    def _build_card(self, link: dict, agency_name: str) -> QFrame:
        card = QFrame(self._card_container)
        card.setFrameShape(QFrame.StyledPanel)
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(
            "QFrame { "
            f"background:{get_palette().get('bg_raised').name()}; "
            f"border:1px solid {get_palette().get('ctrl_border').name()}; "
            "border-radius:6px; "
            "}"
        )
        link_id = link.get("link_id") or link.get("id")
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, lid=link_id, c=card: self._show_card_menu(lid, c, pos))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        header = QHBoxLayout()
        summary = (
            link.get("request_summary")
            or link.get("summary")
            or link.get("description")
            or "Agency request"
        )
        title = QLabel(f"{agency_name} - {summary}" if agency_name else summary)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:700;")
        header.addWidget(title, 1)
        status = str(link.get("status") or "")
        if status:
            badge = QLabel(status)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"background:{get_palette().get('warning').name()}; "
                f"color:{get_palette().get('fg').name()}; "
                "padding:2px 8px; border-radius:4px; font-weight:700;"
            )
            header.addWidget(badge)
        layout.addLayout(header)
        detail_bits = []
        if link.get("created_at"):
            detail_bits.append(f"Linked {link.get('created_at')}")
        request_number = (
            link.get("resource_request_id")
            or link.get("request_id")
            or link.get("agency_request_id")
        )
        if request_number:
            detail_bits.append(f"Request {request_number}")
        if link.get("eta"):
            detail_bits.append(f"ETA {link.get('eta')}")
        detail = QLabel(" | ".join(str(part) for part in detail_bits))
        detail.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        layout.addWidget(detail)
        return card

    def _show_card_menu(self, link_id: int | None, card: QFrame, pos) -> None:
        if link_id is None:
            return
        menu = QMenu(self)
        menu.addAction("Unlink Request", lambda: self._unlink(link_id))
        menu.exec(card.mapToGlobal(pos))

    def _fetch_agencies(self) -> dict:
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id
            iid = get_active_incident_id()
            if not iid:
                return {}
            rows = api_client.get(f"/api/incidents/{iid}/liaison/agencies") or []
            agencies = {}
            for row in rows:
                agency_id = row.get("int_id") or row.get("id")
                agency_name = row.get("agency_name") or row.get("name") or ""
                agencies[agency_id] = agency_name
                if agency_id is not None:
                    agencies[str(agency_id)] = agency_name
            return agencies
        except Exception:
            return {}

    def _link_existing(self) -> None:
        dialog = _LinkAgencyRequestDialog(self._work_assignment_id, self._db_path, parent=self)
        dialog.exec()
        self.reload()

    def _unlink(self, link_id: int | None) -> None:
        if link_id is None:
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
        apply_statusboard_table_behavior(self._req_table, stretch_last_section=True)
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
            agencies = {}
            for agency in api_client.get(f"/api/incidents/{iid}/liaison/agencies") or []:
                agency_id = agency.get("int_id") or agency.get("id")
                agency_name = agency.get("agency_name") or agency.get("name") or ""
                agencies[agency_id] = agency_name
                if agency_id is not None:
                    agencies[str(agency_id)] = agency_name
        except Exception:
            return
        for r in requests:
            agency_name = agencies.get(r.get("agency_id"), "")
            description = (
                r.get("description")
                or r.get("summary")
                or r.get("request_summary")
                or r.get("request_type")
                or ""
            )
            if search_text and search_text not in agency_name.lower() and search_text not in description.lower():
                continue
            row_idx = self._req_table.rowCount()
            self._req_table.insertRow(row_idx)
            self._req_table.setItem(row_idx, 0, QTableWidgetItem(agency_name))
            self._req_table.setItem(row_idx, 1, QTableWidgetItem(description))
            self._req_table.setItem(row_idx, 2, QTableWidgetItem(r.get("priority", "")))
            self._req_table.setItem(row_idx, 3, QTableWidgetItem(r.get("status", "")))
            self._req_table.item(row_idx, 0).setData(Qt.UserRole, r.get("int_id") or r.get("id"))

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
