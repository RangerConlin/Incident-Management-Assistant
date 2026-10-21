"""Reusable "Associations" section for resource detail windows.

Dropped into the Personnel, Vehicle, Aircraft, and Equipment detail dialogs
so an operator can view/add/remove standing associations for that resource
and navigate to the associated resource's own detail window. This panel
never touches incident team data -- it only talks to
/api/resource-associations.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..data.repository import ApiResourceAssociationRepository
from ..models import ResourceAssociation, ResourceEndpoint
from .resource_picker_dialog import ResourcePickerDialog

_COLUMNS = ["Direction", "Type", "Resource", "Association Type", "Organization", "Active", "Notes"]

# Callbacks a host window can register to open a resource's own detail
# window when the user picks "Open" on an associated resource row.
_OPEN_HANDLERS: dict[str, Callable[[int], None]] = {}


def register_open_handler(resource_type: str, handler: Callable[[int], None]) -> None:
    """Let a module register how to open its own detail window by record id.

    Called once at import time by each detail-window module so the panel
    can navigate to *any* associated resource's detail window without
    importing all four modules up front (which would create import
    cycles -- personnel/vehicle/aircraft/equipment detail windows would
    each need to import this panel, which would need to import them back).
    """
    _OPEN_HANDLERS[resource_type] = handler


class _AddAssociationDialog(QDialog):
    def __init__(
        self,
        repository: ApiResourceAssociationRepository,
        self_endpoint: ResourceEndpoint,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Association")
        self._repository = repository
        self._self_endpoint = self_endpoint
        self.target_type: Optional[str] = None
        self.target_id: Optional[int] = None
        self.target_label: str = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.target_button = QPushButton("Select resource…")
        self.target_button.clicked.connect(self._pick_target)
        form.addRow("Associated resource", self.target_button)

        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        try:
            self.type_combo.addItems(self._repository.suggested_types())
        except Exception:
            pass
        form.addRow("Association type", self.type_combo)

        self.org_edit = QLineEdit()
        form.addRow("Owning organization", self.org_edit)

        self.notes_edit = QLineEdit()
        form.addRow("Notes", self.notes_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_target(self) -> None:
        dialog = ResourcePickerDialog(
            self,
            exclude=((self._self_endpoint.resource_type, self._self_endpoint.resource_id),),
        )
        if dialog.exec() == QDialog.Accepted:
            self.target_type = dialog.selected_resource_type
            self.target_id = dialog.selected_resource_id
            self.target_label = dialog.selected_label
            self.target_button.setText(f"{self.target_type}: {self.target_label}")

    def _validate_then_accept(self) -> None:
        if self.target_type is None or self.target_id is None:
            QMessageBox.warning(self, "Add Association", "Select an associated resource first.")
            return
        if not self.type_combo.currentText().strip():
            QMessageBox.warning(self, "Add Association", "Association type is required.")
            return
        self.accept()


class AssociationsPanel(QWidget):
    """Embeddable panel: view/add/remove standing associations for one resource."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[int],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._repository = ApiResourceAssociationRepository()
        self._resource_type = resource_type
        self._resource_id = resource_id
        self._rows: list[ResourceAssociation] = []

        box = QGroupBox("Associations")
        layout = QVBoxLayout(self)
        layout.addWidget(box)
        box_layout = QVBoxLayout(box)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        box_layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Add Association…")
        self.remove_button = QPushButton("Remove Selected")
        self.open_button = QPushButton("Open Associated Resource")
        self.add_button.clicked.connect(self._add_association)
        self.remove_button.clicked.connect(self._remove_selected)
        self.open_button.clicked.connect(self._open_selected)
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        box_layout.addLayout(actions)

        self.set_resource(resource_type, resource_id)

    def set_resource(self, resource_type: str, resource_id: Optional[int]) -> None:
        """Rebind to a different resource (e.g. after a new record is saved
        and gets its id for the first time)."""
        self._resource_type = resource_type
        self._resource_id = resource_id
        has_id = resource_id is not None
        self.add_button.setEnabled(has_id)
        self.remove_button.setEnabled(has_id)
        self.open_button.setEnabled(has_id)
        self.reload()

    def reload(self) -> None:
        self.table.setRowCount(0)
        if self._resource_id is None:
            return
        try:
            self._rows = self._repository.list_for_resource(self._resource_type, int(self._resource_id))
        except Exception:
            self._rows = []
        for row in self._rows:
            self._append_row(row)

    def _append_row(self, assoc: ResourceAssociation) -> None:
        is_source = (
            assoc.source.resource_type == self._resource_type and assoc.source.resource_id == self._resource_id
        )
        other = assoc.target if is_source else assoc.source
        direction = "→" if is_source else "←"
        r = self.table.rowCount()
        self.table.insertRow(r)
        values = [
            direction,
            other.resource_type,
            other.label or str(other.resource_id),
            assoc.association_type,
            assoc.owning_organization or "",
            "Yes" if assoc.active else "No",
            assoc.notes or "",
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 0:
                item.setData(Qt.UserRole, assoc.id)
            self.table.setItem(r, col, item)

    def _selected_association(self) -> Optional[ResourceAssociation]:
        sel = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        row = sel[0].row() if sel else self.table.currentRow()
        if row is None or row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _add_association(self) -> None:
        if self._resource_id is None:
            return
        self_endpoint = ResourceEndpoint(resource_type=self._resource_type, resource_id=int(self._resource_id))
        dialog = _AddAssociationDialog(self._repository, self_endpoint, self)
        if dialog.exec() != QDialog.Accepted:
            return
        association = ResourceAssociation(
            source=self_endpoint,
            target=ResourceEndpoint(resource_type=dialog.target_type, resource_id=int(dialog.target_id)),
            association_type=dialog.type_combo.currentText().strip(),
            owning_organization=dialog.org_edit.text().strip() or None,
            notes=dialog.notes_edit.text().strip(),
        )
        try:
            self._repository.create(association)
        except Exception as exc:
            from utils.api_client import APIError

            if isinstance(exc, APIError):
                QMessageBox.warning(self, "Add Association", str(exc))
            else:
                QMessageBox.warning(self, "Add Association", f"Failed to add association: {exc}")
            return
        self.reload()

    def _remove_selected(self) -> None:
        assoc = self._selected_association()
        if assoc is None or assoc.id is None:
            return
        if QMessageBox.question(
            self, "Remove Association", "Remove this association? This does not delete either resource."
        ) != QMessageBox.Yes:
            return
        try:
            self._repository.delete(assoc.id)
        except Exception as exc:
            QMessageBox.warning(self, "Remove Association", f"Failed to remove association: {exc}")
            return
        self.reload()

    def _open_selected(self) -> None:
        assoc = self._selected_association()
        if assoc is None:
            return
        is_source = (
            assoc.source.resource_type == self._resource_type and assoc.source.resource_id == self._resource_id
        )
        other = assoc.target if is_source else assoc.source
        handler = _OPEN_HANDLERS.get(other.resource_type)
        if handler is None:
            QMessageBox.information(
                self, "Open Associated Resource", f"No detail window is registered for {other.resource_type}."
            )
            return
        handler(other.resource_id)
