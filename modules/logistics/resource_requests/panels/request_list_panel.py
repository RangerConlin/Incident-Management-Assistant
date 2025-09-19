"""List panel showing resource requests with filters and bulk actions."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .. import get_service
from ..api.service import ResourceRequestService
from ..api.validators import ValidationError
from ..models.enums import ApprovalAction
from .dialogs import NoteDialog
from .widgets.filters_bar import FiltersBar


class ResourceRequestListPanel(QtWidgets.QWidget):
    """Main entry point for viewing resource requests."""

    requestActivated = QtCore.Signal(str)

    def __init__(self, service: ResourceRequestService | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service or get_service()
        self._filters: dict[str, object] = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.filters_bar = FiltersBar(self)
        self.filters_bar.filtersChanged.connect(self._on_filters_changed)
        layout.addWidget(self.filters_bar)

        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Title", "Priority", "Status", "Needed By", "Updated"])

        self.table = QtWidgets.QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.doubleClicked.connect(self._on_double_click)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        button_bar = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton("New Request")
        self.new_button.clicked.connect(self._new_request)
        button_bar.addWidget(self.new_button)

        self.submit_button = QtWidgets.QPushButton("Submit")
        self.submit_button.clicked.connect(lambda: self._bulk_action(ApprovalAction.SUBMIT))
        button_bar.addWidget(self.submit_button)

        self.approve_button = QtWidgets.QPushButton("Approve")
        self.approve_button.clicked.connect(lambda: self._bulk_action(ApprovalAction.APPROVE))
        button_bar.addWidget(self.approve_button)

        self.deny_button = QtWidgets.QPushButton("Deny")
        self.deny_button.clicked.connect(lambda: self._bulk_action(ApprovalAction.DENY, require_note=True))
        button_bar.addWidget(self.deny_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(lambda: self._bulk_action(ApprovalAction.CANCEL))
        button_bar.addWidget(self.cancel_button)

        button_bar.addStretch(1)
        layout.addLayout(button_bar)

        QtWidgets.QShortcut(QtGui.QKeySequence.New, self, self._new_request)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL | QtCore.Qt.Key_Return), self, self._submit_selected)

        self.refresh()

    # ----------------------------------------------------------------- utilities
    def _new_request(self) -> None:
        self.requestActivated.emit("NEW")

    def _submit_selected(self) -> None:
        if not self.selection():
            return
        self._bulk_action(ApprovalAction.SUBMIT)

    def _on_double_click(self, index: QtCore.QModelIndex) -> None:
        request_id = index.sibling(index.row(), 0).data(QtCore.Qt.UserRole)
        if request_id:
            self.requestActivated.emit(request_id)

    def _on_filters_changed(self, filters: dict[str, object]) -> None:
        self._filters = filters
        self.refresh()

    def refresh(self) -> None:
        self.model.removeRows(0, self.model.rowCount())
        try:
            records = self.service.list_requests(self._filters)
        except Exception as exc:  # pragma: no cover - defensive
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return

        for record in records:
            row = [QtGui.QStandardItem(str(record.get("title", "")))]
            row[0].setData(record["id"], QtCore.Qt.UserRole)
            row.append(QtGui.QStandardItem(record.get("priority", "")))
            row.append(QtGui.QStandardItem(record.get("status", "")))
            row.append(QtGui.QStandardItem(record.get("needed_by_utc", "")))
            row.append(QtGui.QStandardItem(record.get("last_updated_utc", "")))
            self.model.appendRow(row)

    def selection(self) -> list[str]:
        selection = []
        for index in self.table.selectionModel().selectedRows():
            request_id = index.sibling(index.row(), 0).data(QtCore.Qt.UserRole)
            if request_id:
                selection.append(request_id)
        return selection

    def _bulk_action(self, action: ApprovalAction, require_note: bool = False) -> None:
        request_ids = self.selection()
        if not request_ids:
            return

        note = None
        if require_note:
            dialog = NoteDialog("Provide Note", "A note is required for this action.", True, self)
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            note = dialog.note

        for request_id in request_ids:
            try:
                self.service.record_approval(request_id, action.value, actor_id="ui", note=note)
            except ValidationError as exc:
                QtWidgets.QMessageBox.warning(self, "Validation", str(exc))
        self.refresh()
