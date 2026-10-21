"""Create/edit dialog for a single Resource Package (Stage 3).

Follows the same tabbed-dialog convention as the Resource Type Library
editor: Overview / Personnel / Vehicles / Aircraft / Equipment / Requirements.
Membership (fixed/preferred/optional), required positions, and minimum
quantities can all be combined, and the package is always saveable
incomplete -- nothing here requires full staffing before Save is enabled.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.admin.resource_associations.widgets.resource_picker_dialog import ResourcePickerDialog
from modules.admin.resource_types.data.resource_type_repository import ApiResourceTypeRepository
from modules.admin.resource_types.widgets.resource_type_search_box import ResourceTypeSearchBox

from ..data.repository import ApiResourcePackageRepository
from ..models import (
    MEMBERSHIP_KINDS,
    MinimumQuantityRequirement,
    PackageResourceRef,
    RequiredPosition,
    ResourcePackage,
)

_RESOURCE_KIND_LABELS = {
    "personnel": "Personnel",
    "vehicle": "Vehicles",
    "aircraft": "Aircraft",
    "equipment": "Equipment",
}


class _AddPackageResourceDialog(QDialog):
    """Pick a resource of a given kind and choose its membership + role."""

    def __init__(self, resource_type: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.resource_type = resource_type
        self.setWindowTitle(f"Add {_RESOURCE_KIND_LABELS.get(resource_type, resource_type)}")
        self.resource_id: Optional[int] = None
        self.resource_label: str = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.pick_button = QPushButton("Select resource…")
        self.pick_button.clicked.connect(self._pick)
        form.addRow("Resource", self.pick_button)

        self.membership_combo = QComboBox()
        self.membership_combo.addItem("Fixed (specific resource)", "fixed")
        self.membership_combo.addItem("Preferred (normally assigned, substitutable)", "preferred")
        self.membership_combo.addItem("Optional", "optional")
        form.addRow("Membership", self.membership_combo)

        self.role_edit = QLineEdit()
        self.role_edit.setPlaceholderText("e.g. Team Leader, Driver (optional)")
        form.addRow("Role", self.role_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick(self) -> None:
        dialog = ResourcePickerDialog(self, allowed_kinds=(self.resource_type,))
        if dialog.exec() == QDialog.Accepted:
            self.resource_id = dialog.selected_resource_id
            self.resource_label = dialog.selected_label
            self.pick_button.setText(self.resource_label or str(self.resource_id))

    def _validate_then_accept(self) -> None:
        if self.resource_id is None:
            QMessageBox.warning(self, "Add Resource", "Select a resource first.")
            return
        self.accept()

    def to_ref(self) -> PackageResourceRef:
        return PackageResourceRef(
            resource_type=self.resource_type,
            resource_id=int(self.resource_id),
            membership=self.membership_combo.currentData(),
            role=self.role_edit.text().strip(),
            label=self.resource_label,
        )


class ResourcePackageEditorWindow(QDialog):
    def __init__(
        self,
        repository: ApiResourcePackageRepository,
        package: Optional[ResourcePackage] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.package = package
        self._resources: list[PackageResourceRef] = list(package.resources) if package else []
        self._required_positions: list[RequiredPosition] = list(package.required_positions) if package else []
        self._minimum_quantities: list[MinimumQuantityRequirement] = (
            list(package.minimum_quantities) if package else []
        )

        self.setWindowTitle("Edit Resource Package" if package else "New Resource Package")
        self.resize(900, 700)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_overview_tab(), "Overview")
        self._kind_tables: dict[str, QTableWidget] = {}
        for kind in ("personnel", "vehicle", "aircraft", "equipment"):
            self.tabs.addTab(self._build_kind_tab(kind), _RESOURCE_KIND_LABELS[kind])
        self.tabs.addTab(self._build_requirements_tab(), "Requirements")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

        for kind in self._kind_tables:
            self._refresh_kind_table(kind)

    # ------------------------------------------------------------------
    def _build_overview_tab(self) -> QWidget:
        record = self.package
        widget = QWidget()
        form = QFormLayout(widget)

        self.name_edit = QLineEdit(record.name if record else "")
        self.description_edit = QTextEdit(record.description if record else "")
        self.org_edit = QLineEdit(record.owning_organization if record else "")
        self.parent_unit_edit = QLineEdit(record.parent_org_unit or "" if record else "")
        self.designation_edit = QLineEdit(record.default_team_designation if record else "")
        self.linked_type_search = ResourceTypeSearchBox(ApiResourceTypeRepository(), self)
        if record and record.linked_resource_type_id:
            try:
                rt = ApiResourceTypeRepository().get_resource_type(record.linked_resource_type_id)
                if rt:
                    self.linked_type_search.set_value(rt.id, rt.resource_name or rt.name)
            except Exception:
                pass
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(record.is_active if record else True)
        self.notes_edit = QTextEdit(record.notes if record else "")

        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Owning organization", self.org_edit)
        form.addRow("Parent org unit", self.parent_unit_edit)
        form.addRow("Default team/unit designation", self.designation_edit)
        form.addRow("Linked Resource Type Library entry", self.linked_type_search)
        form.addRow("Active", self.active_check)
        form.addRow("Notes", self.notes_edit)
        return widget

    # ------------------------------------------------------------------
    def _build_kind_tab(self, resource_type: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Membership", "Resource", "Role"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        self._kind_tables[resource_type] = table

        actions = QHBoxLayout()
        add_button = QPushButton(f"Add {_RESOURCE_KIND_LABELS[resource_type]}…")
        remove_button = QPushButton("Remove selected")
        add_button.clicked.connect(lambda: self._add_resource(resource_type))
        remove_button.clicked.connect(lambda: self._remove_resource(resource_type))
        actions.addWidget(add_button)
        actions.addWidget(remove_button)
        actions.addStretch()

        layout.addWidget(table)
        layout.addLayout(actions)
        return widget

    def _add_resource(self, resource_type: str) -> None:
        dialog = _AddPackageResourceDialog(resource_type, self)
        if dialog.exec() != QDialog.Accepted:
            return
        ref = dialog.to_ref()
        if any(r.resource_type == ref.resource_type and r.resource_id == ref.resource_id for r in self._resources):
            QMessageBox.information(self, "Add Resource", "That resource is already in this package.")
            return
        self._resources.append(ref)
        self._refresh_kind_table(resource_type)

    def _remove_resource(self, resource_type: str) -> None:
        table = self._kind_tables[resource_type]
        row = table.currentRow()
        if row < 0:
            return
        item = table.item(row, 1)
        resource_id = item.data(Qt.UserRole) if item else None
        self._resources = [
            r for r in self._resources
            if not (r.resource_type == resource_type and r.resource_id == resource_id)
        ]
        self._refresh_kind_table(resource_type)

    def _refresh_kind_table(self, resource_type: str) -> None:
        table = self._kind_tables[resource_type]
        rows = [r for r in self._resources if r.resource_type == resource_type]
        table.setRowCount(len(rows))
        for i, ref in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(ref.membership.capitalize()))
            label_item = QTableWidgetItem(ref.label or str(ref.resource_id))
            label_item.setData(Qt.UserRole, ref.resource_id)
            table.setItem(i, 1, label_item)
            table.setItem(i, 2, QTableWidgetItem(ref.role))

    # ------------------------------------------------------------------
    def _build_requirements_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Required positions (role/qualification, no specific person named):"))
        self.positions_table = QTableWidget(0, 4)
        self.positions_table.setHorizontalHeaderLabels(["Role", "Qualification", "Quantity", "Notes"])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for p in self._required_positions:
            self._add_position_row(p)
        pos_actions = QHBoxLayout()
        add_pos = QPushButton("Add required position")
        remove_pos = QPushButton("Remove selected")
        add_pos.clicked.connect(self._prompt_add_position)
        remove_pos.clicked.connect(lambda: self._remove_table_row(self.positions_table))
        pos_actions.addWidget(add_pos)
        pos_actions.addWidget(remove_pos)
        pos_actions.addStretch()
        layout.addWidget(self.positions_table)
        layout.addLayout(pos_actions)

        layout.addWidget(QLabel("Minimum-quantity requirements (e.g. \"4 qualified personnel\", \"2 vehicles\"):"))
        self.min_qty_table = QTableWidget(0, 4)
        self.min_qty_table.setHorizontalHeaderLabels(["Description", "Resource Kind", "Qualification", "Minimum"])
        self.min_qty_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for m in self._minimum_quantities:
            self._add_min_qty_row(m)
        qty_actions = QHBoxLayout()
        add_qty = QPushButton("Add minimum-quantity requirement")
        remove_qty = QPushButton("Remove selected")
        add_qty.clicked.connect(self._prompt_add_min_qty)
        remove_qty.clicked.connect(lambda: self._remove_table_row(self.min_qty_table))
        qty_actions.addWidget(add_qty)
        qty_actions.addWidget(remove_qty)
        qty_actions.addStretch()
        layout.addWidget(self.min_qty_table)
        layout.addLayout(qty_actions)
        return widget

    def _remove_table_row(self, table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def _add_position_row(self, position: RequiredPosition) -> None:
        row = self.positions_table.rowCount()
        self.positions_table.insertRow(row)
        self.positions_table.setItem(row, 0, QTableWidgetItem(position.role))
        self.positions_table.setItem(row, 1, QTableWidgetItem(position.qualification))
        self.positions_table.setItem(row, 2, QTableWidgetItem(str(position.quantity)))
        self.positions_table.setItem(row, 3, QTableWidgetItem(position.notes))

    def _prompt_add_position(self) -> None:
        self._add_position_row(RequiredPosition(role="New Position", quantity=1))
        self.positions_table.editItem(self.positions_table.item(self.positions_table.rowCount() - 1, 0))

    def _add_min_qty_row(self, requirement: MinimumQuantityRequirement) -> None:
        row = self.min_qty_table.rowCount()
        self.min_qty_table.insertRow(row)
        self.min_qty_table.setItem(row, 0, QTableWidgetItem(requirement.description))
        self.min_qty_table.setItem(row, 1, QTableWidgetItem(requirement.resource_kind))
        self.min_qty_table.setItem(row, 2, QTableWidgetItem(requirement.qualification))
        self.min_qty_table.setItem(row, 3, QTableWidgetItem(str(requirement.minimum_count)))

    def _prompt_add_min_qty(self) -> None:
        self._add_min_qty_row(MinimumQuantityRequirement(description="New requirement", minimum_count=1))
        self.min_qty_table.editItem(self.min_qty_table.item(self.min_qty_table.rowCount() - 1, 0))

    # ------------------------------------------------------------------
    def _collect_positions(self) -> list[RequiredPosition]:
        positions = []
        for row in range(self.positions_table.rowCount()):
            role_item = self.positions_table.item(row, 0)
            if not role_item or not role_item.text().strip():
                continue
            qty_item = self.positions_table.item(row, 2)
            try:
                qty = int(qty_item.text()) if qty_item and qty_item.text().strip() else 1
            except ValueError:
                qty = 1
            positions.append(
                RequiredPosition(
                    role=role_item.text().strip(),
                    qualification=(self.positions_table.item(row, 1).text() if self.positions_table.item(row, 1) else ""),
                    quantity=qty,
                    notes=(self.positions_table.item(row, 3).text() if self.positions_table.item(row, 3) else ""),
                )
            )
        return positions

    def _collect_min_quantities(self) -> list[MinimumQuantityRequirement]:
        requirements = []
        for row in range(self.min_qty_table.rowCount()):
            desc_item = self.min_qty_table.item(row, 0)
            if not desc_item or not desc_item.text().strip():
                continue
            count_item = self.min_qty_table.item(row, 3)
            try:
                count = int(count_item.text()) if count_item and count_item.text().strip() else 1
            except ValueError:
                count = 1
            requirements.append(
                MinimumQuantityRequirement(
                    description=desc_item.text().strip(),
                    resource_kind=(self.min_qty_table.item(row, 1).text() if self.min_qty_table.item(row, 1) else ""),
                    qualification=(self.min_qty_table.item(row, 2).text() if self.min_qty_table.item(row, 2) else ""),
                    minimum_count=count,
                )
            )
        return requirements

    def to_model(self) -> ResourcePackage:
        return ResourcePackage(
            id=self.package.id if self.package else None,
            name=self.name_edit.text().strip(),
            description=self.description_edit.toPlainText(),
            owning_organization=self.org_edit.text().strip(),
            parent_org_unit=self.parent_unit_edit.text().strip() or None,
            linked_resource_type_id=self.linked_type_search.resource_type_id,
            default_team_designation=self.designation_edit.text().strip(),
            resources=list(self._resources),
            required_positions=self._collect_positions(),
            minimum_quantities=self._collect_min_quantities(),
            is_active=self.active_check.isChecked(),
            notes=self.notes_edit.toPlainText(),
        )

    def _validate_then_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Resource Package", "Name is required.")
            self.tabs.setCurrentIndex(0)
            return
        # Deliberately no "must be fully staffed" check -- packages are
        # always saveable incomplete/understaffed.
        self.accept()
