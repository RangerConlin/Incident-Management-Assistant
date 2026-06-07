from __future__ import annotations

"""Qt Widgets foundation for Incident Organization Management."""

from collections import defaultdict
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from styles.colors import MUTED_TEXT
from utils.app_signals import app_signals
from utils.state import AppState

from ..controller import IncidentOrganizationController
from ..models import OrganizationPosition, PositionAssignment


class PositionDialog(QDialog):
    """Small editor for custom AHJ-defined organization positions."""

    CLASSIFICATIONS = ["command", "section", "branch", "division", "group", "unit", "position"]

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        position: OrganizationPosition | None = None,
        parent_position_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Position")
        layout = QFormLayout(self)
        self.title_edit = QLineEdit(position.title if position else "", self)
        layout.addRow("Title", self.title_edit)
        self.classification_combo = QComboBox(self)
        self.classification_combo.addItems(self.CLASSIFICATIONS)
        selected = position.classification if position else "position"
        self.classification_combo.setCurrentText(selected if selected in self.CLASSIFICATIONS else "position")
        layout.addRow("Classification", self.classification_combo)
        self.parent_edit = QLineEdit(
            str(position.parent_position_id if position else parent_position_id or ""), self
        )
        layout.addRow("Parent position ID", self.parent_edit)
        self.period_edit = QLineEdit(position.operational_period if position else "", self)
        layout.addRow("Operational period", self.period_edit)
        quals = ", ".join(position.required_qualifications) if position else ""
        self.qualifications_edit = QLineEdit(quals, self)
        layout.addRow("Required qualifications", self.qualifications_edit)
        self.critical_check = QCheckBox("Critical position", self)
        self.critical_check.setChecked(bool(position.is_critical) if position else False)
        layout.addRow("", self.critical_check)
        self.custom_check = QCheckBox("Custom AHJ-defined title/structure", self)
        self.custom_check.setChecked(True if position is None else bool(position.is_custom))
        layout.addRow("", self.custom_check)
        self.notes_edit = QTextEdit(position.notes if position and position.notes else "", self)
        self.notes_edit.setMaximumHeight(80)
        layout.addRow("Notes", self.notes_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict[str, object]:
        parent_text = self.parent_edit.text().strip()
        return {
            "title": self.title_edit.text().strip(),
            "classification": self.classification_combo.currentText(),
            "parent_position_id": int(parent_text) if parent_text else None,
            "operational_period": self.period_edit.text().strip(),
            "required_qualifications": self.qualifications_edit.text().strip(),
            "is_critical": self.critical_check.isChecked(),
            "is_custom": self.custom_check.isChecked(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class AssignmentDialog(QDialog):
    """Dialog for assigning personnel to a selected position."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        personnel: dict[str, object | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Personnel")
        layout = QFormLayout(self)
        self.personnel_id_edit = QLineEdit(str((personnel or {}).get("id") or ""), self)
        layout.addRow("Personnel ID", self.personnel_id_edit)
        self.name_edit = QLineEdit(str((personnel or {}).get("name") or ""), self)
        layout.addRow("Name", self.name_edit)
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["primary", "deputy", "assistant", "trainee", "relief"])
        layout.addRow("Assignment type", self.type_combo)
        self.period_edit = QLineEdit("", self)
        layout.addRow("Operational period", self.period_edit)
        self.assigned_by_edit = QLineEdit("", self)
        layout.addRow("Assigned by", self.assigned_by_edit)
        self.notes_edit = QTextEdit("", self)
        self.notes_edit.setMaximumHeight(80)
        layout.addRow("Notes", self.notes_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict[str, object]:
        return {
            "personnel_id": self.personnel_id_edit.text().strip(),
            "display_name": self.name_edit.text().strip(),
            "assignment_type": self.type_combo.currentText(),
            "operational_period": self.period_edit.text().strip(),
            "assigned_by": self.assigned_by_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class IncidentOrganizationPanel(QWidget):
    """Tree, detail, staffing, and generator support for incident organization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("IncidentOrganizationPanel")
        self.incident_id: Optional[str] = None
        self.controller: Optional[IncidentOrganizationController] = None
        self._positions_by_id: dict[int, OrganizationPosition] = {}
        self._pool_rows: list[dict[str, object | None]] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        toolbar = QHBoxLayout()
        self.btn_add_position = QPushButton("Add Position…", self)
        self.btn_add_position.clicked.connect(self._add_position)
        toolbar.addWidget(self.btn_add_position)
        self.btn_edit_position = QPushButton("Edit Position…", self)
        self.btn_edit_position.clicked.connect(self._edit_position)
        toolbar.addWidget(self.btn_edit_position)
        self.btn_deactivate_position = QPushButton("Deactivate", self)
        self.btn_deactivate_position.clicked.connect(self._deactivate_position)
        toolbar.addWidget(self.btn_deactivate_position)
        toolbar.addStretch(1)
        self.btn_ics203 = QPushButton("Prepare ICS 203", self)
        self.btn_ics203.clicked.connect(lambda: self._prepare_form("ICS_203"))
        toolbar.addWidget(self.btn_ics203)
        self.btn_ics207 = QPushButton("Prepare ICS 207", self)
        self.btn_ics207.clicked.connect(lambda: self._prepare_form("ICS_207"))
        toolbar.addWidget(self.btn_ics207)
        root_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal, self)
        root_layout.addWidget(splitter, stretch=1)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Organization", "Status"])
        self.tree.itemSelectionChanged.connect(self._handle_tree_selection)
        splitter.addWidget(self.tree)

        center = QWidget(self)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_title = QLabel("Select a position", center)
        self.detail_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        center_layout.addWidget(self.detail_title)
        self.detail_meta = QLabel("", center)
        self.detail_meta.setStyleSheet(f"color: {MUTED_TEXT};")
        center_layout.addWidget(self.detail_meta)
        self.status_label = QLabel("", center)
        center_layout.addWidget(self.status_label)
        self.warning_label = QLabel("", center)
        self.warning_label.setWordWrap(True)
        center_layout.addWidget(self.warning_label)
        center_layout.addWidget(QLabel("Assigned Personnel", center))
        self.assignments_table = QTableWidget(center)
        self.assignments_table.setColumnCount(5)
        self.assignments_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Start", "Operational Period", "Notes"]
        )
        self.assignments_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.assignments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.assignments_table.horizontalHeader().setStretchLastSection(True)
        center_layout.addWidget(self.assignments_table, stretch=1)
        assignment_buttons = QHBoxLayout()
        self.btn_assign_selected = QPushButton("Assign Selected", center)
        self.btn_assign_selected.clicked.connect(self._assign_selected_person)
        assignment_buttons.addWidget(self.btn_assign_selected)
        self.btn_remove_assignment = QPushButton("Remove Assignment", center)
        self.btn_remove_assignment.clicked.connect(self._remove_selected_assignment)
        assignment_buttons.addWidget(self.btn_remove_assignment)
        assignment_buttons.addStretch(1)
        center_layout.addLayout(assignment_buttons)
        splitter.addWidget(center)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Personnel Assignment Pool", right))
        filter_row = QHBoxLayout()
        self.personnel_search = QLineEdit(right)
        self.personnel_search.setPlaceholderText("Search checked-in/available/qualified personnel")
        filter_row.addWidget(self.personnel_search, stretch=1)
        self.btn_search_personnel = QPushButton("Search", right)
        self.btn_search_personnel.clicked.connect(self._search_personnel)
        filter_row.addWidget(self.btn_search_personnel)
        right_layout.addLayout(filter_row)
        self.filter_checked_in = QCheckBox("Checked-in", right)
        self.filter_available = QCheckBox("Available", right)
        self.filter_qualified = QCheckBox("Qualified", right)
        for checkbox in (self.filter_checked_in, self.filter_available, self.filter_qualified):
            checkbox.setEnabled(False)
            right_layout.addWidget(checkbox)
        self.pool_table = QTableWidget(right)
        self.pool_table.setColumnCount(4)
        self.pool_table.setHorizontalHeaderLabels(["Name", "Callsign", "Agency", "Phone"])
        self.pool_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pool_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pool_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.pool_table, stretch=1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        self._set_enabled(False)
        self._init_incident_tracking()

    # ------------------------------------------------------------------
    def load(self, incident_id: str) -> None:
        self.incident_id = str(incident_id)
        self.controller = IncidentOrganizationController(self.incident_id)
        self._refresh()
        self._set_enabled(True)

    def _ensure_controller(self) -> IncidentOrganizationController:
        if self.controller is None:
            if not self.incident_id:
                raise RuntimeError("Incident must be loaded before managing organization")
            self.controller = IncidentOrganizationController(self.incident_id)
        return self.controller

    def _init_incident_tracking(self) -> None:
        active = self._active_incident_from_state()
        if active:
            self.load(active)
        app_signals.incidentChanged.connect(self._handle_incident_changed)

    @staticmethod
    def _active_incident_from_state() -> str | None:
        active = AppState.get_active_incident()
        return str(active) if active else None

    def _handle_incident_changed(self, incident_id: str) -> None:
        if incident_id:
            self.load(str(incident_id))

    def _set_enabled(self, enabled: bool) -> None:
        for button in (
            self.btn_add_position,
            self.btn_edit_position,
            self.btn_deactivate_position,
            self.btn_ics203,
            self.btn_ics207,
            self.btn_assign_selected,
            self.btn_remove_assignment,
            self.btn_search_personnel,
        ):
            button.setEnabled(enabled)

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._refresh_tree()
        self._handle_tree_selection()

    def _refresh_tree(self) -> None:
        controller = self._ensure_controller()
        positions = controller.list_positions()
        summary = controller.staffing_summary()
        self._positions_by_id = {position.id or 0: position for position in positions}
        children: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for position in positions:
            children[position.parent_position_id].append(position)
        self.tree.clear()

        def add_items(parent_item: QTreeWidget | QTreeWidgetItem, parent_id: int | None) -> None:
            for position in children.get(parent_id, []):
                item_summary = summary.get(position.id or 0)
                status = item_summary.staffing_status if item_summary else "unknown"
                item = QTreeWidgetItem([position.title, status])
                item.setData(0, Qt.UserRole, position.id)
                if item_summary and item_summary.warnings:
                    item.setToolTip(0, "\n".join(w.message for w in item_summary.warnings))
                parent_item.addChild(item)
                add_items(item, position.id)

        add_items(self.tree.invisibleRootItem(), None)
        self.tree.expandAll()

    def _selected_position_id(self) -> int | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value = items[0].data(0, Qt.UserRole)
        return int(value) if value else None

    def _handle_tree_selection(self) -> None:
        position_id = self._selected_position_id()
        self.btn_edit_position.setEnabled(bool(position_id and self.incident_id))
        self.btn_deactivate_position.setEnabled(bool(position_id and self.incident_id))
        self.btn_assign_selected.setEnabled(bool(position_id and self.incident_id))
        self.btn_remove_assignment.setEnabled(bool(position_id and self.incident_id))
        if not position_id or self.controller is None:
            self.detail_title.setText("Select a position")
            self.detail_meta.setText("")
            self.status_label.setText("")
            self.warning_label.setText("")
            self.assignments_table.setRowCount(0)
            return
        position = self.controller.get_position(position_id)
        if position is None:
            return
        assignments = self.controller.list_assignments(position_id)
        summary = self.controller.staffing_summary().get(position_id)
        self.detail_title.setText(position.title)
        self.detail_meta.setText(
            f"{position.classification} | Parent: {position.parent_position_id or 'top level'} | "
            f"Operational period: {position.operational_period or 'any'}"
        )
        critical = "Critical" if position.is_critical else "Standard"
        self.status_label.setText(
            f"Status: {(summary.staffing_status if summary else 'unknown')} | {critical} | "
            f"Required: {', '.join(position.required_qualifications) or 'none'}"
        )
        warnings = summary.warnings if summary else []
        self.warning_label.setText("\n".join(w.message for w in warnings))
        self._populate_assignments(assignments)

    def _populate_assignments(self, assignments: list[PositionAssignment]) -> None:
        self.assignments_table.setRowCount(len(assignments))
        for row, assignment in enumerate(assignments):
            values = [
                assignment.display_name,
                assignment.assignment_type,
                assignment.start_time or "",
                assignment.operational_period or "",
                assignment.notes or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, assignment.id)
                self.assignments_table.setItem(row, col, item)

    # ------------------------------------------------------------------
    def _add_position(self) -> None:
        if not self.incident_id:
            QMessageBox.warning(
                self,
                "Incident Required",
                "Load an incident before managing organization.",
            )
            return
        dialog = PositionDialog(self, parent_position_id=self._selected_position_id())
        if dialog.exec() == QDialog.Accepted:
            try:
                self._ensure_controller().add_position(dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Position", str(exc))
                return
            self._refresh()

    def _edit_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id:
            return
        position = self._ensure_controller().get_position(position_id)
        if position is None:
            return
        dialog = PositionDialog(self, position=position)
        if dialog.exec() == QDialog.Accepted:
            try:
                self._ensure_controller().update_position(position_id, dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Position", str(exc))
                return
            self._refresh()

    def _deactivate_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id:
            return
        self._ensure_controller().deactivate_position(position_id)
        self._refresh()

    def _search_personnel(self) -> None:
        if self.controller is None:
            return
        self._pool_rows = self.controller.personnel_pool(self.personnel_search.text())
        self.pool_table.setRowCount(len(self._pool_rows))
        for row, person in enumerate(self._pool_rows):
            values = [
                str(person.get("name") or ""),
                str(person.get("callsign") or ""),
                str(person.get("agency") or ""),
                str(person.get("phone") or ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, person.get("id"))
                self.pool_table.setItem(row, col, item)

    def _assign_selected_person(self) -> None:
        position_id = self._selected_position_id()
        if not position_id:
            return
        personnel = None
        selected = self.pool_table.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._pool_rows):
                personnel = self._pool_rows[row]
        dialog = AssignmentDialog(self, personnel=personnel)
        if dialog.exec() == QDialog.Accepted:
            try:
                _, warnings = self._ensure_controller().assign_person(
                    position_id, dialog.values()
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Assignment", str(exc))
                return
            if warnings:
                QMessageBox.warning(
                    self,
                    "Qualification Review",
                    "\n".join(w.message for w in warnings),
                )
            self._refresh()

    def _remove_selected_assignment(self) -> None:
        selected = self.assignments_table.selectedItems()
        if not selected:
            return
        assignment_id = selected[0].data(Qt.UserRole)
        if assignment_id:
            self._ensure_controller().remove_assignment(int(assignment_id))
            self._refresh()

    def _prepare_form(self, form_type: str) -> None:
        controller = self._ensure_controller()
        payload = (
            controller.build_ics207_payload()
            if form_type == "ICS_207"
            else controller.build_ics203_payload()
        )
        controller.save_generated_snapshot(form_type, payload)
        QMessageBox.information(
            self,
            "Generated Output Prepared",
            f"{form_type.replace('_', ' ')} data was prepared from the incident organization.",
        )
