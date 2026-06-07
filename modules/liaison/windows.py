from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel

from .models import (
    AGENCY_STATUSES,
    FEEDBACK_STATUSES,
    FEEDBACK_TYPES,
    INTERACTION_TYPES,
    PRIORITIES,
    VALIDATION_STATUSES,
)
from .repository import (
    create_agency,
    create_feedback,
    create_interaction,
    fetch_agency_detail,
    fetch_agency_rows,
    fetch_feedback_rows,
    update_agency_status,
)

__all__ = [
    "get_agencies_panel",
    "get_requests_panel",
    "AgencyStatusBoard",
    "FeedbackBoard",
    "AgencyDetailDialog",
]


STATUS_COLORS = {
    "Not Contacted": ("#3a3a3a", "#f4f4f4"),
    "Contacted": ("#244a73", "#ffffff"),
    "Awaiting Response": ("#735c24", "#ffffff"),
    "Standby": ("#435466", "#ffffff"),
    "Supporting": ("#266b4b", "#ffffff"),
    "Active": ("#1f7a3f", "#ffffff"),
    "Demobilizing": ("#6f4d90", "#ffffff"),
    "Released": ("#555555", "#ffffff"),
    "Unavailable": ("#7a2d2d", "#ffffff"),
}

PRIORITY_COLORS = {
    "Critical": ("#8a1f1f", "#ffffff"),
    "High": ("#9b5d00", "#ffffff"),
    "Medium": ("#314f78", "#ffffff"),
    "Low": ("#3f5f3f", "#ffffff"),
}


class MultiColumnFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.search_text = ""
        self.status_text = "All"
        self.priority_text = "All"
        self.status_column = -1
        self.priority_column = -1

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if model is None:
            return True
        if self.status_text != "All" and self.status_column >= 0:
            idx = model.index(source_row, self.status_column, source_parent)
            if model.data(idx) != self.status_text:
                return False
        if self.priority_text != "All" and self.priority_column >= 0:
            idx = model.index(source_row, self.priority_column, source_parent)
            if model.data(idx) != self.priority_text:
                return False
        if not self.search_text:
            return True
        needle = self.search_text.lower()
        for col in range(model.columnCount()):
            idx = model.index(source_row, col, source_parent)
            if needle in str(model.data(idx) or "").lower():
                return True
        return False


class _BaseBoard(QWidget):
    headers: list[str] = []

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.model = QStandardItemModel(self)
        self.proxy = MultiColumnFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(lambda index: self._open_current_detail())

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search Liaison records...")
        self.search.textChanged.connect(self._set_search)
        self.status_filter = QComboBox(self)
        self.priority_filter = QComboBox(self)
        self.priority_filter.addItems(["All", *PRIORITIES])
        self.priority_filter.currentTextChanged.connect(self._set_priority)
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.reload)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search:"))
        filters.addWidget(self.search, 1)
        filters.addWidget(QLabel("Status:"))
        filters.addWidget(self.status_filter)
        filters.addWidget(QLabel("Priority:"))
        filters.addWidget(self.priority_filter)
        filters.addWidget(self.refresh_button)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.table)

        self.model.setHorizontalHeaderLabels(self.headers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

    def _set_search(self, value: str) -> None:
        self.proxy.search_text = value.strip()
        self.proxy.invalidateFilter()

    def _set_status(self, value: str) -> None:
        self.proxy.status_text = value
        self.proxy.invalidateFilter()

    def _set_priority(self, value: str) -> None:
        self.proxy.priority_text = value
        self.proxy.invalidateFilter()

    def _selected_source_row(self) -> int:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return -1
        return self.proxy.mapToSource(indexes[0]).row()

    def _selected_id(self) -> int | None:
        row = self._selected_source_row()
        if row < 0:
            return None
        item = self.model.item(row, 0)
        value = item.data(Qt.UserRole) if item else None
        return int(value) if value is not None else None

    def _open_current_detail(self) -> None:
        pass

    def show_context_menu(self, position) -> None:
        pass

    def reload(self) -> None:
        pass


class AgencyStatusBoard(_BaseBoard):
    headers = [
        "Agency Name",
        "Agency Type",
        "Jurisdiction",
        "Current Status",
        "Assigned Liaison",
        "Last Contact",
        "Next Contact Due",
        "Open Requests",
        "Resource Offers",
        "Open Feedback Items",
        "Priority",
    ]

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(incident_id, parent)
        self.proxy.status_column = 3
        self.proxy.priority_column = 10
        self.status_filter.addItems(["All", *AGENCY_STATUSES])
        self.status_filter.currentTextChanged.connect(self._set_status)
        self.reload()

    def reload(self) -> None:
        try:
            self.model.removeRows(0, self.model.rowCount())
            for row in fetch_agency_rows(self.incident_id):
                self._append_agency(row)
            self.table.resizeColumnsToContents()
        except Exception as exc:
            QMessageBox.critical(self, "Liaison Agency Board", f"Failed to load Liaison agencies:\n{exc}")

    def _append_agency(self, row: dict[str, Any]) -> None:
        values = [
            row.get("agency_name", ""),
            row.get("agency_type", ""),
            row.get("jurisdiction", ""),
            row.get("current_status", ""),
            row.get("assigned_liaison", ""),
            row.get("last_contact", ""),
            row.get("next_contact_due", ""),
            row.get("open_requests", 0),
            row.get("resource_offers", 0),
            row.get("open_feedback_items", 0),
            row.get("priority", ""),
        ]
        items = [QStandardItem(str(value or "")) for value in values]
        items[0].setData(int(row["id"]), Qt.UserRole)
        status = str(row.get("current_status") or "")
        priority = str(row.get("priority") or "")
        for item in items:
            if status in STATUS_COLORS:
                bg, fg = STATUS_COLORS[status]
                item.setBackground(QColor(bg))
                item.setForeground(QColor(fg))
        if priority in PRIORITY_COLORS:
            bg, fg = PRIORITY_COLORS[priority]
            items[10].setBackground(QColor(bg))
            items[10].setForeground(QColor(fg))
        self.model.appendRow(items)

    def _open_current_detail(self) -> None:
        agency_id = self._selected_id()
        if agency_id is None:
            return
        dialog = AgencyDetailDialog(agency_id, self.incident_id, self)
        dialog.exec()
        self.reload()

    def _add_agency(self) -> None:
        dialog = AgencyEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            create_agency(dialog.values(), self.incident_id)
            self.reload()

    def _add_interaction(self) -> None:
        agency_id = self._selected_id()
        if agency_id is None:
            return
        dialog = InteractionDialog(agency_id, self)
        if dialog.exec() == QDialog.Accepted:
            create_interaction(dialog.values(), self.incident_id)
            self.reload()

    def _add_feedback(self) -> None:
        agency_id = self._selected_id()
        if agency_id is None:
            return
        dialog = FeedbackDialog(agency_id, self)
        if dialog.exec() == QDialog.Accepted:
            create_feedback(dialog.values(), self.incident_id)
            self.reload()

    def _change_status(self, status: str) -> None:
        agency_id = self._selected_id()
        if agency_id is None:
            return
        update_agency_status(agency_id, status, self.incident_id)
        self.reload()

    def show_context_menu(self, position) -> None:
        if self.table.indexAt(position).row() < 0:
            return
        menu = QMenu(self)
        menu.addAction("View Agency Details", self._open_current_detail)
        menu.addAction("Add Interaction", self._add_interaction)
        menu.addAction("Add Request / Offer", lambda: QMessageBox.information(self, "External Coordination", "TODO: wire agency request/resource offer editor to Resource Requests."))
        menu.addAction("Add Feedback", self._add_feedback)
        status_menu = menu.addMenu("Change Status")
        for status in AGENCY_STATUSES:
            status_menu.addAction(status, lambda checked=False, s=status: self._change_status(s))
        menu.addAction("Open Contact Info", self._open_current_detail)
        menu.exec(self.table.viewport().mapToGlobal(position))


class FeedbackBoard(_BaseBoard):
    headers = [
        "Date/Time",
        "Source",
        "Feedback Type",
        "Priority",
        "Linked Item",
        "Status",
        "Assigned To",
        "Due/Follow-up",
        "Resolution Status",
    ]

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(incident_id, parent)
        self.proxy.status_column = 5
        self.proxy.priority_column = 3
        self.status_filter.addItems(["All", *FEEDBACK_STATUSES])
        self.status_filter.currentTextChanged.connect(self._set_status)
        self.reload()

    def reload(self) -> None:
        try:
            self.model.removeRows(0, self.model.rowCount())
            for row in fetch_feedback_rows(self.incident_id):
                self._append_feedback(row)
            self.table.resizeColumnsToContents()
        except Exception as exc:
            QMessageBox.critical(self, "Liaison Feedback Board", f"Failed to load stakeholder feedback:\n{exc}")

    def _append_feedback(self, row: dict[str, Any]) -> None:
        values = [
            row.get("date_time", ""),
            row.get("source", ""),
            row.get("feedback_type", ""),
            row.get("priority", ""),
            row.get("linked_item", ""),
            row.get("status", ""),
            row.get("assigned_to", ""),
            row.get("due_followup", ""),
            row.get("resolution_status", ""),
        ]
        items = [QStandardItem(str(value or "")) for value in values]
        items[0].setData(int(row["id"]), Qt.UserRole)
        priority = str(row.get("priority") or "")
        if priority in PRIORITY_COLORS:
            bg, fg = PRIORITY_COLORS[priority]
            for item in items:
                item.setBackground(QColor(bg))
                item.setForeground(QColor(fg))
        self.model.appendRow(items)

    def _add_feedback(self) -> None:
        dialog = FeedbackDialog(None, self)
        if dialog.exec() == QDialog.Accepted:
            create_feedback(dialog.values(), self.incident_id)
            self.reload()

    def show_context_menu(self, position) -> None:
        menu = QMenu(self)
        menu.addAction("Add Feedback", self._add_feedback)
        menu.addAction("View Linked Item", lambda: QMessageBox.information(self, "Linked Item", "TODO: open Planning/Operations/Command linked item detail when module hooks are available."))
        menu.exec(self.table.viewport().mapToGlobal(position))


class AgencyDetailDialog(QDialog):
    def __init__(self, agency_id: int, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.incident_id = incident_id
        self.setWindowTitle("Liaison Agency Details")
        self.resize(980, 680)
        self.tabs = QTabWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        self._load()

    def _load(self) -> None:
        detail = fetch_agency_detail(self.agency_id, self.incident_id)
        agency = detail["agency"]
        overview = QWidget(self)
        form = QFormLayout(overview)
        for label, key in [
            ("Agency Name", "name"),
            ("Agency Type", "agency_type"),
            ("Jurisdiction", "jurisdiction"),
            ("Current Status", "current_status"),
            ("Assigned Liaison", "assigned_liaison"),
            ("Last Contact", "last_contact"),
            ("Next Contact Due", "next_contact_due"),
            ("Priority", "priority"),
            ("Notes", "notes"),
        ]:
            form.addRow(label + ":", QLabel(str(agency.get(key) or "")))
        self.tabs.addTab(overview, "Overview")
        self.tabs.addTab(self._table_tab(detail["contacts"]), "Contacts")
        self.tabs.addTab(self._table_tab(detail["interactions"]), "Interaction Log")
        self.tabs.addTab(self._requests_offers_tab(detail), "Requests / Offers")
        self.tabs.addTab(self._table_tab(detail["feedback"]), "Stakeholder Feedback")
        self.tabs.addTab(self._restrictions_agreements_tab(detail), "Restrictions / Agreements")
        self.tabs.addTab(self._table_tab(detail["attachments"]), "Attachments")
        self.tabs.addTab(self._table_tab(detail["audit"]), "Audit Log")

    def _table_tab(self, rows: list[dict[str, Any]]) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        table = QTableView(widget)
        model = QStandardItemModel(table)
        if rows:
            headers = list(rows[0].keys())
            model.setHorizontalHeaderLabels(headers)
            for row in rows:
                model.appendRow([QStandardItem(str(row.get(header) or "")) for header in headers])
        table.setModel(model)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSortingEnabled(True)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        return widget

    def _requests_offers_tab(self, detail: dict[str, Any]) -> QWidget:
        tabs = QTabWidget(self)
        tabs.addTab(self._table_tab(detail["requests"]), "External Requests")
        tabs.addTab(self._table_tab(detail["offers"]), "Resource Offers")
        return tabs

    def _restrictions_agreements_tab(self, detail: dict[str, Any]) -> QWidget:
        tabs = QTabWidget(self)
        tabs.addTab(self._table_tab(detail["restrictions"]), "Restrictions")
        tabs.addTab(self._table_tab(detail["agreements"]), "Agreements")
        return tabs


class AgencyEditDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Liaison Agency")
        layout = QFormLayout(self)
        self.name = QLineEdit(self)
        self.agency_type = QLineEdit(self)
        self.jurisdiction = QLineEdit(self)
        self.status = QComboBox(self)
        self.status.addItems(AGENCY_STATUSES)
        self.liaison = QLineEdit(self)
        self.next_due = QLineEdit(self)
        self.priority = QComboBox(self)
        self.priority.addItems(PRIORITIES)
        self.notes = QTextEdit(self)
        for label, widget in [
            ("Agency Name", self.name),
            ("Agency Type", self.agency_type),
            ("Jurisdiction", self.jurisdiction),
            ("Current Status", self.status),
            ("Assigned Liaison", self.liaison),
            ("Next Contact Due", self.next_due),
            ("Priority", self.priority),
            ("Notes", self.notes),
        ]:
            layout.addRow(label + ":", widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self) -> None:  # type: ignore[override]
        if not self.name.text().strip():
            QMessageBox.warning(self, "Agency Required", "Agency Name is required.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name.text().strip(),
            "agency_type": self.agency_type.text().strip(),
            "jurisdiction": self.jurisdiction.text().strip(),
            "current_status": self.status.currentText(),
            "assigned_liaison": self.liaison.text().strip(),
            "next_contact_due": self.next_due.text().strip(),
            "priority": self.priority.currentText(),
            "notes": self.notes.toPlainText().strip(),
        }


class InteractionDialog(QDialog):
    def __init__(self, agency_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.setWindowTitle("Add Liaison Interaction")
        layout = QFormLayout(self)
        self.interaction_type = QComboBox(self)
        self.interaction_type.addItems(INTERACTION_TYPES)
        self.occurred_at = QLineEdit(self)
        self.subject = QLineEdit(self)
        self.summary = QTextEdit(self)
        self.followup = QLineEdit(self)
        self.followup_assigned = QLineEdit(self)
        self.followup_due = QLineEdit(self)
        for label, widget in [
            ("Interaction Type", self.interaction_type),
            ("Occurred At", self.occurred_at),
            ("Subject", self.subject),
            ("Summary", self.summary),
            ("Follow-up Action", self.followup),
            ("Assigned User", self.followup_assigned),
            ("Due Date", self.followup_due),
        ]:
            layout.addRow(label + ":", widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "agency_id": self.agency_id,
            "interaction_type": self.interaction_type.currentText(),
            "occurred_at": self.occurred_at.text().strip(),
            "subject": self.subject.text().strip(),
            "summary": self.summary.toPlainText().strip(),
            "followup_action": self.followup.text().strip(),
            "followup_assigned_to": self.followup_assigned.text().strip(),
            "followup_due": self.followup_due.text().strip(),
        }


class FeedbackDialog(QDialog):
    def __init__(self, agency_id: int | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.setWindowTitle("Add Stakeholder Feedback")
        layout = QFormLayout(self)
        self.feedback_type = QComboBox(self)
        self.feedback_type.addItems(FEEDBACK_TYPES)
        self.priority = QComboBox(self)
        self.priority.addItems(PRIORITIES)
        self.summary = QLineEdit(self)
        self.requested_action = QTextEdit(self)
        self.assigned_section = QLineEdit(self)
        self.assigned_to = QLineEdit(self)
        self.status = QComboBox(self)
        self.status.addItems(FEEDBACK_STATUSES)
        self.validation = QComboBox(self)
        self.validation.addItems(VALIDATION_STATUSES)
        self.followup_due = QLineEdit(self)
        self.linked_task = QLineEdit(self)
        self.linked_objective = QLineEdit(self)
        self.linked_resource = QLineEdit(self)
        for label, widget in [
            ("Feedback Type", self.feedback_type),
            ("Priority", self.priority),
            ("Summary", self.summary),
            ("Recommendation / Requested Action", self.requested_action),
            ("Assigned Section", self.assigned_section),
            ("Assigned User", self.assigned_to),
            ("Status", self.status),
            ("Validation Status", self.validation),
            ("Due / Follow-up", self.followup_due),
            ("Linked Objective ID", self.linked_objective),
            ("Linked Task ID", self.linked_task),
            ("Linked Resource Request ID", self.linked_resource),
        ]:
            layout.addRow(label + ":", widget)
        # TODO: replace raw linked IDs with selectors from Planning, Operations, and Resource Requests.
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self) -> None:  # type: ignore[override]
        if not self.summary.text().strip():
            QMessageBox.warning(self, "Feedback Required", "Summary is required.")
            return
        super().accept()

    @staticmethod
    def _int_or_none(value: str) -> int | None:
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def values(self) -> dict[str, Any]:
        return {
            "agency_id": self.agency_id,
            "feedback_type": self.feedback_type.currentText(),
            "priority": self.priority.currentText(),
            "summary": self.summary.text().strip(),
            "requested_action": self.requested_action.toPlainText().strip(),
            "assigned_section": self.assigned_section.text().strip(),
            "assigned_to": self.assigned_to.text().strip(),
            "status": self.status.currentText(),
            "validation_status": self.validation.currentText(),
            "followup_due": self.followup_due.text().strip(),
            "objective_id": self._int_or_none(self.linked_objective.text()),
            "task_id": self._int_or_none(self.linked_task.text()),
            "resource_request_id": self._int_or_none(self.linked_resource.text()),
        }


class ExternalCoordinationPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "External Coordination consolidates external requests, resource offers, "
            "stakeholder feedback, priority issues, and follow-up actions."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(FeedbackBoard(incident_id, self), "Stakeholder Feedback")
        self.tabs.addTab(QLabel("TODO: agency request and resource offer work queues will link to Logistics Resource Requests."), "Requests / Offers")
        self.tabs.addTab(QLabel("TODO: priority issues and follow-up actions will surface Command-critical Liaison items."), "Priority Issues / Follow-ups")
        layout.addWidget(self.tabs)


def get_agencies_panel(incident_id: object | None = None) -> QWidget:
    """Return the Liaison Agency Status Board for the active incident."""
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Liaison Agency Status Board")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    board = AgencyStatusBoard(incident_id, panel)
    layout.addWidget(board)
    add_button = QPushButton("Add Agency", panel)
    add_button.clicked.connect(board._add_agency)
    layout.addWidget(add_button, alignment=Qt.AlignLeft)
    return panel


def get_requests_panel(incident_id: object | None = None) -> QWidget:
    """Return External Coordination, replacing the simple request tracker."""
    return ExternalCoordinationPanel(incident_id)
