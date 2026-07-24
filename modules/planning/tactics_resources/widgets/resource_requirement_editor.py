"""
ResourceRequirementEditor
=========================
Tab widget for managing resource requirements on a Work Assignment (ICS 215 style).

Shows a table of requirements and, when a row is selected, the actual
resources assigned to that requirement below it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from modules.planning.tactics_resources.data.resource_gap_service import ResourceGapService
from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import PRIORITY_VALUES
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import get_palette, subscribe_theme, wa_priority_colors

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

    _REQ_COLUMN_WIDTHS = {
        0: 210,
        1: 180,
        2: 86,
        3: 54,
        4: 58,
        5: 54,
        6: 48,
    }
    _ASSIGN_COLUMN_WIDTHS = {
        0: 96,
        2: 120,
        3: 140,
    }

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
        top_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("RESOURCE REQUIREMENTS")
        title.setStyleSheet(
            f"color:{get_palette().get('fg_muted').name()}; font-weight:700;"
        )
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        self._add_btn = QPushButton("Add Requirement")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._summary_label)
        header.addWidget(self._add_btn)
        top_layout.addLayout(header)

        self._edit_btn = QPushButton("Edit")
        self._remove_btn = QPushButton("Remove")
        self._logistics_btn = QPushButton("Create Logistics Request")
        self._logistics_btn.setToolTip("Create a Logistics Resource Request (ICS-213RR) for the selected requirement.")

        # Requirements table
        req_columns = ["Resource Type", "Capability", "Priority", "Req.", "Assn.", "Avail.", "Gap", "Notes"]
        self._req_table = QTableWidget(0, len(req_columns))
        self._req_table.setHorizontalHeaderLabels(req_columns)
        apply_statusboard_table_behavior(self._req_table, stretch_last_section=True)
        self._apply_compact_table_header(self._req_table, self._REQ_COLUMN_WIDTHS)
        self._req_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._req_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._req_table.customContextMenuRequested.connect(self._show_req_context_menu)
        top_layout.addWidget(self._req_table)
        splitter.addWidget(top_widget)

        # Bottom: actual assigned resources
        bottom_group = QGroupBox("ASSIGNED RESOURCES")
        bottom_layout = QVBoxLayout(bottom_group)

        assign_btn_bar = QHBoxLayout()
        self._assigned_summary_label = QLabel("")
        self._assigned_summary_label.setStyleSheet(f"color:{get_palette().get('fg_muted').name()};")
        self._assign_btn = QPushButton("Assign Resource")
        self._remove_assign_btn = QPushButton("Remove Assigned")
        assign_btn_bar.addWidget(self._assigned_summary_label)
        assign_btn_bar.addStretch(1)
        assign_btn_bar.addWidget(self._assign_btn)
        bottom_layout.addLayout(assign_btn_bar)

        assign_columns = ["Kind", "Name", "Status", "Assigned"]
        self._assign_table = QTableWidget(0, len(assign_columns))
        self._assign_table.setHorizontalHeaderLabels(assign_columns)
        apply_statusboard_table_behavior(self._assign_table, stretch_last_section=False)
        self._apply_compact_table_header(self._assign_table, self._ASSIGN_COLUMN_WIDTHS)
        self._assign_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._assign_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._assign_table.customContextMenuRequested.connect(self._show_assign_context_menu)
        bottom_layout.addWidget(self._assign_table)
        splitter.addWidget(bottom_group)

        splitter.setSizes([300, 150])

        # Wire signals
        self._add_btn.clicked.connect(self._add_requirement)
        self._edit_btn.clicked.connect(self._edit_requirement)
        self._remove_btn.clicked.connect(self._remove_requirement)
        self._logistics_btn.clicked.connect(self._create_logistics_request)
        self._assign_btn.clicked.connect(self._assign_resource)
        self._remove_assign_btn.clicked.connect(self._remove_assigned)
        self._req_table.itemSelectionChanged.connect(self._on_req_selected)

        try:
            # subscribe_theme invokes the callback immediately with the
            # current theme, so this also performs the initial reload().
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            self.reload()

    # ------------------------------------------------------------------
    def _apply_compact_table_header(self, table: QTableWidget, widths: dict[int, int]) -> None:
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setMinimumSectionSize(36)
        header.setStyleSheet(
            "QHeaderView::section { "
            f"color:{get_palette().get('fg_muted').name()}; "
            "font-size:10px; font-weight:700; "
            "padding:3px 6px; "
            "}"
        )
        for column, width in widths.items():
            if column < table.columnCount():
                header.setSectionResizeMode(column, QHeaderView.Interactive)
                table.setColumnWidth(column, width)

    def _format_table_timestamp(self, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        normalized = text.replace("T", " ")
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            if "." in normalized:
                normalized = normalized.split(".", 1)[0]
            return normalized[:19]
        return f"{dt:%b} {dt.day}, {dt.year} {dt:%H:%M:%S}"

    def _assigned_resource_name(self, assignment) -> str:
        kind = str(assignment.resource_kind or "").lower()
        resource_id = str(assignment.resource_id or "")
        stored_name = str(assignment.display_name or "").strip()
        if kind == "vehicle":
            return resource_id or stored_name
        if kind == "equipment":
            if stored_name and resource_id and resource_id not in stored_name:
                return f"{stored_name} ({resource_id})"
            return stored_name or resource_id
        if stored_name:
            return stored_name
        return resource_id

    def _on_theme_changed(self, _name: str) -> None:
        self._apply_compact_table_header(self._req_table, self._REQ_COLUMN_WIDTHS)
        self._apply_compact_table_header(self._assign_table, self._ASSIGN_COLUMN_WIDTHS)
        self._assign_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.reload()

    def reload(self) -> None:
        """Reload requirements from the database."""
        try:
            repo = WorkAssignmentRepository(self._db_path)
            reqs = repo.list_resource_requirements(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Resources", f"Failed to load resources:\n{exc}")
            return
        self._req_table.setRowCount(0)
        total_required = 0
        total_assigned = 0
        total_gap = 0
        current_req_ids: set[int] = set()
        for req in reqs:
            row = self._req_table.rowCount()
            self._req_table.insertRow(row)
            if req.id is not None:
                current_req_ids.add(int(req.id))
            total_required += req.quantity_required
            total_assigned += req.quantity_assigned
            self._req_table.setItem(row, 0, QTableWidgetItem(req.resource_type_text))
            self._req_table.setItem(row, 1, QTableWidgetItem(req.capability_text))

            priority_item = QTableWidgetItem(req.priority)
            priority_brushes = wa_priority_colors().get(req.priority)
            if priority_brushes:
                priority_item.setBackground(priority_brushes["bg"])
                priority_item.setForeground(priority_brushes["fg"])
            self._req_table.setItem(row, 2, priority_item)
            self._req_table.setItem(row, 3, QTableWidgetItem(str(req.quantity_required)))
            self._req_table.setItem(row, 4, QTableWidgetItem(str(req.quantity_assigned)))
            self._req_table.setItem(row, 5, QTableWidgetItem(str(req.quantity_available)))
            gap = max(req.quantity_required - req.quantity_assigned, 0)
            total_gap += gap
            gap_item = QTableWidgetItem(str(gap))
            if gap > 0:
                gap_item.setForeground(get_palette().get("danger"))
            self._req_table.setItem(row, 6, gap_item)
            self._req_table.setItem(row, 7, QTableWidgetItem(req.notes))
            # Store the DB id in UserRole
            self._req_table.item(row, 0).setData(Qt.UserRole, req.id)
        self._summary_label.setText(
            f"{len(reqs)} requirements | {total_required} required | "
            f"{total_assigned} assigned | {total_gap} gap"
        )
        if self._selected_req_id is not None and self._selected_req_id in current_req_ids:
            self._reload_assigned(self._selected_req_id)
        else:
            self._selected_req_id = None
            self._assign_table.setRowCount(0)
            self._assigned_summary_label.setText("Select a requirement to view assigned resources")

    def _reload_assigned(self, requirement_id: int) -> None:
        """Reload the actual assigned resources for the selected requirement."""
        self._assign_table.setRowCount(0)
        self._assigned_summary_label.setText("Loading assigned resources...")
        try:
            repo = WorkAssignmentRepository(self._db_path)
            assigned = repo.list_assigned_resources_for_wa(self._work_assignment_id, requirement_id)
        except Exception:
            self._assigned_summary_label.setText("Assigned resources unavailable")
            return
        self._assigned_summary_label.setText(f"{len(assigned)} assigned to selected requirement")
        for a in assigned:
            row = self._assign_table.rowCount()
            self._assign_table.insertRow(row)
            self._assign_table.setItem(row, 0, QTableWidgetItem(a.resource_kind))
            self._assign_table.setItem(row, 1, QTableWidgetItem(self._assigned_resource_name(a)))
            self._assign_table.setItem(row, 2, QTableWidgetItem(a.status))
            self._assign_table.setItem(row, 3, QTableWidgetItem(self._format_table_timestamp(a.assigned_at)))
            self._assign_table.item(row, 0).setData(Qt.UserRole, a.id)

    def _show_req_context_menu(self, pos) -> None:
        item = self._req_table.itemAt(pos)
        if item is not None:
            self._req_table.setCurrentCell(item.row(), item.column())
        if self._req_table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Assign Resource", self._assign_resource)
        menu.addSeparator()
        menu.addAction("Edit Requirement", self._edit_requirement)
        menu.addAction("Remove Requirement", self._remove_requirement)
        menu.addSeparator()
        menu.addAction("Create Logistics Request", self._create_logistics_request)
        menu.exec(self._req_table.viewport().mapToGlobal(pos))

    def _show_assign_context_menu(self, pos) -> None:
        item = self._assign_table.itemAt(pos)
        if item is not None:
            self._assign_table.setCurrentCell(item.row(), item.column())
        if self._assign_table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction("Remove Assigned Resource", self._remove_assigned)
        menu.exec(self._assign_table.viewport().mapToGlobal(pos))

    def _current_req_id(self) -> int | None:
        row = self._req_table.currentRow()
        if row < 0:
            return None
        item = self._req_table.item(row, 0)
        if not item:
            return None
        try:
            return int(item.data(Qt.UserRole))
        except (TypeError, ValueError):
            return None

    def _on_req_selected(self) -> None:
        req_id = self._current_req_id()
        self._selected_req_id = req_id
        if req_id is not None:
            self._reload_assigned(req_id)
        else:
            self._assign_table.setRowCount(0)
            self._assigned_summary_label.setText("Select a requirement to view assigned resources")

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
            repo.update_resource_requirement_for_wa(self._work_assignment_id, req_id, data)
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
            repo.remove_resource_requirement_for_wa(self._work_assignment_id, req_id)
        except Exception as exc:
            QMessageBox.critical(self, "Remove", f"Failed to remove:\n{exc}")
            return
        self._selected_req_id = None
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

    def _create_logistics_request(self) -> None:
        req_id = self._current_req_id()
        if req_id is None:
            QMessageBox.information(self, "Create Logistics Request", "Select a requirement row first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            request_id = repo.create_logistics_request_from_requirement(self._work_assignment_id, req_id)
        except Exception as exc:
            QMessageBox.critical(self, "Create Logistics Request", f"Failed to create request:\n{exc}")
            return
        if request_id is None:
            QMessageBox.warning(self, "Create Logistics Request", "Failed to create the logistics request.")
            return
        self.reload()
        self.changed.emit()
        QMessageBox.information(self, "Create Logistics Request", f"Logistics request {request_id} created.")

    def _assign_resource(self) -> None:
        req_id = self._current_req_id()
        if req_id is None:
            QMessageBox.information(self, "Assign Resource", "Select a requirement row first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            reqs = repo.list_resource_requirements(self._work_assignment_id)
            requirement = next((r for r in reqs if r.id == req_id), None)
        except Exception:
            requirement = None
        dialog = _AssignResourceDialog(req_id, self._gap_service, requirement=requirement, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data.get("resource_id"):
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.assign_actual_resource_for_wa(
                self._work_assignment_id,
                req_id,
                data["resource_kind"],
                data["resource_id"],
                data.get("display_name", ""),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Assign Resource", f"Failed to assign:\n{exc}")
            return
        self._selected_req_id = req_id
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
        req_id = self._current_req_id() or self._selected_req_id
        if req_id is None:
            return
        if QMessageBox.question(
            self, "Remove", "Remove this resource assignment?"
        ) != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.remove_actual_resource_for_wa(self._work_assignment_id, req_id, assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Remove", f"Failed to remove:\n{exc}")
            return
        self._selected_req_id = req_id
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
    """Dialog for assigning a specific resource to a requirement.

    Shows resources matching the requirement's type/capability from the
    Resource Type Library (via ResourceGapService) so the user can fill
    the gap with a click, with a manual-entry fallback below for
    resources not tracked in the library.
    """

    _KINDS = ["personnel", "team", "vehicle", "equipment", "aircraft", "facility", "supply", "other"]

    @staticmethod
    def _resource_id_for(kind: str, item: dict) -> str:
        kind = kind.lower()
        if kind == "vehicle":
            return str(item.get("vehicle_id") or item.get("id") or item.get("resource_id") or "")
        if kind == "equipment":
            return str(
                item.get("equipment_id")
                or item.get("id")
                or item.get("equipment_record")
                or item.get("record_id")
                or item.get("serial_number")
                or item.get("resource_id")
                or ""
            )
        if kind == "aircraft":
            return str(item.get("aircraft_id") or item.get("id") or item.get("resource_id") or "")
        return str(item.get("id") or item.get("resource_id") or item.get("record_id") or "")

    @classmethod
    def _display_name_for(cls, kind: str, item: dict, resource_id: str) -> str:
        kind = kind.lower()
        if kind in {"personnel", "person", "team"}:
            return str(item.get("display_name") or item.get("name") or item.get("callsign") or resource_id)
        if kind == "aircraft":
            return str(item.get("callsign") or item.get("tail_number") or resource_id)
        if kind == "vehicle":
            return resource_id
        if kind == "equipment":
            name = str(item.get("name") or item.get("display_name") or "").strip()
            equipment_id = resource_id.strip()
            if name and equipment_id and equipment_id not in name:
                return f"{name} ({equipment_id})"
            return name or equipment_id
        return str(item.get("display_name") or item.get("name") or resource_id)

    def __init__(
        self,
        requirement_id: int,
        gap_service: ResourceGapService,
        requirement=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Resource")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        suggestions = []
        if requirement is not None:
            try:
                suggestions = gap_service.suggest_resources_for_requirement(requirement)
            except Exception:
                suggestions = []

        if suggestions:
            layout.addWidget(QLabel("Available resources matching this requirement:"))
            sugg_columns = ["Kind", "ID", "Name"]
            self._sugg_table = QTableWidget(0, len(sugg_columns))
            self._sugg_table.setHorizontalHeaderLabels(sugg_columns)
            apply_statusboard_table_behavior(self._sugg_table, stretch_last_section=True)
            self._sugg_table.setMaximumHeight(150)
            for s in suggestions:
                row = self._sugg_table.rowCount()
                self._sugg_table.insertRow(row)
                kind = str(s.get("resource_kind") or "")
                res_id = self._resource_id_for(kind, s)
                name = self._display_name_for(kind, s, res_id)
                self._sugg_table.setItem(row, 0, QTableWidgetItem(kind))
                self._sugg_table.setItem(row, 1, QTableWidgetItem(res_id))
                self._sugg_table.setItem(row, 2, QTableWidgetItem(name))
            self._sugg_table.itemSelectionChanged.connect(self._on_suggestion_selected)
            layout.addWidget(self._sugg_table)
        else:
            self._sugg_table = None

        layout.addWidget(QLabel("Assign:"))
        form = QFormLayout()
        layout.addLayout(form)

        self._kind_combo = QComboBox()
        self._kind_combo.addItems(self._KINDS)
        form.addRow("Resource Kind", self._kind_combo)

        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("Resource ID or name")
        form.addRow("Resource ID *", self._id_edit)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Name")
        form.addRow("Name", self._name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_suggestion_selected(self) -> None:
        if self._sugg_table is None:
            return
        row = self._sugg_table.currentRow()
        if row < 0:
            return
        kind = self._sugg_table.item(row, 0).text()
        res_id = self._sugg_table.item(row, 1).text()
        name = self._sugg_table.item(row, 2).text()
        idx = self._kind_combo.findText(kind)
        if idx >= 0:
            self._kind_combo.setCurrentIndex(idx)
        self._id_edit.setText(res_id)
        self._name_edit.setText(name)

    def get_data(self) -> dict:
        return {
            "resource_kind": self._kind_combo.currentText(),
            "resource_id": self._id_edit.text().strip(),
            "display_name": self._name_edit.text().strip(),
        }
