"""Detail panel for an individual resource request."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .. import get_service
from ..api import printers
from ..api.service import ResourceRequestService
from ..api.validators import ValidationError
from ..models.enums import ApprovalAction, Priority, RequestStatus
from .dialogs import AssignDialog, EtaDialog, NoteDialog
from .widgets.approvals_timeline import ApprovalsTimeline
from .widgets.audit_view import AuditView
from .widgets.fulfillment_view import FulfillmentView
from .widgets.items_table import ItemsTable


class ResourceRequestDetailPanel(QtWidgets.QWidget):
    """Presents and edits a single resource request."""

    requestSaved = QtCore.Signal(str)

    def __init__(self, service: ResourceRequestService | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service or get_service()
        self.current_request_id: Optional[str] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_layout = QtWidgets.QHBoxLayout()
        self.title_edit = QtWidgets.QLineEdit(self)
        self.title_edit.setPlaceholderText("Request title")
        header_layout.addWidget(QtWidgets.QLabel("Title:"))
        header_layout.addWidget(self.title_edit, stretch=1)

        self.priority_combo = QtWidgets.QComboBox(self)
        for priority in Priority:
            self.priority_combo.addItem(priority.value.title(), priority.value)
        header_layout.addWidget(QtWidgets.QLabel("Priority:"))
        header_layout.addWidget(self.priority_combo)

        self.status_label = QtWidgets.QLabel("DRAFT")
        header_layout.addWidget(QtWidgets.QLabel("Status:"))
        header_layout.addWidget(self.status_label)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        self.tabs = QtWidgets.QTabWidget(self)
        layout.addWidget(self.tabs, stretch=1)

        # Details tab
        details_widget = QtWidgets.QWidget(self.tabs)
        form = QtWidgets.QFormLayout(details_widget)
        self.section_edit = QtWidgets.QLineEdit(details_widget)
        self.needed_by_edit = QtWidgets.QDateTimeEdit(details_widget)
        self.needed_by_edit.setCalendarPopup(True)
        self.delivery_edit = QtWidgets.QLineEdit(details_widget)
        self.comms_edit = QtWidgets.QLineEdit(details_widget)
        self.links_edit = QtWidgets.QLineEdit(details_widget)
        self.justification_edit = QtWidgets.QPlainTextEdit(details_widget)
        self.justification_edit.setPlaceholderText("Provide justification…")
        form.addRow("Requesting Section", self.section_edit)
        form.addRow("Needed By", self.needed_by_edit)
        form.addRow("Delivery Location", self.delivery_edit)
        form.addRow("Comms Requirements", self.comms_edit)
        form.addRow("Links", self.links_edit)
        form.addRow("Justification", self.justification_edit)
        self.tabs.addTab(details_widget, "Details")

        # Items tab
        self.items_table = ItemsTable(self.tabs)
        self.tabs.addTab(self.items_table, "Items")

        # Approvals tab
        approvals_widget = QtWidgets.QWidget(self.tabs)
        approvals_layout = QtWidgets.QVBoxLayout(approvals_widget)
        self.approvals_view = ApprovalsTimeline(approvals_widget)
        approvals_layout.addWidget(self.approvals_view)
        approval_buttons = QtWidgets.QHBoxLayout()
        self.submit_button = QtWidgets.QPushButton("Submit")
        self.submit_button.clicked.connect(lambda: self._record_action(ApprovalAction.SUBMIT))
        self.review_button = QtWidgets.QPushButton("Review")
        self.review_button.clicked.connect(lambda: self._record_action(ApprovalAction.REVIEW))
        self.approve_button = QtWidgets.QPushButton("Approve")
        self.approve_button.clicked.connect(lambda: self._record_action(ApprovalAction.APPROVE))
        self.deny_button = QtWidgets.QPushButton("Deny")
        self.deny_button.clicked.connect(lambda: self._record_action(ApprovalAction.DENY, require_note=True))
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(lambda: self._record_action(ApprovalAction.CANCEL))
        approval_buttons.addWidget(self.submit_button)
        approval_buttons.addWidget(self.review_button)
        approval_buttons.addWidget(self.approve_button)
        approval_buttons.addWidget(self.deny_button)
        approval_buttons.addWidget(self.cancel_button)
        approval_buttons.addStretch(1)
        approvals_layout.addLayout(approval_buttons)
        self.tabs.addTab(approvals_widget, "Approvals")

        # Fulfillment tab
        fulfillment_widget = QtWidgets.QWidget(self.tabs)
        fulfillment_layout = QtWidgets.QVBoxLayout(fulfillment_widget)
        self.fulfillment_view = FulfillmentView(fulfillment_widget)
        self.fulfillment_view.assignRequested.connect(self._assign_fulfillment)
        self.fulfillment_view.updateRequested.connect(self._update_fulfillment)
        fulfillment_layout.addWidget(self.fulfillment_view)
        self.tabs.addTab(fulfillment_widget, "Fulfillment")

        # Audit tab
        self.audit_view = AuditView(self.tabs)
        self.tabs.addTab(self.audit_view, "Audit")

        # Footer actions
        footer = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        footer.addWidget(self.save_button)

        self.print_ics_button = QtWidgets.QPushButton("Print ICS-213 RR")
        self.print_ics_button.clicked.connect(self._print_ics)
        footer.addWidget(self.print_ics_button)

        self.print_summary_button = QtWidgets.QPushButton("Print Summary")
        self.print_summary_button.clicked.connect(self._print_summary)
        footer.addWidget(self.print_summary_button)

        footer.addStretch(1)
        layout.addLayout(footer)

        QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.CTRL | QtCore.Qt.Key_Return),
            self,
            lambda: self._record_action(ApprovalAction.SUBMIT),
        )


    # ----------------------------------------------------------------- loading
    def start_new(self) -> None:
        self.current_request_id = None
        self.title_edit.clear()
        self.section_edit.clear()
        self.needed_by_edit.setDateTime(QtCore.QDateTime.currentDateTime())
        self.delivery_edit.clear()
        self.comms_edit.clear()
        self.links_edit.clear()
        self.justification_edit.clear()
        self.items_table.set_items([])
        self.approvals_view.clear()
        self.fulfillment_view.set_fulfillment(None)
        self.audit_view.clear()
        self.status_label.setText(RequestStatus.DRAFT.value)
        self.priority_combo.setCurrentIndex(0)

    def load_request(self, request_id: str) -> None:
        if request_id == "NEW":
            self.start_new()
            return

        record = self.service.get_request(request_id)
        self.current_request_id = request_id
        self.title_edit.setText(record.get("title", ""))
        self.section_edit.setText(record.get("requesting_section", ""))
        needed_by = record.get("needed_by_utc")
        if needed_by:
            dt = QtCore.QDateTime.fromString(needed_by, QtCore.Qt.ISODate)
            if not dt.isValid():
                dt = QtCore.QDateTime.fromString(needed_by, QtCore.Qt.ISODateWithMs)
            if dt.isValid():
                self.needed_by_edit.setDateTime(dt)
        self.delivery_edit.setText(record.get("delivery_location", ""))
        self.comms_edit.setText(record.get("comms_requirements", ""))
        self.links_edit.setText(record.get("links", ""))
        self.justification_edit.setPlainText(record.get("justification", ""))
        priority_index = self.priority_combo.findData(record.get("priority"))
        if priority_index >= 0:
            self.priority_combo.setCurrentIndex(priority_index)
        self.status_label.setText(record.get("status", RequestStatus.DRAFT.value))
        self.items_table.set_items(record.get("items", []))
        self.approvals_view.set_approvals(record.get("approvals", []))
        fulfillments = record.get("fulfillments", [])
        self.fulfillment_view.set_fulfillment(fulfillments[-1] if fulfillments else None)
        self.audit_view.set_entries(record.get("audit", []))

    # ------------------------------------------------------------------- actions
    def save(self) -> None:
        header = {
            "title": self.title_edit.text().strip(),
            "requesting_section": self.section_edit.text().strip(),
            "priority": self.priority_combo.currentData(),
            "needed_by_utc": self.needed_by_edit.dateTime().toString(QtCore.Qt.ISODate),
            "delivery_location": self.delivery_edit.text().strip() or None,
            "comms_requirements": self.comms_edit.text().strip() or None,
            "links": self.links_edit.text().strip() or None,
            "justification": self.justification_edit.toPlainText().strip() or None,
            "created_by_id": "ui",
        }

        items = self.items_table.items_data()

        if self.current_request_id:
            try:
                self.service.update_request(self.current_request_id, header)
                self.service.replace_items(self.current_request_id, items)
            except ValidationError as exc:
                QtWidgets.QMessageBox.warning(self, "Validation", str(exc))
                return
            self.requestSaved.emit(self.current_request_id)
        else:
            try:
                request_id = self.service.create_request(header, items)
            except ValidationError as exc:
                QtWidgets.QMessageBox.warning(self, "Validation", str(exc))
                return
            self.current_request_id = request_id
            self.requestSaved.emit(request_id)
        if self.current_request_id:
            self.load_request(self.current_request_id)

    def _record_action(self, action: ApprovalAction, require_note: bool = False) -> None:
        if not self.current_request_id:
            self.save()
        if not self.current_request_id:
            return

        note = None
        if require_note:
            dialog = NoteDialog("Provide Note", "A note is required for this action.", True, self)
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            note = dialog.note
        try:
            self.service.record_approval(self.current_request_id, action.value, actor_id="ui", note=note)
            self.load_request(self.current_request_id)
            self.requestSaved.emit(self.current_request_id)
        except ValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "Validation", str(exc))

    def _assign_fulfillment(self) -> None:
        if not self.current_request_id:
            return
        dialog = AssignDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        values = dialog.values()
        self.service.assign_fulfillment(
            self.current_request_id,
            supplier_id=values["supplier_id"],
            team_id=values["team_id"],
            vehicle_id=values["vehicle_id"],
            eta_utc=values["eta_utc"],
            note=values["note"],
        )
        self.load_request(self.current_request_id)

    def _update_fulfillment(self) -> None:
        if not self.current_request_id:
            return
        record = self.service.get_request(self.current_request_id)
        fulfillments = record.get("fulfillments", [])
        if not fulfillments:
            return
        latest = fulfillments[-1]
        dialog = EtaDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        values = dialog.values()
        status, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Update Status",
            "New Status",
            [
                "SOURCING",
                "ASSIGNED",
                "INTRANSIT",
                "DELIVERED",
                "PARTIAL",
                "FAILED",
            ],
            editable=False,
        )
        if not ok:
            return
        self.service.update_fulfillment(latest["id"], status, note=values["note"], eta_utc=values["eta_utc"])
        self.load_request(self.current_request_id)

    def _print_ics(self) -> None:
        if not self.current_request_id:
            return
        path = printers.render_ics_213rr(self.current_request_id)
        QtWidgets.QMessageBox.information(self, "PDF Generated", f"ICS-213 RR exported to {path}")

    def _print_summary(self) -> None:
        if not self.current_request_id:
            return
        path = printers.render_summary_sheet(self.current_request_id)
        QtWidgets.QMessageBox.information(self, "PDF Generated", f"Summary exported to {path}")
