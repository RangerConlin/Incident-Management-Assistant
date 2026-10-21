"""QtWidgets editor dialog for Resource Type Library records."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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

from ..data.resource_type_repository import ApiResourceTypeRepository
from ..models.resource_type_models import (
    FemaNimsMapping,
    RESOURCE_CATEGORIES,
    RESOURCE_SOURCES,
    ResourceType,
    ResourceTypeComponent,
    ResourceTypeSpec,
)
from ..widgets.resource_type_search_box import ResourceTypeSearchBox
from .capability_manager_window import CapabilityManagerWindow


class _EquipmentRequirementPickerDialog(QDialog):
    """Small modal: pick one existing Resource Type Library record to use
    as an equipment requirement (required or recommended)."""

    def __init__(self, repository: ApiResourceTypeRepository, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Equipment Resource Type")
        self.resource_search = ResourceTypeSearchBox(repository, self)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Resource type", self.resource_search)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_then_accept(self) -> None:
        if self.resource_search.resource_type_id is None:
            QMessageBox.warning(self, "Equipment Requirement", "Select an existing resource type.")
            return
        self.accept()


class ComponentEditorDialog(QDialog):
    """Dialog for adding one component row to a kit/cache resource type."""

    def __init__(
        self,
        repository: ApiResourceTypeRepository,
        parent_resource_type_id: Optional[int],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.parent_resource_type_id = parent_resource_type_id
        self.setWindowTitle("Add Component")

        self.resource_search = ResourceTypeSearchBox(repository, self)
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0.01, 999999.0)
        self.quantity_spin.setDecimals(2)
        self.quantity_spin.setValue(1.0)
        self.required_check = QCheckBox("Required component")
        self.required_check.setChecked(True)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional component notes")

        form = QFormLayout()
        form.addRow("Component resource type", self.resource_search)
        form.addRow("Quantity", self.quantity_spin)
        form.addRow("Required", self.required_check)
        form.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def to_component(self) -> ResourceTypeComponent:
        """Return the chosen component after validation has succeeded."""

        return ResourceTypeComponent(
            parent_resource_type_id=self.parent_resource_type_id or 0,
            component_resource_type_id=int(self.resource_search.resource_type_id or 0),
            quantity=float(self.quantity_spin.value()),
            required=self.required_check.isChecked(),
            notes=self.notes_edit.toPlainText(),
            component_name=self.resource_search.resource_type_text,
        )

    def _validate_then_accept(self) -> None:
        component_id = self.resource_search.resource_type_id
        if component_id is None:
            QMessageBox.warning(
                self,
                "Component",
                "Select an existing resource type for kit/cache components. Free text is allowed in other workflows, but components must reference library records.",
            )
            return
        if self.parent_resource_type_id and int(component_id) == self.parent_resource_type_id:
            QMessageBox.warning(
                self, "Component", "A resource type cannot contain itself as a component."
            )
            return
        if self.parent_resource_type_id and self.repository.would_create_cycle(
            self.parent_resource_type_id, int(component_id)
        ):
            QMessageBox.warning(
                self, "Component", "This component would create a circular kit/cache reference."
            )
            return
        self.accept()


class ResourceTypeEditorWindow(QDialog):
    """Create/edit dialog for a single resource type.

    The dialog gathers data only.  The main library window calls the repository
    to save, which keeps database logic out of UI code.
    """

    component_headers = ["Component Resource Type", "Quantity", "Required", "Notes"]

    def __init__(
        self,
        repository: ApiResourceTypeRepository,
        resource_type: Optional[ResourceType] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.resource_type = resource_type
        self._assigned_capability_ids: set[int] = set(resource_type.capability_ids if resource_type else [])
        self.setWindowTitle("Edit Resource Type" if resource_type else "New Resource Type")
        self.resize(860, 680)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_basic_tab(), "Basic Info")
        self.tabs.addTab(self._build_requirements_tab(), "Classification && Requirements")
        self.tabs.addTab(self._build_aliases_tab(), "Aliases")
        self.tabs.addTab(self._build_capabilities_tab(), "Capabilities")
        self.tabs.addTab(self._build_components_tab(), "Components / Kit Contents")
        self.tabs.addTab(self._build_fema_tab(), "FEMA/NIMS Mapping")
        self.tabs.addTab(self._build_audit_tab(), "Audit / Metadata")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
        self._refresh_capability_lists()
        self._update_component_tab_state()

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------
    def _build_basic_tab(self) -> QWidget:
        record = self.resource_type
        widget = QWidget()
        self.name_edit = QLineEdit(record.name if record else "")
        self.display_edit = QLineEdit(record.resource_name if record else "")
        self.category_combo = QComboBox()
        self.category_combo.addItems(RESOURCE_CATEGORIES)
        self.source_combo = QComboBox()
        self.source_combo.addItems(RESOURCE_SOURCES)
        self.owner_edit = QLineEdit(record.owner_agency if record else "")
        self.description_edit = QTextEdit(record.description if record else "")
        self.default_unit_edit = QLineEdit(record.default_unit if record else "each")
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0, 999999.0)
        self.quantity_spin.setDecimals(2)
        self.quantity_spin.setValue(record.typical_quantity if record else 1.0)
        self.team_size_spin = QSpinBox()
        self.team_size_spin.setRange(0, 10000)
        self.team_size_spin.setSpecialValueText("Not set")
        self.team_size_spin.setValue(record.typical_team_size or 0 if record else 0)
        self.kit_check = QCheckBox("Is kit/cache")
        self.kit_check.setChecked(record.is_kit_cache if record else False)
        self.consumable_check = QCheckBox("Is consumable")
        self.consumable_check.setChecked(record.is_consumable if record else False)
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(record.is_active if record else True)
        self.notes_edit = QTextEdit(record.notes if record else "")

        if record:
            self.category_combo.setCurrentText(record.category)
            self.source_combo.setCurrentText(record.source)

        self.kit_check.toggled.connect(self._update_component_tab_state)

        form = QFormLayout(widget)
        form.addRow("Name", self.name_edit)
        form.addRow("Planning display name", self.display_edit)
        form.addRow("Category", self.category_combo)
        form.addRow("Source", self.source_combo)
        form.addRow("Owner agency", self.owner_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Default unit", self.default_unit_edit)
        form.addRow("Typical quantity", self.quantity_spin)
        form.addRow("Typical team size", self.team_size_spin)
        form.addRow("Is kit/cache", self.kit_check)
        form.addRow("Is consumable", self.consumable_check)
        form.addRow("Active", self.active_check)
        form.addRow("Notes", self.notes_edit)
        return widget

    def _build_requirements_tab(self) -> QWidget:
        """Extensible classification + composition-requirement fields.

        Everything here is structured-but-generic (free text kind, a
        name/value/unit spec table, plain qualification strings, and
        resource-type-id equipment references) so a new kind of resource
        can be fully described without any code change.
        """
        record = self.resource_type
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.kind_combo = QComboBox()
        self.kind_combo.setEditable(True)
        self.kind_combo.setInsertPolicy(QComboBox.NoInsert)
        try:
            self.kind_combo.addItems(self.repository.list_kinds())
        except Exception:
            pass
        if record and record.kind:
            self.kind_combo.setCurrentText(record.kind)
        else:
            self.kind_combo.setCurrentText("")
        form.addRow("Resource Kind", self.kind_combo)

        self.min_personnel_spin = QSpinBox()
        self.min_personnel_spin.setRange(0, 10000)
        self.min_personnel_spin.setSpecialValueText("Not set")
        self.min_personnel_spin.setValue((record.min_personnel or 0) if record else 0)
        form.addRow("Minimum staffing (personnel)", self.min_personnel_spin)
        layout.addLayout(form)

        # Required qualifications ------------------------------------------------
        layout.addWidget(QLabel("Required qualifications (name or code a member must hold):"))
        self.qualifications_list = QListWidget()
        for q in (record.required_qualifications if record else []):
            self.qualifications_list.addItem(q)
        qual_row = QHBoxLayout()
        self.qualification_edit = QLineEdit()
        self.qualification_edit.setPlaceholderText("e.g. Ground Team Member, EMT-B")
        add_qual_btn = QPushButton("Add")
        remove_qual_btn = QPushButton("Remove selected")
        add_qual_btn.clicked.connect(self._add_qualification)
        remove_qual_btn.clicked.connect(
            lambda: self.qualifications_list.takeItem(self.qualifications_list.currentRow())
        )
        qual_row.addWidget(self.qualification_edit, 1)
        qual_row.addWidget(add_qual_btn)
        layout.addLayout(qual_row)
        layout.addWidget(self.qualifications_list)
        layout.addWidget(remove_qual_btn)

        # Required / recommended equipment ---------------------------------------
        equip_box = QGroupBox("Equipment")
        equip_layout = QVBoxLayout(equip_box)
        equip_layout.addWidget(QLabel("Required equipment (resource types this kind cannot operate without):"))
        self.required_equipment_list = QListWidget()
        for rt_id in (record.required_equipment_ids if record else []):
            self._add_equipment_requirement_row(self.required_equipment_list, rt_id)
        req_row = QHBoxLayout()
        req_add_btn = QPushButton("Add required equipment")
        req_remove_btn = QPushButton("Remove selected")
        req_add_btn.clicked.connect(lambda: self._prompt_add_equipment_requirement(self.required_equipment_list))
        req_remove_btn.clicked.connect(
            lambda: self.required_equipment_list.takeItem(self.required_equipment_list.currentRow())
        )
        req_row.addWidget(req_add_btn)
        req_row.addWidget(req_remove_btn)
        req_row.addStretch()
        equip_layout.addWidget(self.required_equipment_list)
        equip_layout.addLayout(req_row)

        equip_layout.addWidget(QLabel("Recommended / optional equipment:"))
        self.recommended_equipment_list = QListWidget()
        for rt_id in (record.recommended_equipment_ids if record else []):
            self._add_equipment_requirement_row(self.recommended_equipment_list, rt_id)
        rec_row = QHBoxLayout()
        rec_add_btn = QPushButton("Add recommended equipment")
        rec_remove_btn = QPushButton("Remove selected")
        rec_add_btn.clicked.connect(lambda: self._prompt_add_equipment_requirement(self.recommended_equipment_list))
        rec_remove_btn.clicked.connect(
            lambda: self.recommended_equipment_list.takeItem(self.recommended_equipment_list.currentRow())
        )
        rec_row.addWidget(rec_add_btn)
        rec_row.addWidget(rec_remove_btn)
        rec_row.addStretch()
        equip_layout.addWidget(self.recommended_equipment_list)
        equip_layout.addLayout(rec_row)
        layout.addWidget(equip_box)

        # Technical specs ----------------------------------------------------------
        layout.addWidget(QLabel("Technical specifications (name / value / unit / notes):"))
        self.spec_headers = ["Name", "Value", "Unit", "Notes"]
        self.spec_table = QTableWidget(0, len(self.spec_headers))
        self.spec_table.setHorizontalHeaderLabels(self.spec_headers)
        self.spec_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.spec_table.setSelectionBehavior(QTableWidget.SelectRows)
        for spec in (record.technical_specs if record else []):
            self._add_spec_row(spec)
        spec_actions = QHBoxLayout()
        add_spec_btn = QPushButton("Add spec row")
        remove_spec_btn = QPushButton("Remove selected row")
        add_spec_btn.clicked.connect(lambda: self._add_spec_row(ResourceTypeSpec(name="")))
        remove_spec_btn.clicked.connect(self._remove_selected_spec_row)
        spec_actions.addWidget(add_spec_btn)
        spec_actions.addWidget(remove_spec_btn)
        spec_actions.addStretch()
        layout.addWidget(self.spec_table)
        layout.addLayout(spec_actions)

        layout.addWidget(QLabel("Other composition requirements:"))
        self.composition_notes_edit = QTextEdit(record.composition_notes if record else "")
        layout.addWidget(self.composition_notes_edit)
        return widget

    def _add_qualification(self) -> None:
        text = self.qualification_edit.text().strip()
        if not text:
            return
        existing = {self.qualifications_list.item(i).text().lower() for i in range(self.qualifications_list.count())}
        if text.lower() in existing:
            self.qualification_edit.clear()
            return
        self.qualifications_list.addItem(text)
        self.qualification_edit.clear()

    def _add_equipment_requirement_row(self, target: QListWidget, resource_type_id: int) -> None:
        label = str(resource_type_id)
        try:
            rt = self.repository.get_resource_type(int(resource_type_id))
            if rt:
                label = rt.resource_name or rt.name
        except Exception:
            pass
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, int(resource_type_id))
        target.addItem(item)

    def _prompt_add_equipment_requirement(self, target: QListWidget) -> None:
        dialog = _EquipmentRequirementPickerDialog(self.repository, self)
        if dialog.exec() != QDialog.Accepted:
            return
        rt_id = int(dialog.resource_search.resource_type_id)
        existing_ids = {target.item(i).data(Qt.UserRole) for i in range(target.count())}
        if rt_id in existing_ids:
            return
        self._add_equipment_requirement_row(target, rt_id)

    def _add_spec_row(self, spec: ResourceTypeSpec) -> None:
        row = self.spec_table.rowCount()
        self.spec_table.insertRow(row)
        self.spec_table.setItem(row, 0, QTableWidgetItem(spec.name))
        self.spec_table.setItem(row, 1, QTableWidgetItem(spec.value))
        self.spec_table.setItem(row, 2, QTableWidgetItem(spec.unit))
        self.spec_table.setItem(row, 3, QTableWidgetItem(spec.notes))

    def _remove_selected_spec_row(self) -> None:
        row = self.spec_table.currentRow()
        if row >= 0:
            self.spec_table.removeRow(row)

    def _requirement_tab_values(self) -> dict[str, Any]:
        qualifications = [
            self.qualifications_list.item(i).text() for i in range(self.qualifications_list.count())
        ]
        required_ids = [
            int(self.required_equipment_list.item(i).data(Qt.UserRole))
            for i in range(self.required_equipment_list.count())
        ]
        recommended_ids = [
            int(self.recommended_equipment_list.item(i).data(Qt.UserRole))
            for i in range(self.recommended_equipment_list.count())
        ]
        specs: list[ResourceTypeSpec] = []
        for row in range(self.spec_table.rowCount()):
            name_item = self.spec_table.item(row, 0)
            if not name_item or not name_item.text().strip():
                continue
            specs.append(
                ResourceTypeSpec(
                    name=name_item.text().strip(),
                    value=(self.spec_table.item(row, 1).text() if self.spec_table.item(row, 1) else ""),
                    unit=(self.spec_table.item(row, 2).text() if self.spec_table.item(row, 2) else ""),
                    notes=(self.spec_table.item(row, 3).text() if self.spec_table.item(row, 3) else ""),
                )
            )
        return {
            "kind": self.kind_combo.currentText().strip(),
            "min_personnel": self.min_personnel_spin.value() or None,
            "required_qualifications": qualifications,
            "required_equipment_ids": required_ids,
            "recommended_equipment_ids": recommended_ids,
            "technical_specs": specs,
            "composition_notes": self.composition_notes_edit.toPlainText(),
        }

    def _build_aliases_tab(self) -> QWidget:
        widget = QWidget()
        self.alias_list = QListWidget()
        for alias in self.resource_type.aliases if self.resource_type else []:
            self.alias_list.addItem(alias)
        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("Add another name users might search for")
        add_button = QPushButton("Add alias")
        remove_button = QPushButton("Remove selected alias")
        add_button.clicked.connect(self._add_alias)
        remove_button.clicked.connect(lambda: self.alias_list.takeItem(self.alias_list.currentRow()))

        row = QHBoxLayout()
        row.addWidget(self.alias_edit, 1)
        row.addWidget(add_button)
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Aliases improve search without creating duplicate resource types."))
        layout.addLayout(row)
        layout.addWidget(self.alias_list)
        layout.addWidget(remove_button)
        return widget

    def _build_capabilities_tab(self) -> QWidget:
        widget = QWidget()
        self.capability_search = QLineEdit()
        self.capability_search.setPlaceholderText("Search capability tags...")
        self.available_capability_list = QListWidget()
        self.assigned_capability_list = QListWidget()
        add_button = QPushButton("Add →")
        remove_button = QPushButton("← Remove")
        manager_button = QPushButton("Open Capability Manager")
        self.capability_search.textChanged.connect(self._refresh_capability_lists)
        add_button.clicked.connect(self._assign_selected_capability)
        remove_button.clicked.connect(self._remove_selected_capability)
        manager_button.clicked.connect(self._open_capability_manager)

        lists = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Available capabilities"))
        left.addWidget(self.available_capability_list)
        middle = QVBoxLayout()
        middle.addStretch()
        middle.addWidget(add_button)
        middle.addWidget(remove_button)
        middle.addStretch()
        right = QVBoxLayout()
        right.addWidget(QLabel("Assigned to this resource type"))
        right.addWidget(self.assigned_capability_list)
        lists.addLayout(left, 1)
        lists.addLayout(middle)
        lists.addLayout(right, 1)

        layout = QVBoxLayout(widget)
        layout.addWidget(self.capability_search)
        layout.addLayout(lists)
        layout.addWidget(manager_button)
        return widget

    def _build_components_tab(self) -> QWidget:
        widget = QWidget()
        self.components_note = QLabel(
            "Use this tab for kits/caches such as a radio cache. Components must be existing resource types."
        )
        self.component_table = QTableWidget(0, len(self.component_headers))
        self.component_table.setHorizontalHeaderLabels(self.component_headers)
        self.component_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.component_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.component_table.setSelectionMode(QTableWidget.SingleSelection)

        for component in self.resource_type.components if self.resource_type else []:
            self._add_component_row(component)

        self.add_component_button = QPushButton("Add component")
        self.remove_component_button = QPushButton("Remove selected component")
        self.add_component_button.clicked.connect(self._prompt_add_component)
        self.remove_component_button.clicked.connect(self._remove_selected_component)

        actions = QHBoxLayout()
        actions.addWidget(self.add_component_button)
        actions.addWidget(self.remove_component_button)
        actions.addStretch()
        layout = QVBoxLayout(widget)
        layout.addWidget(self.components_note)
        layout.addWidget(self.component_table)
        layout.addLayout(actions)
        return widget

    def _build_fema_tab(self) -> QWidget:
        mapping = self.resource_type.fema_mappings[0] if self.resource_type and self.resource_type.fema_mappings else None
        widget = QWidget()
        self.fema_name_edit = QLineEdit(mapping.nims_name if mapping else "")
        self.fema_category_edit = QLineEdit(mapping.discipline if mapping else "")
        self.fema_type_edit = QLineEdit(mapping.type_code if mapping else "")
        self.fema_kind_edit = QLineEdit(mapping.kind if mapping else "")
        self.fema_reference_edit = QLineEdit(mapping.reference_url if mapping else "")
        self.fema_notes_edit = QTextEdit(mapping.notes if mapping else "")

        form = QFormLayout(widget)
        form.addRow("FEMA/NIMS resource name", self.fema_name_edit)
        form.addRow("FEMA/NIMS category", self.fema_category_edit)
        form.addRow("FEMA/NIMS type", self.fema_type_edit)
        form.addRow("FEMA/NIMS kind", self.fema_kind_edit)
        form.addRow("Reference URL or notes", self.fema_reference_edit)
        form.addRow("Mapping notes", self.fema_notes_edit)
        return widget

    def _build_audit_tab(self) -> QWidget:
        record = self.resource_type
        widget = QWidget()
        form = QFormLayout(widget)
        for label, value in (
            ("Created at", record.created_at if record else "Saved after creation"),
            ("Updated at", record.updated_at if record else "Saved after creation"),
            ("Created by", record.created_by if record else ""),
            ("Updated by", record.updated_by if record else ""),
        ):
            edit = QLineEdit(value)
            edit.setReadOnly(True)
            form.addRow(label, edit)
        return widget

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------
    def _add_alias(self) -> None:
        alias = self.alias_edit.text().strip()
        if not alias:
            QMessageBox.information(self, "Aliases", "Enter an alias first.")
            return
        existing = {self.alias_list.item(index).text().lower() for index in range(self.alias_list.count())}
        if alias.lower() in existing:
            QMessageBox.information(self, "Aliases", "That alias is already listed.")
            return
        self.alias_list.addItem(alias)
        self.alias_edit.clear()

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def _refresh_capability_lists(self) -> None:
        if not hasattr(self, "available_capability_list"):
            return
        search_text = self.capability_search.text() if hasattr(self, "capability_search") else ""
        self.available_capability_list.clear()
        self.assigned_capability_list.clear()
        for capability in self.repository.list_capabilities(search_text, include_inactive=True):
            item = QListWidgetItem(f"{capability['name']} ({capability['category']})")
            item.setData(Qt.UserRole, capability)
            if int(capability["id"]) in self._assigned_capability_ids:
                self.assigned_capability_list.addItem(item)
            elif capability.get("is_active"):
                self.available_capability_list.addItem(item)

    def _assign_selected_capability(self) -> None:
        item = self.available_capability_list.currentItem()
        if not item:
            return
        self._assigned_capability_ids.add(int(item.data(Qt.UserRole)["id"]))
        self._refresh_capability_lists()

    def _remove_selected_capability(self) -> None:
        item = self.assigned_capability_list.currentItem()
        if not item:
            return
        self._assigned_capability_ids.discard(int(item.data(Qt.UserRole)["id"]))
        self._refresh_capability_lists()

    def _open_capability_manager(self) -> None:
        CapabilityManagerWindow(self.repository, self).exec()
        self._refresh_capability_lists()

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------
    def _update_component_tab_state(self) -> None:
        if not hasattr(self, "component_table"):
            return
        enabled = self.kit_check.isChecked()
        self.component_table.setEnabled(enabled)
        self.add_component_button.setEnabled(enabled)
        self.remove_component_button.setEnabled(enabled)
        if enabled:
            self.components_note.setText("Add the resource types contained in this kit/cache.")
        else:
            self.components_note.setText("Check 'Is kit/cache' on Basic Info to enable component editing.")

    def _prompt_add_component(self) -> None:
        dialog = ComponentEditorDialog(
            self.repository,
            self.resource_type.id if self.resource_type else None,
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            component = dialog.to_component()
            existing_ids = {
                int(self.component_table.item(row, 0).data(Qt.UserRole))
                for row in range(self.component_table.rowCount())
                if self.component_table.item(row, 0)
            }
            if component.component_resource_type_id in existing_ids:
                QMessageBox.information(self, "Components", "That component is already listed.")
                return
            self._add_component_row(component)

    def _add_component_row(self, component: ResourceTypeComponent) -> None:
        row = self.component_table.rowCount()
        self.component_table.insertRow(row)
        name_item = QTableWidgetItem(component.component_name or str(component.component_resource_type_id))
        name_item.setData(Qt.UserRole, int(component.component_resource_type_id))
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.component_table.setItem(row, 0, name_item)
        self.component_table.setItem(row, 1, QTableWidgetItem(str(component.quantity)))
        required_item = QTableWidgetItem("Yes" if component.required else "No")
        required_item.setFlags(required_item.flags() & ~Qt.ItemIsEditable)
        self.component_table.setItem(row, 2, required_item)
        self.component_table.setItem(row, 3, QTableWidgetItem(component.notes))

    def _remove_selected_component(self) -> None:
        row = self.component_table.currentRow()
        if row >= 0:
            self.component_table.removeRow(row)

    # ------------------------------------------------------------------
    # Conversion and validation
    # ------------------------------------------------------------------
    def to_model(self) -> ResourceType:
        """Convert all tabs into a ResourceType dataclass."""

        aliases = [self.alias_list.item(index).text() for index in range(self.alias_list.count())]
        mappings: list[FemaNimsMapping] = []
        if any(
            field.text().strip()
            for field in (
                self.fema_name_edit,
                self.fema_category_edit,
                self.fema_type_edit,
                self.fema_kind_edit,
                self.fema_reference_edit,
            )
        ) or self.fema_notes_edit.toPlainText().strip():
            mappings.append(
                FemaNimsMapping(
                    resource_type_id=self.resource_type.id if self.resource_type else 0,
                    nims_name=self.fema_name_edit.text(),
                    discipline=self.fema_category_edit.text(),
                    type_code=self.fema_type_edit.text(),
                    kind=self.fema_kind_edit.text(),
                    reference_url=self.fema_reference_edit.text(),
                    notes=self.fema_notes_edit.toPlainText(),
                )
            )
        requirements = self._requirement_tab_values()
        return ResourceType(
            id=self.resource_type.id if self.resource_type else None,
            name=self.name_edit.text(),
            resource_name=self.display_edit.text(),
            category=self.category_combo.currentText(),
            source=self.source_combo.currentText(),
            owner_agency=self.owner_edit.text(),
            description=self.description_edit.toPlainText(),
            default_unit=self.default_unit_edit.text(),
            typical_quantity=float(self.quantity_spin.value()),
            typical_team_size=self.team_size_spin.value() or None,
            is_kit_cache=self.kit_check.isChecked(),
            is_consumable=self.consumable_check.isChecked(),
            is_active=self.active_check.isChecked(),
            notes=self.notes_edit.toPlainText(),
            aliases=aliases,
            capability_ids=sorted(self._assigned_capability_ids),
            fema_mappings=mappings,
            created_at=self.resource_type.created_at if self.resource_type else "",
            updated_at=self.resource_type.updated_at if self.resource_type else "",
            created_by=self.resource_type.created_by if self.resource_type else "",
            updated_by=self.resource_type.updated_by if self.resource_type else "",
            kind=requirements["kind"],
            technical_specs=requirements["technical_specs"],
            min_personnel=requirements["min_personnel"],
            required_qualifications=requirements["required_qualifications"],
            required_equipment_ids=requirements["required_equipment_ids"],
            recommended_equipment_ids=requirements["recommended_equipment_ids"],
            composition_notes=requirements["composition_notes"],
        )

    def components(self) -> list[ResourceTypeComponent]:
        """Return component rows currently shown in the kit/cache table."""

        if not self.kit_check.isChecked():
            return []
        components: list[ResourceTypeComponent] = []
        parent_id = self.resource_type.id if self.resource_type else 0
        for row in range(self.component_table.rowCount()):
            name_item = self.component_table.item(row, 0)
            quantity_item = self.component_table.item(row, 1)
            if not name_item or not quantity_item:
                continue
            quantity = float(quantity_item.text())
            components.append(
                ResourceTypeComponent(
                    parent_resource_type_id=parent_id,
                    component_resource_type_id=int(name_item.data(Qt.UserRole)),
                    component_name=name_item.text(),
                    quantity=quantity,
                    required=(self.component_table.item(row, 2).text() == "Yes"),
                    notes=self.component_table.item(row, 3).text() if self.component_table.item(row, 3) else "",
                )
            )
        return components

    def _validate_then_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Resource Type", "Name is required.")
            self.tabs.setCurrentIndex(0)
            return
        if not self.category_combo.currentText().strip():
            QMessageBox.warning(self, "Resource Type", "Category is required.")
            self.tabs.setCurrentIndex(0)
            return
        if not self.source_combo.currentText().strip():
            QMessageBox.warning(self, "Resource Type", "Source is required.")
            self.tabs.setCurrentIndex(0)
            return
        try:
            for component in self.components():
                if component.quantity <= 0:
                    raise ValueError("Component quantity must be greater than zero.")
                if self.resource_type and component.component_resource_type_id == self.resource_type.id:
                    raise ValueError("A resource type cannot contain itself as a component.")
                if self.resource_type and self.repository.would_create_cycle(
                    self.resource_type.id, component.component_resource_type_id
                ):
                    raise ValueError("A component would create a circular kit/cache reference.")
        except ValueError as exc:
            QMessageBox.warning(self, "Resource Type", str(exc))
            self.tabs.setCurrentIndex(3)
            return
        self.accept()
