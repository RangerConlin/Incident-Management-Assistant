"""
ResourceRequirementEditor
=========================
Tab widget for managing resource requirements on a Work Assignment (ICS 215 style).

Shows a table of requirements and, when a row is selected, the actual
resources assigned to that requirement below it.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.resource_gap_service import ResourceGapService
from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import PRIORITY_VALUES

# Try to import the ResourceTypeSearchBox — degrade gracefully if unavailable
try:
    from modules.admin.resource_types.widgets.resource_type_search_box import ResourceTypeSearchBox
    _HAS_SEARCH_BOX = True
except ImportError:
    _HAS_SEARCH_BOX = False


class ResourceRequirementEditor(QWidget):
    """
    Displays and edits the resource requirements for one Work Assignment.

    Signals:
        changed() — emitted after any add/update/remove operation so the
                    parent window can refresh its summary counts.
    """

    changed = Signal()

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path
        self._gap_service = ResourceGapService(db_path)
        self._selected_req_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Vertical, self)
        layout.addWidget(splitter)

        # Top: requirements table
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        btn_bar = QHBoxLayout()
        self._add_btn = QPushButton("Add Requirement")
        self._edit_btn = QPushButton("Edit")
        self._remove_btn = QPushButton("Remove")
        self._recalc_btn = QPushButton("Recalculate Gaps")
        self._logistics_btn = QPushButton("Create Logistics Request")
        self._logistics_btn.setEnabled(False)  # pending integration
        self._logistics_btn.setToolTip("Logistics Request integration pending.")
        for btn in (self._add_btn, self._edit_btn, self._remove_btn,
                    self._recalc_btn, self._logistics_btn):
            btn_bar.addWidget(btn)
        btn_bar.addStretch(1)
        top_layout.addLayout(btn_bar)

        # Requirements table
        req_columns = ["Resource Type", "Capability", "Req.", "Assigned", "Available", "Gap", "Priority", "Notes"]
        self._req_table = QTableWidget(0, len(req_columns))
        self._req_table.setHorizontalHeaderLabels(req_columns)
        self._req_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._req_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._req_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._req_table.horizontalHeader().setStretchLastSection(True)
        self._req_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout.addWidget(self._req_table)
        splitter.addWidget(top_widget)

        # Bottom: actual assigned resources
        bottom_group = QGroupBox("Actual Assigned Resources (for selected requirement)")
        bottom_layout = QVBoxLayout(bottom_group)

        assign_btn_bar = QHBoxLayout()
        self._assign_btn = QPushButton("Assign Resource")
        self._remove_assign_btn = QPushButton("Remove Assigned")
        assign_btn_bar.addWidget(self._assign_btn)
        assign_btn_bar.addWidget(self._remove_assign_btn)
        assign_btn_bar.addStretch(1)
        bottom_layout.addLayout(assign_btn_bar)

        assign_columns = ["Kind", "ID", "Display Name", "Status", "Assigned At", "Released At"]
        self._assign_table = QTableWidget(0, len(assign_columns))
        self._assign_table.setHorizontalHeaderLabels(assign_columns)
        self._assign_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._assign_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._assign_table.horizontalHeader().setStretchLastSection(True)
        bottom_layout.addWidget(self._assign_table)
        splitter.addWidget(bottom_group)

        splitter.setSizes([300, 150])

        # Wire signals
        self._add_btn.clicked.connect(self._add_requirement)
        self._edit_btn.clicked.connect(self._edit_requirement)
        self._remove_btn.clicked.connect(self._remove_requirement)
        self._recalc_btn.clicked.connect(self._recalculate_gaps)
        self._assign_btn.clicked.connect(self._assign_resource)
        self._remove_assign_btn.clicked.connect(self._remove_assigned)
        self._req_table.itemSelectionChanged.connect(self._on_req_selected)

        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Reload requirements from the database."""
        try:
            repo = WorkAssignmentRepository(self._db_path)
            reqs = repo.list_resource_requirements(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Resources", f"Failed to load resources:\n{exc}")
            return
        self._req_table.setRowCount(0)
        for req in reqs:
            row = self._req_table.rowCount()
            self._req_table.insertRow(row)
            self._req_table.setItem(row, 0, QTableWidgetItem(req.resource_type_text))
            self._req_table.setItem(row, 1, QTableWidgetItem(req.capability_text))
            self._req_table.setItem(row, 2, QTableWidgetItem(str(req.quantity_required)))
            self._req_table.setItem(row, 3, QTableWidgetItem(str(req.quantity_assigned)))
            self._req_table.setItem(row, 4, QTableWidgetItem(str(req.quantity_available)))
            gap = max(req.quantity_required - req.quantity_assigned, 0)
            gap_item = QTableWidgetItem(str(gap))
            if gap > 0:
                gap_item.setForeground(Qt.red)
            self._req_table.setItem(row, 5, gap_item)
            self._req_table.setItem(row, 6, QTableWidgetItem(req.priority))
            self._req_table.setItem(row, 7, QTableWidgetItem(req.notes))
            # Store the DB id in UserRole
            self._req_table.item(row, 0).setData(Qt.UserRole, req.id)

    def _reload_assigned(self, requirement_id: int) -> None:
        """Reload the actual assigned resources for the selected requirement."""
        self._assign_table.setRowCount(0)
        try:
            repo = WorkAssignmentRepository(self._db_path)
            assigned = repo.list_assigned_resources(requirement_id)
        except Exception:
            return
        for a in assigned:
            row = self._assign_table.rowCount()
            self._assign_table.insertRow(row)
            self._assign_table.setItem(row, 0, QTableWidgetItem(a.resource_kind))
            self._assign_table.setItem(row, 1, QTableWidgetItem(a.resource_id))
            self._assign_table.setItem(row, 2, QTableWidgetItem(a.display_name))
            self._assign_table.setItem(row, 3, QTableWidgetItem(a.status))
            self._assign_table.setItem(row, 4, QTableWidgetItem(a.assigned_at))
            self._assign_table.setItem(row, 5, QTableWidgetItem(a.released_at))
            self._assign_table.item(row, 0).setData(Qt.UserRole, a.id)

    def _current_req_id(self) -> int | None:
        row = self._req_table.currentRow()
        if row < 0:
            return None
        item = self._req_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_req_selected(self) -> None:
        req_id = self._current_req_id()
        self._selected_req_id = req_id
        if req_id is not None:
            self._reload_assigned(req_id)
        else:
            self._assign_table.setRowCount(0)

    # ------------------------------------------------------------------

    def _add_requirement(self) -> None:
        dialog = _ResourceRequirementDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data.get("resource_type_text"):
            QMessageBox.warning(self, "Add Requirement", "Resource type text is required.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.add_resource_requirement(self._work_assignment_id, data)
        except Exception as exc:
            QMessageBox.critical(self, "Add Requirement", f"Failed to add requirement:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _edit_requirement(self) -> None:
        req_id = self._current_req_id()
        if req_id is None:
            QMessageBox.information(self, "Edit", "Select a requirement first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            reqs = repo.list_resource_requirements(self._work_assignment_id)
            req = next((r for r in reqs if r.id == req_id), None)
        except Exception:
            req = None
        if not req:
            return
        dialog = _ResourceRequirementDialog(existing=req, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.update_resource_requirement(req_id, data)
            repo.recalculate_resource_gap(req_id)
        except Exception as exc:
            QMessageBox.critical(self, "Edit Requirement", f"Failed to update:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _remove_requirement(self) -> None:
        req_id = self._current_req_id()
        if req_id is None:
            QMessageBox.information(self, "Remove", "Select a requirement first.")
            return
        if QMessageBox.question(
            self, "Remove Requirement", "Remove this resource requirement?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.remove_resource_requirement(req_id)
        except Exception as exc:
            QMessageBox.critical(self, "Remove", f"Failed to remove:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _recalculate_gaps(self) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.recalculate_all_resource_gaps(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Recalculate", f"Failed to recalculate gaps:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _assign_resource(self) -> None:
        req_id = self._current_req_id()
        if req_id is None:
            QMessageBox.information(self, "Assign Resource", "Select a requirement row first.")
            return
        dialog = _AssignResourceDialog(req_id, self._gap_service, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data.get("resource_id"):
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.assign_actual_resource(
                req_id,
                data["resource_kind"],
                data["resource_id"],
                data.get("display_name", ""),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Assign Resource", f"Failed to assign:\n{exc}")
            return
        self._reload_assigned(req_id)
        self.reload()
        self.changed.emit()

    def _remove_assigned(self) -> None:
        row = self._assign_table.currentRow()
        if row < 0:
            return
        item = self._assign_table.item(row, 0)
        if not item:
            return
        assignment_id = item.data(Qt.UserRole)
        if QMessageBox.question(
            self, "Remove", "Remove this resource assignment?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.remove_actual_resource(assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Remove", f"Failed to remove:\n{exc}")
            return
        req_id = self._current_req_id()
        if req_id:
            self._reload_assigned(req_id)
        self.reload()
        self.changed.emit()


# ---------------------------------------------------------------------------
# Add/Edit requirement dialog
# ---------------------------------------------------------------------------

class _ResourceRequirementDialog(QDialog):
    """Simple dialog for adding or editing a resource requirement."""

    def __init__(self, existing=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resource Requirement")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._resource_type_id: int | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # Resource type — use smart search box if available, otherwise plain text
        if _HAS_SEARCH_BOX:
            self._type_search = ResourceTypeSearchBox()
            self._type_search.resourceTypeSelected.connect(self._on_type_selected)
            form.addRow("Resource Type *", self._type_search)
        else:
            self._type_search = None
            self._type_text = QLineEdit()
            self._type_text.setPlaceholderText("Resource type (required)")
            form.addRow("Resource Type *", self._type_text)

        self._capability_edit = QLineEdit()
        self._capability_edit.setPlaceholderText("Optional capability")
        form.addRow("Capability", self._capability_edit)

        self._qty_spin = QSpinBox()
        self._qty_spin.setMinimum(1)
        self._qty_spin.setMaximum(9999)
        self._qty_spin.setValue(1)
        form.addRow("Quantity Required *", self._qty_spin)

        self._priority_combo = QComboBox()
        self._priority_combo.addItems(PRIORITY_VALUES)
        self._priority_combo.setCurrentText("Normal")
        form.addRow("Priority", self._priority_combo)

        self._notes_edit = QLineEdit()
        form.addRow("Notes", self._notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing:
            self._populate(existing)

    def _on_type_selected(self, type_id, type_text: str) -> None:
        self._resource_type_id = type_id

    def _populate(self, req) -> None:
        self._resource_type_id = req.resource_type_id
        if _HAS_SEARCH_BOX and self._type_search:
            self._type_search.set_value(req.resource_type_id, req.resource_type_text)
        elif hasattr(self, "_type_text"):
            self._type_text.setText(req.resource_type_text)
        self._capability_edit.setText(req.capability_text)
        self._qty_spin.setValue(req.quantity_required)
        self._priority_combo.setCurrentText(req.priority)
        self._notes_edit.setText(req.notes)

    def get_data(self) -> dict:
        if _HAS_SEARCH_BOX and self._type_search:
            type_text = self._type_search.resource_type_text or ""
            type_id = self._type_search.resource_type_id
        else:
            type_text = self._type_text.text().strip() if hasattr(self, "_type_text") else ""
            type_id = self._resource_type_id
        return {
            "resource_type_id": type_id,
            "resource_type_text": type_text,
            "capability_text": self._capability_edit.text().strip(),
            "quantity_required": self._qty_spin.value(),
            "priority": self._priority_combo.currentText(),
            "notes": self._notes_edit.text().strip(),
        }


# ---------------------------------------------------------------------------
# Assign actual resource dialog
# ---------------------------------------------------------------------------

class _AssignResourceDialog(QDialog):
    """Dialog for assigning a specific resource to a requirement."""

    _KINDS = ["personnel", "team", "vehicle", "equipment", "aircraft", "facility", "supply", "other"]

    def __init__(
        self,
        requirement_id: int,
        gap_service: ResourceGapService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Resource")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._kind_combo = QComboBox()
        self._kind_combo.addItems(self._KINDS)
        form.addRow("Resource Kind", self._kind_combo)

        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("Resource ID or name")
        form.addRow("Resource ID *", self._id_edit)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Display name")
        form.addRow("Display Name", self._name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "resource_kind": self._kind_combo.currentText(),
            "resource_id": self._id_edit.text().strip(),
            "display_name": self._name_edit.text().strip(),
        }
