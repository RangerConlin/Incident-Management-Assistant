"""Customer Requests & Feedback — inbound customer-side coordination.

Covers three things a LOFR routes between incident staff and external
customers: new task/objective requests from a customer, resource offers
from a customer/agency, and feedback the customer gives on work already
done. Requests can be converted directly into a real Objective or Task,
with a back-link to the originating Liaison record.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel

from modules.liaison import repository as liaison_repo
from modules.liaison.windows import AgencyRequestDialog, FeedbackBoard, ResourceOfferDialog
from utils.styles import liaison_priority_colors, subscribe_theme

_OBJECTIVE_PRIORITY_MAP = {"Low": "low", "Medium": "normal", "High": "high", "Critical": "urgent"}


class CustomerRequestsBoard(QWidget):
    """Incoming customer/agency requests, convertible into real Objectives/Tasks."""

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.model = QStandardItemModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search customer requests...")
        self.search.textChanged.connect(self._apply_search)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Add Customer Request", self)
        add_btn.clicked.connect(self._add_request)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(refresh_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.headers = ["Description", "Requested By", "Priority", "Status", "Needed By", "Converted To"]
        self.model.setHorizontalHeaderLabels(self.headers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self._rows_cache: list[dict[str, Any]] = []
        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass
        self.reload()

    def _on_theme_changed(self, _name: str) -> None:
        self._render_rows(self._rows_cache)

    def reload(self) -> None:
        try:
            self._rows_cache = liaison_repo.fetch_agency_requests(incident_id=self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Customer Requests", f"Failed to load requests:\n{exc}")
            self._rows_cache = []
        self._render_rows(self._rows_cache)

    def _render_rows(self, rows: list[dict[str, Any]]) -> None:
        self.model.removeRows(0, self.model.rowCount())
        colors = liaison_priority_colors()
        for row in rows:
            converted_type = row.get("converted_to_type")
            converted_id = row.get("converted_to_id")
            converted_text = f"{converted_type.title()} #{converted_id}" if converted_type else ""
            values = [
                row.get("description", ""),
                row.get("requested_by", ""),
                row.get("priority", ""),
                row.get("status", ""),
                row.get("due_date", ""),
                converted_text,
            ]
            items = [QStandardItem(str(v or "")) for v in values]
            items[0].setData(int(row["int_id"]), Qt.UserRole)
            brushes = colors.get(str(row.get("priority") or ""))
            if brushes:
                for item in items:
                    item.setBackground(brushes["bg"])
                    item.setForeground(brushes["fg"])
            self.model.appendRow(items)
        self.table.resizeColumnsToContents()

    def _apply_search(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.model.rowCount()):
            visible = not needle or any(
                needle in str(self.model.item(row, col).text()).lower()
                for col in range(self.model.columnCount())
            )
            self.table.setRowHidden(row, not visible)

    def _selected_row(self) -> dict[str, Any] | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.model.item(indexes[0].row(), 0)
        request_id = item.data(Qt.UserRole) if item else None
        if request_id is None:
            return None
        return next((r for r in self._rows_cache if r.get("int_id") == request_id), None)

    def _add_request(self) -> None:
        dialog = AgencyRequestDialog(None, self)
        if dialog.exec() == QDialog.Accepted:
            liaison_repo.create_agency_request(dialog.values(), self.incident_id)
            self.reload()

    def _convert_to_objective(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        if row.get("converted_to_type"):
            QMessageBox.information(self, "Already Converted", "This request has already been converted.")
            return
        priority = _OBJECTIVE_PRIORITY_MAP.get(str(row.get("priority") or "Medium"), "normal")
        try:
            liaison_repo.convert_agency_request_to_objective(
                row.get("description", ""),
                row["int_id"],
                priority=priority,
                incident_id=self.incident_id,
            )
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Convert to Objective", f"Failed to convert:\n{exc}")

    def _convert_to_task(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        if row.get("converted_to_type"):
            QMessageBox.information(self, "Already Converted", "This request has already been converted.")
            return
        priority = str(row.get("priority") or "Medium")
        try:
            liaison_repo.convert_agency_request_to_task(
                row.get("description", ""),
                row["int_id"],
                priority=priority,
                incident_id=self.incident_id,
            )
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Convert to Task", f"Failed to convert:\n{exc}")

    def _show_context_menu(self, position) -> None:
        if self.table.indexAt(position).row() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Convert to Objective", self._convert_to_objective)
        menu.addAction("Convert to Task", self._convert_to_task)
        menu.exec(self.table.viewport().mapToGlobal(position))


class ResourceOffersBoard(QWidget):
    """Resource offers made by agencies/customers."""

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.model = QStandardItemModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Add Resource Offer", self)
        add_btn.clicked.connect(self._add_offer)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(add_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(refresh_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)
        self.reload()

    def reload(self) -> None:
        try:
            offers = liaison_repo.fetch_resource_offers(incident_id=self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Resource Offers", f"Failed to load offers:\n{exc}")
            return
        columns = ["description", "quantity", "status", "available_from", "offered_by"]
        self.model.removeRows(0, self.model.rowCount())
        self.model.setHorizontalHeaderLabels(columns)
        for row in offers:
            self.model.appendRow([QStandardItem(str(row.get(col) or "")) for col in columns])
        self.table.resizeColumnsToContents()

    def _add_offer(self) -> None:
        dialog = ResourceOfferDialog(None, self)
        if dialog.exec() == QDialog.Accepted:
            liaison_repo.create_resource_offer(dialog.values(), self.incident_id)
            self.reload()


class CustomerBoard(QWidget):
    """Customer Requests, Resource Offers, and Feedback in one board."""

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(CustomerRequestsBoard(incident_id, self), "Customer Requests")
        self.tabs.addTab(ResourceOffersBoard(incident_id, self), "Resource Offers")
        self.tabs.addTab(FeedbackBoard(incident_id, self), "Customer Feedback")
        layout.addWidget(self.tabs)


def get_customer_panel(incident_id: object | None = None) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Customer Requests & Feedback")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(CustomerBoard(incident_id, panel))
    return panel
