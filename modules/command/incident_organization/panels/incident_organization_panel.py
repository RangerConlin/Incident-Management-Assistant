from __future__ import annotations

"""Qt Widgets foundation for Incident Organization Management."""

from collections import defaultdict
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
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
    QListWidget,
    QListWidgetItem,
    QMenu,
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
from ..models import OrganizationPosition, OrganizationTemplate, PositionAssignment


class PositionDialog(QDialog):
    """Small editor for custom AHJ-defined organization positions."""

    CLASSIFICATIONS = ["command", "section", "branch", "division", "group", "unit", "position"]
    _TOP_LEVEL_SENTINEL = -1

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        position: OrganizationPosition | None = None,
        parent_position_id: int | None = None,
        existing_positions: list[OrganizationPosition] | None = None,
        exclude_id: int | None = None,
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

        self.parent_combo = QComboBox(self)
        self.parent_combo.addItem("— Top Level (no parent) —", self._TOP_LEVEL_SENTINEL)
        preselect_id = (position.parent_position_id if position else parent_position_id) or self._TOP_LEVEL_SENTINEL
        self._populate_parent_combo(existing_positions or [], exclude_id, preselect_id)
        layout.addRow("Parent position", self.parent_combo)

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

    def _populate_parent_combo(
        self,
        positions: list[OrganizationPosition],
        exclude_id: int | None,
        preselect_id: int,
    ) -> None:
        """Add positions to the parent combo with depth-indented labels."""
        from collections import defaultdict

        by_parent: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for pos in positions:
            if pos.id != exclude_id:
                by_parent[pos.parent_position_id].append(pos)

        def add_children(parent_id: int | None, depth: int) -> None:
            for pos in by_parent.get(parent_id, []):
                label = "    " * depth + pos.title + f"  ({pos.classification})"
                self.parent_combo.addItem(label, pos.id)
                if pos.id == preselect_id:
                    self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)
                add_children(pos.id, depth + 1)

        add_children(None, 0)

    def values(self) -> dict[str, object]:
        raw_id = self.parent_combo.currentData()
        parent_id = None if raw_id == self._TOP_LEVEL_SENTINEL else raw_id
        return {
            "title": self.title_edit.text().strip(),
            "classification": self.classification_combo.currentText(),
            "parent_position_id": parent_id,
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


class TemplatesDialog(QDialog):
    """Dialog for previewing and loading organization templates."""

    def __init__(
        self, templates: list[OrganizationTemplate], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Organization Templates")
        self._templates_by_name = {template.name: template for template in templates}
        self._selected_name: str | None = None

        layout = QVBoxLayout(self)
        self.lst_templates = QListWidget(self)
        for template in sorted(templates, key=lambda item: item.name.lower()):
            item = QListWidgetItem(template.name)
            item.setData(Qt.UserRole, template.name)
            if template.description:
                item.setToolTip(template.description)
            self.lst_templates.addItem(item)
        self.lst_templates.currentItemChanged.connect(self._update_preview)
        layout.addWidget(self.lst_templates)

        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            "Select a template to preview the positions that will be created."
        )
        layout.addWidget(self.preview, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, self)
        buttons.button(QDialogButtonBox.Ok).setText("Load")
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.lst_templates.count():
            self.lst_templates.setCurrentRow(0)

    def _update_preview(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            self.preview.clear()
            return
        template = self._templates_by_name.get(str(current.data(Qt.UserRole)))
        if template is None:
            self.preview.clear()
            return
        lines: list[str] = []
        if template.description:
            lines.extend([template.description, ""])
        depths: dict[str, int] = {}
        for index, raw in enumerate(template.payload):
            key = str(raw.get("key") or f"item_{index}")
            parent_key = str(raw.get("parent_key") or "")
            depth = depths.get(parent_key, -1) + 1 if parent_key else 0
            depths[key] = depth
            title = str(raw.get("title") or "").strip() or "(Untitled)"
            classification = str(raw.get("classification") or "position")
            critical = " [critical]" if bool(raw.get("is_critical")) else ""
            lines.append(f"{'  ' * depth}{title} ({classification}){critical}")
        self.preview.setPlainText("\n".join(lines) if lines else "Template is empty.")

    def _handle_accept(self) -> None:
        item = self.lst_templates.currentItem()
        if item is None:
            self.reject()
            return
        self._selected_name = str(item.data(Qt.UserRole))
        self.accept()

    def selected_template_name(self) -> str | None:
        return self._selected_name


class _MoveUnderDialog(QDialog):
    """Prompt for choosing a new parent position (or top level) for a position."""

    _TOP_LEVEL_SENTINEL = -1

    def __init__(
        self,
        position_title: str,
        candidates: list[OrganizationPosition],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Move Position Under…")
        layout = QFormLayout(self)
        layout.addRow(QLabel(f'Move "{position_title}" under:', self))
        self.combo = QComboBox(self)
        self.combo.addItem("— Top Level (no parent) —", self._TOP_LEVEL_SENTINEL)
        from collections import defaultdict

        by_parent: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for pos in candidates:
            by_parent[pos.parent_position_id].append(pos)

        def add_children(parent_id: int | None, depth: int) -> None:
            for pos in by_parent.get(parent_id, []):
                label = "    " * depth + pos.title + f"  ({pos.classification})"
                self.combo.addItem(label, pos.id)
                add_children(pos.id, depth + 1)

        add_children(None, 0)
        layout.addRow("New parent", self.combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_parent_id(self) -> int | None:
        raw = self.combo.currentData()
        return None if raw == self._TOP_LEVEL_SENTINEL else raw


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
        self.btn_templates = QPushButton("Templates…", self)
        self.btn_templates.clicked.connect(self._apply_template)
        toolbar.addWidget(self.btn_templates)
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
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
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
            self.btn_templates,
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
        parent_label = "top level"
        if position.parent_position_id and position.parent_position_id in self._positions_by_id:
            parent_label = self._positions_by_id[position.parent_position_id].title
        self.detail_meta.setText(
            f"{position.classification} | Parent: {parent_label} | "
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
    def _show_tree_context_menu(self, point) -> None:
        if not self.incident_id:
            return
        menu = QMenu(self)
        action_add_child = QAction("Add Child Position…", self)
        action_add_child.triggered.connect(self._add_child_position)
        menu.addAction(action_add_child)
        action_add_sibling = QAction("Add Sibling Position…", self)
        action_add_sibling.triggered.connect(self._add_sibling_position)
        menu.addAction(action_add_sibling)
        action_add_top = QAction("Add Top-Level Position…", self)
        action_add_top.triggered.connect(self._add_position)
        menu.addAction(action_add_top)
        menu.addSeparator()
        position_id = self._selected_position_id()
        action_move = QAction("Move Under…", self)
        action_move.triggered.connect(self._move_position)
        action_move.setEnabled(bool(position_id))
        menu.addAction(action_move)
        menu.exec(self.tree.mapToGlobal(point))

    def _add_position(self) -> None:
        self._open_add_dialog(preset_parent_id=None)

    def _add_child_position(self) -> None:
        self._open_add_dialog(preset_parent_id=self._selected_position_id())

    def _add_sibling_position(self) -> None:
        position_id = self._selected_position_id()
        sibling_parent: int | None = None
        if position_id and position_id in self._positions_by_id:
            sibling_parent = self._positions_by_id[position_id].parent_position_id
        self._open_add_dialog(preset_parent_id=sibling_parent)

    def _open_add_dialog(self, *, preset_parent_id: int | None) -> None:
        if not self.incident_id:
            QMessageBox.warning(
                self,
                "Incident Required",
                "Load an incident before managing organization.",
            )
            return
        positions = list(self._positions_by_id.values())
        dialog = PositionDialog(
            self,
            parent_position_id=preset_parent_id,
            existing_positions=positions,
        )
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
        positions = list(self._positions_by_id.values())
        dialog = PositionDialog(
            self,
            position=position,
            existing_positions=positions,
            exclude_id=position_id,
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                self._ensure_controller().update_position(position_id, dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Position", str(exc))
                return
            self._refresh()

    def _move_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id or not self.incident_id:
            return
        position = self._positions_by_id.get(position_id)
        if position is None:
            return
        positions = [p for p in self._positions_by_id.values() if p.id != position_id]
        dialog = _MoveUnderDialog(position.title, positions, self)
        if dialog.exec() == QDialog.Accepted:
            new_parent = dialog.selected_parent_id()
            self._ensure_controller().move_position(position_id, new_parent)
            self._refresh()

    def _deactivate_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id:
            return
        self._ensure_controller().deactivate_position(position_id)
        self._refresh()

    def _apply_template(self) -> None:
        if not self.incident_id:
            active = self._active_incident_from_state()
            if active:
                self.load(active)
            else:
                QMessageBox.warning(
                    self,
                    "Incident Required",
                    "Load an incident before managing organization.",
                )
                return
        controller = self._ensure_controller()
        templates = controller.list_templates()
        if not templates:
            QMessageBox.information(
                self,
                "Organization Templates",
                "No organization templates are available.",
            )
            return
        dialog = TemplatesDialog(templates, self)
        if dialog.exec() != QDialog.Accepted:
            return
        template_name = dialog.selected_template_name()
        if not template_name:
            return
        try:
            applied_ids = controller.apply_template(template_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Organization Template", str(exc))
            return
        self._refresh()
        QMessageBox.information(
            self,
            "Template Loaded",
            f"Loaded {len(applied_ids)} organization positions from {template_name}.",
        )

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
