from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QSortFilterProxyModel
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
    OFFER_STATUSES,
    PRIORITIES,
    REQUEST_STATUSES,
    VALIDATION_STATUSES,
)
from .repository import (
    create_agency,
    create_agency_request,
    create_feedback,
    create_interaction,
    create_resource_offer,
    fetch_agency_detail,
    fetch_agency_rows,
    fetch_feedback_rows,
    update_agency_status,
)
from utils.itemview_delegates import RowOutlineSelectionDelegate
from utils.styles import get_palette, liaison_agency_status_colors, liaison_priority_colors, subscribe_theme

__all__ = [
    "get_agencies_panel",
    "AgencyStatusBoard",
    "FeedbackBoard",
    "AgencyDetailDialog",
    "AgencyRequestDialog",
    "ResourceOfferDialog",
    "FeedbackDialog",
]


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
        try:
            pal = get_palette()
            color = pal.get("ctrl_focus", pal.get("accent"))
            self._outline_delegate = RowOutlineSelectionDelegate(self.table, color)
            self.table.setItemDelegate(self._outline_delegate)
        except Exception:
            self._outline_delegate = None

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

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, _name: str) -> None:
        self.reload()

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
        "Code",
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
        self.proxy.status_column = 4
        self.proxy.priority_column = 11
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
            row.get("code", ""),
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
        status_colors = liaison_agency_status_colors()
        priority_colors = liaison_priority_colors()
        # Color only the cells the badge represents (Current Status, Priority)
        # so the tint carries meaning instead of washing out the whole row.
        status_brushes = status_colors.get(status)
        if status_brushes:
            items[4].setBackground(status_brushes["bg"])
            items[4].setForeground(status_brushes["fg"])
        priority_brushes = priority_colors.get(priority)
        if priority_brushes:
            items[11].setBackground(priority_brushes["bg"])
            items[11].setForeground(priority_brushes["fg"])
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

    def _add_request(self) -> None:
        agency_id = self._selected_id()
        if agency_id is None:
            return
        dialog = AgencyRequestDialog(agency_id, self)
        if dialog.exec() == QDialog.Accepted:
            create_agency_request(dialog.values(), self.incident_id)
            self.reload()

    def _add_offer(self) -> None:
        agency_id = self._selected_id()
        if agency_id is None:
            return
        dialog = ResourceOfferDialog(agency_id, self)
        if dialog.exec() == QDialog.Accepted:
            create_resource_offer(dialog.values(), self.incident_id)
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
        request_menu = menu.addMenu("Add Request / Offer")
        request_menu.addAction("External Request", self._add_request)
        request_menu.addAction("Resource Offer", self._add_offer)
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
        items[0].setData(
            {
                "objective_id": row.get("objective_id"),
                "task_id": row.get("task_id"),
                "resource_request_id": row.get("resource_request_id"),
            },
            Qt.UserRole + 1,
        )
        priority = str(row.get("priority") or "")
        priority_brushes = liaison_priority_colors().get(priority)
        if priority_brushes:
            for item in items:
                item.setBackground(priority_brushes["bg"])
                item.setForeground(priority_brushes["fg"])
        self.model.appendRow(items)

    def _add_feedback(self) -> None:
        dialog = FeedbackDialog(None, self)
        if dialog.exec() == QDialog.Accepted:
            create_feedback(dialog.values(), self.incident_id)
            self.reload()

    def _selected_linked_ids(self) -> dict[str, Any] | None:
        row = self._selected_source_row()
        if row < 0:
            return None
        item = self.model.item(row, 0)
        return item.data(Qt.UserRole + 1) if item else None

    def _open_linked_item(self) -> None:
        linked = self._selected_linked_ids()
        if not linked:
            return
        if linked.get("task_id"):
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(int(linked["task_id"]))
            return
        if linked.get("objective_id"):
            from modules.command.widgets.objective_detail_dialog import ObjectiveDetailDialog
            dialog = ObjectiveDetailDialog(self)
            dialog.load_objective(str(linked["objective_id"]))
            dialog.show()
            return
        if linked.get("resource_request_id"):
            from modules.logistics.resource_requests import get_service
            from modules.logistics.resource_requests.panels.request_detail_panel import (
                ResourceRequestDetailPanel,
            )
            dialog = QDialog(self)
            dialog.setWindowTitle("Resource Request Detail")
            layout = QVBoxLayout(dialog)
            service = get_service(str(self.incident_id) if self.incident_id is not None else None)
            panel = ResourceRequestDetailPanel(service=service, parent=dialog)
            panel.load_request(str(linked["resource_request_id"]))
            layout.addWidget(panel)
            dialog.resize(700, 500)
            dialog.exec()
            return
        QMessageBox.information(self, "Linked Item", "This feedback item has no linked Objective, Task, or Resource Request.")

    def show_context_menu(self, position) -> None:
        if self.table.indexAt(position).row() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Add Feedback", self._add_feedback)
        menu.addAction("View Linked Item", self._open_linked_item)
        menu.exec(self.table.viewport().mapToGlobal(position))


class AgencyDetailDialog(QDialog):
    def __init__(self, agency_id: int, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.incident_id = incident_id
        self.setWindowTitle("Liaison Agency Details")
        self.tabs = QTabWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        self._load()
        self.adjustSize()

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
        self.code = QLineEdit(self)
        self.code.setPlaceholderText("e.g. AFRCC, OEM")
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
            ("Agency Code", self.code),
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
        if not self.code.text().strip():
            QMessageBox.warning(
                self, "Agency Code Required",
                "Agency Code is required — it's used to number Agency Requests (e.g. AFRCC-1, AFRCC-2)."
            )
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name.text().strip(),
            "code": self.code.text().strip().upper(),
            "agency_type": self.agency_type.text().strip(),
            "jurisdiction": self.jurisdiction.text().strip(),
            "current_status": self.status.currentText(),
            "assigned_liaison": self.liaison.text().strip(),
            "next_contact_due": self.next_due.text().strip(),
            "priority": self.priority.currentText(),
            "notes": self.notes.toPlainText().strip(),
        }


class InteractionDialog(QDialog):
    """Add a Liaison interaction.

    When ``agency_id`` is ``None`` an agency picker is shown so the dialog can
    be launched from anywhere (e.g. the overview's "Log Interaction" button)
    without requiring the caller to pre-select a row in the Agency Directory.
    """

    def __init__(
        self,
        agency_id: int | None,
        parent: QWidget | None = None,
        agencies: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.setWindowTitle("Add Liaison Interaction")
        layout = QFormLayout(self)

        self.agency_picker: QComboBox | None = None
        if agency_id is None:
            self.agency_picker = QComboBox(self)
            for agency in agencies or []:
                self.agency_picker.addItem(str(agency.get("agency_name") or "Unnamed Agency"), agency.get("id"))
            layout.addRow("Agency:", self.agency_picker)

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

    def accept(self) -> None:  # type: ignore[override]
        if self.agency_picker is not None and self.agency_picker.currentData() is None:
            QMessageBox.warning(self, "Agency Required", "Select an agency for this interaction.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        agency_id = self.agency_id
        if self.agency_picker is not None:
            agency_id = self.agency_picker.currentData()
        return {
            "agency_id": agency_id,
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


class AgencyRequestDialog(QDialog):
    def __init__(self, agency_id: int | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.setWindowTitle("Add External Agency Request")
        layout = QFormLayout(self)
        self.description = QLineEdit(self)
        self.requested_by = QLineEdit(self)
        self.priority = QComboBox(self)
        self.priority.addItems(PRIORITIES)
        self.status = QComboBox(self)
        self.status.addItems(REQUEST_STATUSES)
        self.due_date = QLineEdit(self)
        self.notes = QTextEdit(self)
        for label, widget in [
            ("Description", self.description),
            ("Requested By", self.requested_by),
            ("Priority", self.priority),
            ("Status", self.status),
            ("Needed By", self.due_date),
            ("Notes", self.notes),
        ]:
            layout.addRow(label + ":", widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self) -> None:  # type: ignore[override]
        if not self.description.text().strip():
            QMessageBox.warning(self, "Description Required", "Description is required.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "agency_id": self.agency_id,
            "description": self.description.text().strip(),
            "requested_by": self.requested_by.text().strip(),
            "priority": self.priority.currentText(),
            "status": self.status.currentText(),
            "due_date": self.due_date.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class ResourceOfferDialog(QDialog):
    def __init__(self, agency_id: int | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agency_id = agency_id
        self.setWindowTitle("Add Resource Offer")
        layout = QFormLayout(self)
        self.description = QLineEdit(self)
        self.offered_by = QLineEdit(self)
        self.quantity = QLineEdit(self)
        self.status = QComboBox(self)
        self.status.addItems(OFFER_STATUSES)
        self.available_from = QLineEdit(self)
        self.notes = QTextEdit(self)
        for label, widget in [
            ("Description", self.description),
            ("Offered By", self.offered_by),
            ("Quantity", self.quantity),
            ("Status", self.status),
            ("Available From", self.available_from),
            ("Notes", self.notes),
        ]:
            layout.addRow(label + ":", widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def accept(self) -> None:  # type: ignore[override]
        if not self.description.text().strip():
            QMessageBox.warning(self, "Description Required", "Description is required.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "agency_id": self.agency_id,
            "description": self.description.text().strip(),
            "offered_by": self.offered_by.text().strip(),
            "quantity": self.quantity.text().strip(),
            "status": self.status.currentText(),
            "available_from": self.available_from.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


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
