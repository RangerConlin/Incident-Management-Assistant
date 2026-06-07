"""QtWidgets editor dialog for Hazard Type Library records."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..data.hazard_type_repository import HazardTypeRepository
from ..models.hazard_type_models import (
    HAZARD_CATEGORIES,
    HAZARD_LIKELIHOODS,
    HAZARD_RISK_LEVELS,
    HAZARD_SEVERITIES,
    HAZARD_SOURCES,
    HazardMitigation,
    HazardPpeItem,
    HazardReference,
    HazardType,
    HazardTypeResourceDefault,
)

try:
    from modules.admin.resource_types.widgets import ResourceTypeSearchBox
except Exception:  # pragma: no cover - graceful runtime fallback
    ResourceTypeSearchBox = None  # type: ignore[assignment]


class MitigationEditorDialog(QDialog):
    """Small helper dialog for one mitigation row."""

    def __init__(
        self,
        mitigation: Optional[HazardMitigation] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Mitigation" if mitigation else "Add Mitigation")
        self.text_edit = QLineEdit(mitigation.mitigation_text if mitigation else "")
        self.category_edit = QLineEdit(mitigation.mitigation_category if mitigation else "")
        self.default_check = QCheckBox("Default mitigation")
        self.default_check.setChecked(mitigation.is_default if mitigation else False)
        self.sort_spin = QSpinBox()
        self.sort_spin.setRange(0, 9999)
        self.sort_spin.setValue(mitigation.sort_order if mitigation else 0)

        form = QFormLayout(self)
        form.addRow("Mitigation text", self.text_edit)
        form.addRow("Category", self.category_edit)
        form.addRow("Default", self.default_check)
        form.addRow("Sort order", self.sort_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def to_model(self) -> HazardMitigation:
        return HazardMitigation(
            hazard_type_id=0,
            mitigation_text=self.text_edit.text(),
            mitigation_category=self.category_edit.text(),
            is_default=self.default_check.isChecked(),
            sort_order=self.sort_spin.value(),
        )

    def _validate_then_accept(self) -> None:
        if not self.text_edit.text().strip():
            QMessageBox.warning(self, "Mitigation", "Mitigation text is required.")
            return
        self.accept()


class PpeEditorDialog(QDialog):
    """Small helper dialog for one PPE row."""

    def __init__(self, ppe_item: Optional[HazardPpeItem] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit PPE" if ppe_item else "Add PPE")
        self.text_edit = QLineEdit(ppe_item.ppe_text if ppe_item else "")
        self.default_check = QCheckBox("Default PPE")
        self.default_check.setChecked(ppe_item.is_default if ppe_item else False)
        self.sort_spin = QSpinBox()
        self.sort_spin.setRange(0, 9999)
        self.sort_spin.setValue(ppe_item.sort_order if ppe_item else 0)

        form = QFormLayout(self)
        form.addRow("PPE text", self.text_edit)
        form.addRow("Default", self.default_check)
        form.addRow("Sort order", self.sort_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def to_model(self) -> HazardPpeItem:
        return HazardPpeItem(
            hazard_type_id=0,
            ppe_text=self.text_edit.text(),
            is_default=self.default_check.isChecked(),
            sort_order=self.sort_spin.value(),
        )

    def _validate_then_accept(self) -> None:
        if not self.text_edit.text().strip():
            QMessageBox.warning(self, "PPE", "PPE text is required.")
            return
        self.accept()


class ReferenceEditorDialog(QDialog):
    """Small helper dialog for one reference row."""

    def __init__(
        self, reference: Optional[HazardReference] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Reference" if reference else "Add Reference")
        self.title_edit = QLineEdit(reference.title if reference else "")
        self.url_edit = QLineEdit(reference.url_or_path if reference else "")
        self.notes_edit = QTextEdit(reference.notes if reference else "")

        form = QFormLayout(self)
        form.addRow("Title", self.title_edit)
        form.addRow("URL or Path", self.url_edit)
        form.addRow("Notes", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def to_model(self) -> HazardReference:
        return HazardReference(
            hazard_type_id=0,
            title=self.title_edit.text(),
            url_or_path=self.url_edit.text(),
            notes=self.notes_edit.toPlainText(),
        )

    def _validate_then_accept(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Reference", "Title is required.")
            return
        self.accept()


class HazardTypeEditorWindow(QDialog):
    """Create/edit dialog for a single hazard type."""

    mitigation_headers = ["Mitigation Text", "Category", "Default", "Sort Order"]
    ppe_headers = ["PPE Item", "Default", "Sort Order"]
    resource_default_headers = ["Resource Type", "Category", "Notes"]
    reference_headers = ["Title", "URL or Path", "Notes"]

    def __init__(
        self,
        repository: HazardTypeRepository,
        hazard_type: Optional[HazardType] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.hazard_type = hazard_type
        self.setWindowTitle("Edit Hazard Type" if hazard_type else "New Hazard Type")
        self.resize(960, 760)

        self.toolbar = QToolBar(self)
        self.toolbar.addAction("Save", self._accept_save)
        self.toolbar.addAction("Save && Close", self._accept_save)
        self.toolbar.addAction("Cancel", self.reject)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_basic_tab(), "Basic Info")
        self.tabs.addTab(self._build_aliases_tab(), "Aliases")
        self.tabs.addTab(self._build_mitigations_tab(), "Mitigations / Control Measures")
        self.tabs.addTab(self._build_ppe_tab(), "PPE")
        self.tabs.addTab(self._build_resource_defaults_tab(), "Resource Type Defaults")
        self.tabs.addTab(self._build_references_tab(), "References")
        self.tabs.addTab(self._build_audit_tab(), "Audit / Metadata")

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.tabs)

    def _build_basic_tab(self) -> QWidget:
        record = self.hazard_type
        widget = QWidget()
        self.name_edit = QLineEdit(record.name if record else "")
        self.display_edit = QLineEdit(record.display_name if record else "")
        self.category_combo = QComboBox()
        self.category_combo.addItems(HAZARD_CATEGORIES)
        self.source_combo = QComboBox()
        self.source_combo.addItems(HAZARD_SOURCES)
        self.owner_edit = QLineEdit(record.owner_agency if record else "")
        self.risk_combo = QComboBox()
        self.risk_combo.addItems(HAZARD_RISK_LEVELS)
        self.likelihood_combo = QComboBox()
        self.likelihood_combo.addItems(HAZARD_LIKELIHOODS)
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(HAZARD_SEVERITIES)
        self.control_measure_edit = QTextEdit(record.default_control_measure if record else "")
        self.default_ppe_edit = QTextEdit(record.default_ppe if record else "")
        self.safety_message_edit = QTextEdit(record.default_safety_message if record else "")
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(record.is_active if record else True)
        self.description_edit = QTextEdit(record.description if record else "")
        self.notes_edit = QTextEdit(record.notes if record else "")

        if record:
            self.category_combo.setCurrentText(record.category)
            self.source_combo.setCurrentText(record.source)
            self.risk_combo.setCurrentText(record.default_risk_level)
            self.likelihood_combo.setCurrentText(record.default_likelihood)
            self.severity_combo.setCurrentText(record.default_severity)

        form = QFormLayout(widget)
        form.addRow("Name", self.name_edit)
        form.addRow("Display name", self.display_edit)
        form.addRow("Category", self.category_combo)
        form.addRow("Source", self.source_combo)
        form.addRow("Owner agency", self.owner_edit)
        form.addRow("Default risk level", self.risk_combo)
        form.addRow("Default likelihood", self.likelihood_combo)
        form.addRow("Default severity", self.severity_combo)
        form.addRow("Default control measure", self.control_measure_edit)
        form.addRow("Default PPE", self.default_ppe_edit)
        form.addRow("Default safety message", self.safety_message_edit)
        form.addRow("Active", self.active_check)
        form.addRow("Description", self.description_edit)
        form.addRow("Notes", self.notes_edit)
        return widget

    def _build_aliases_tab(self) -> QWidget:
        widget = QWidget()
        self.alias_list = QListWidget()
        for alias in self.hazard_type.aliases if self.hazard_type else []:
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
        layout.addWidget(QLabel("Aliases improve search without creating duplicate hazard types."))
        layout.addLayout(row)
        layout.addWidget(self.alias_list)
        layout.addWidget(remove_button)
        return widget

    def _build_mitigations_tab(self) -> QWidget:
        widget = QWidget()
        self.mitigation_table = QTableWidget(0, len(self.mitigation_headers))
        self.mitigation_table.setHorizontalHeaderLabels(self.mitigation_headers)
        self.mitigation_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mitigation_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mitigation_table.setSelectionMode(QTableWidget.SingleSelection)
        self.mitigation_table.doubleClicked.connect(self._edit_selected_mitigation)

        for mitigation in self.hazard_type.mitigations if self.hazard_type else []:
            self._add_mitigation_row(mitigation)

        add_button = QPushButton("Add mitigation")
        edit_button = QPushButton("Edit mitigation")
        remove_button = QPushButton("Remove mitigation")
        add_button.clicked.connect(self._add_mitigation)
        edit_button.clicked.connect(self._edit_selected_mitigation)
        remove_button.clicked.connect(lambda: self._remove_selected_table_row(self.mitigation_table))

        actions = QHBoxLayout()
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        layout = QVBoxLayout(widget)
        layout.addWidget(self.mitigation_table)
        layout.addLayout(actions)
        return widget

    def _build_ppe_tab(self) -> QWidget:
        widget = QWidget()
        summary_group = QGroupBox("Default PPE Summary")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.addWidget(QLabel("Use this summary for quick default fill-ins. The table below stores structured PPE rows for search and reuse."))
        self.default_ppe_preview = QTextEdit()
        self.default_ppe_preview.setReadOnly(True)
        self.default_ppe_preview.setPlainText(self.default_ppe_edit.toPlainText())
        self.default_ppe_edit.textChanged.connect(self._sync_default_ppe_preview)
        summary_layout.addWidget(self.default_ppe_preview)

        self.ppe_table = QTableWidget(0, len(self.ppe_headers))
        self.ppe_table.setHorizontalHeaderLabels(self.ppe_headers)
        self.ppe_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ppe_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ppe_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ppe_table.doubleClicked.connect(self._edit_selected_ppe)

        for ppe_item in self.hazard_type.ppe_items if self.hazard_type else []:
            self._add_ppe_row(ppe_item)

        add_button = QPushButton("Add PPE")
        edit_button = QPushButton("Edit PPE")
        remove_button = QPushButton("Remove PPE")
        mark_default_button = QPushButton("Mark selected default")
        add_button.clicked.connect(self._add_ppe)
        edit_button.clicked.connect(self._edit_selected_ppe)
        remove_button.clicked.connect(lambda: self._remove_selected_table_row(self.ppe_table))
        mark_default_button.clicked.connect(self._mark_selected_ppe_default)

        actions = QHBoxLayout()
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(remove_button)
        actions.addWidget(mark_default_button)
        actions.addStretch()
        layout = QVBoxLayout(widget)
        layout.addWidget(summary_group)
        layout.addWidget(self.ppe_table)
        layout.addLayout(actions)
        return widget

    def _sync_default_ppe_preview(self) -> None:
        if hasattr(self, "default_ppe_preview"):
            self.default_ppe_preview.setPlainText(self.default_ppe_edit.toPlainText())

    def _build_resource_defaults_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Attach this hazard as a default hazard for resource types."))

        if ResourceTypeSearchBox is not None:
            self.resource_type_search = ResourceTypeSearchBox(parent=self)
            search_row = QHBoxLayout()
            search_row.addWidget(self.resource_type_search, 1)
            add_button = QPushButton("Add resource type")
            add_button.clicked.connect(self._add_resource_default_from_search)
            search_row.addWidget(add_button)
            layout.addLayout(search_row)
            self.resource_default_fallback_edit = None
        else:
            self.resource_type_search = None
            self.resource_default_fallback_edit = QLineEdit()
            self.resource_default_fallback_edit.setPlaceholderText("Enter resource type ID")
            fallback_row = QHBoxLayout()
            fallback_row.addWidget(self.resource_default_fallback_edit, 1)
            add_button = QPushButton("Add resource type")
            add_button.clicked.connect(self._add_resource_default_from_fallback)
            fallback_row.addWidget(add_button)
            layout.addLayout(fallback_row)

        self.resource_default_notes_edit = QLineEdit()
        self.resource_default_notes_edit.setPlaceholderText("Optional notes for this default link")
        layout.addWidget(self.resource_default_notes_edit)

        self.resource_defaults_table = QTableWidget(0, len(self.resource_default_headers))
        self.resource_defaults_table.setHorizontalHeaderLabels(self.resource_default_headers)
        self.resource_defaults_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.resource_defaults_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.resource_defaults_table.setSelectionMode(QTableWidget.SingleSelection)

        for default in self.hazard_type.resource_defaults if self.hazard_type else []:
            self._add_resource_default_row(default)

        remove_button = QPushButton("Remove resource type")
        remove_button.clicked.connect(lambda: self._remove_selected_table_row(self.resource_defaults_table))
        layout.addWidget(self.resource_defaults_table)
        layout.addWidget(remove_button)
        return widget

    def _build_references_tab(self) -> QWidget:
        widget = QWidget()
        self.references_table = QTableWidget(0, len(self.reference_headers))
        self.references_table.setHorizontalHeaderLabels(self.reference_headers)
        self.references_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.references_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.references_table.setSelectionMode(QTableWidget.SingleSelection)
        self.references_table.doubleClicked.connect(self._edit_selected_reference)

        for reference in self.hazard_type.references if self.hazard_type else []:
            self._add_reference_row(reference)

        add_button = QPushButton("Add reference")
        edit_button = QPushButton("Edit reference")
        remove_button = QPushButton("Remove reference")
        add_button.clicked.connect(self._add_reference)
        edit_button.clicked.connect(self._edit_selected_reference)
        remove_button.clicked.connect(lambda: self._remove_selected_table_row(self.references_table))

        actions = QHBoxLayout()
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(remove_button)
        actions.addStretch()
        layout = QVBoxLayout(widget)
        layout.addWidget(self.references_table)
        layout.addLayout(actions)
        return widget

    def _build_audit_tab(self) -> QWidget:
        record = self.hazard_type
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

    def _add_mitigation(self) -> None:
        dialog = MitigationEditorDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._add_mitigation_row(dialog.to_model())

    def _edit_selected_mitigation(self) -> None:
        row = self.mitigation_table.currentRow()
        if row < 0:
            return
        current = self._mitigation_from_row(row)
        dialog = MitigationEditorDialog(current, self)
        if dialog.exec() == QDialog.Accepted:
            self._set_mitigation_row(row, dialog.to_model())

    def _add_mitigation_row(self, mitigation: HazardMitigation) -> None:
        row = self.mitigation_table.rowCount()
        self.mitigation_table.insertRow(row)
        self._set_mitigation_row(row, mitigation)

    def _set_mitigation_row(self, row: int, mitigation: HazardMitigation) -> None:
        text_item = QTableWidgetItem(mitigation.mitigation_text)
        text_item.setData(Qt.UserRole, mitigation.id)
        self.mitigation_table.setItem(row, 0, text_item)
        self.mitigation_table.setItem(row, 1, QTableWidgetItem(mitigation.mitigation_category))
        self.mitigation_table.setItem(row, 2, QTableWidgetItem("Yes" if mitigation.is_default else "No"))
        self.mitigation_table.setItem(row, 3, QTableWidgetItem(str(mitigation.sort_order)))

    def _mitigation_from_row(self, row: int) -> HazardMitigation:
        return HazardMitigation(
            hazard_type_id=self.hazard_type.id if self.hazard_type else 0,
            mitigation_text=self.mitigation_table.item(row, 0).text(),
            mitigation_category=self.mitigation_table.item(row, 1).text(),
            is_default=self.mitigation_table.item(row, 2).text() == "Yes",
            sort_order=int(self.mitigation_table.item(row, 3).text() or 0),
            id=self.mitigation_table.item(row, 0).data(Qt.UserRole),
        )

    def _add_ppe(self) -> None:
        dialog = PpeEditorDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._add_ppe_row(dialog.to_model())

    def _edit_selected_ppe(self) -> None:
        row = self.ppe_table.currentRow()
        if row < 0:
            return
        current = self._ppe_from_row(row)
        dialog = PpeEditorDialog(current, self)
        if dialog.exec() == QDialog.Accepted:
            self._set_ppe_row(row, dialog.to_model())

    def _add_ppe_row(self, ppe_item: HazardPpeItem) -> None:
        row = self.ppe_table.rowCount()
        self.ppe_table.insertRow(row)
        self._set_ppe_row(row, ppe_item)

    def _set_ppe_row(self, row: int, ppe_item: HazardPpeItem) -> None:
        text_item = QTableWidgetItem(ppe_item.ppe_text)
        text_item.setData(Qt.UserRole, ppe_item.id)
        self.ppe_table.setItem(row, 0, text_item)
        self.ppe_table.setItem(row, 1, QTableWidgetItem("Yes" if ppe_item.is_default else "No"))
        self.ppe_table.setItem(row, 2, QTableWidgetItem(str(ppe_item.sort_order)))

    def _ppe_from_row(self, row: int) -> HazardPpeItem:
        return HazardPpeItem(
            hazard_type_id=self.hazard_type.id if self.hazard_type else 0,
            ppe_text=self.ppe_table.item(row, 0).text(),
            is_default=self.ppe_table.item(row, 1).text() == "Yes",
            sort_order=int(self.ppe_table.item(row, 2).text() or 0),
            id=self.ppe_table.item(row, 0).data(Qt.UserRole),
        )

    def _mark_selected_ppe_default(self) -> None:
        row = self.ppe_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "PPE", "Select a PPE row first.")
            return
        for index in range(self.ppe_table.rowCount()):
            self.ppe_table.setItem(index, 1, QTableWidgetItem("Yes" if index == row else "No"))

    def _add_resource_default_from_search(self) -> None:
        if self.resource_type_search is None:
            return
        resource_type_id = self.resource_type_search.resource_type_id
        if resource_type_id is None:
            QMessageBox.warning(
                self,
                "Resource Type Defaults",
                "Select an existing resource type from the library.",
            )
            return
        resource_type_text = self.resource_type_search.resource_type_text
        self._append_resource_default(
            HazardTypeResourceDefault(
                hazard_type_id=self.hazard_type.id if self.hazard_type else 0,
                resource_type_id=int(resource_type_id),
                notes=self.resource_default_notes_edit.text(),
                resource_type_name=resource_type_text,
            )
        )
        self.resource_type_search.clear()
        self.resource_default_notes_edit.clear()

    def _add_resource_default_from_fallback(self) -> None:
        if self.resource_default_fallback_edit is None:
            return
        text = self.resource_default_fallback_edit.text().strip()
        if not text.isdigit():
            QMessageBox.warning(
                self,
                "Resource Type Defaults",
                "Enter a numeric resource type ID.",
            )
            return
        self._append_resource_default(
            HazardTypeResourceDefault(
                hazard_type_id=self.hazard_type.id if self.hazard_type else 0,
                resource_type_id=int(text),
                notes=self.resource_default_notes_edit.text(),
                resource_type_name=text,
            )
        )
        self.resource_default_fallback_edit.clear()
        self.resource_default_notes_edit.clear()

    def _append_resource_default(self, default: HazardTypeResourceDefault) -> None:
        existing_ids = {
            int(self.resource_defaults_table.item(row, 0).data(Qt.UserRole))
            for row in range(self.resource_defaults_table.rowCount())
            if self.resource_defaults_table.item(row, 0) is not None
        }
        if default.resource_type_id in existing_ids:
            QMessageBox.information(
                self,
                "Resource Type Defaults",
                "That resource type is already linked.",
            )
            return
        self._add_resource_default_row(default)

    def _add_resource_default_row(self, default: HazardTypeResourceDefault) -> None:
        row = self.resource_defaults_table.rowCount()
        self.resource_defaults_table.insertRow(row)
        name_item = QTableWidgetItem(default.resource_type_name or str(default.resource_type_id))
        name_item.setData(Qt.UserRole, int(default.resource_type_id))
        self.resource_defaults_table.setItem(row, 0, name_item)
        self.resource_defaults_table.setItem(row, 1, QTableWidgetItem(default.resource_type_category))
        self.resource_defaults_table.setItem(row, 2, QTableWidgetItem(default.notes))

    def _add_reference(self) -> None:
        dialog = ReferenceEditorDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._add_reference_row(dialog.to_model())

    def _edit_selected_reference(self) -> None:
        row = self.references_table.currentRow()
        if row < 0:
            return
        current = self._reference_from_row(row)
        dialog = ReferenceEditorDialog(current, self)
        if dialog.exec() == QDialog.Accepted:
            self._set_reference_row(row, dialog.to_model())

    def _add_reference_row(self, reference: HazardReference) -> None:
        row = self.references_table.rowCount()
        self.references_table.insertRow(row)
        self._set_reference_row(row, reference)

    def _set_reference_row(self, row: int, reference: HazardReference) -> None:
        title_item = QTableWidgetItem(reference.title)
        title_item.setData(Qt.UserRole, reference.id)
        self.references_table.setItem(row, 0, title_item)
        self.references_table.setItem(row, 1, QTableWidgetItem(reference.url_or_path))
        self.references_table.setItem(row, 2, QTableWidgetItem(reference.notes))

    def _reference_from_row(self, row: int) -> HazardReference:
        return HazardReference(
            hazard_type_id=self.hazard_type.id if self.hazard_type else 0,
            title=self.references_table.item(row, 0).text(),
            url_or_path=self.references_table.item(row, 1).text(),
            notes=self.references_table.item(row, 2).text(),
            id=self.references_table.item(row, 0).data(Qt.UserRole),
        )

    def _remove_selected_table_row(self, table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def to_model(self) -> HazardType:
        aliases = [self.alias_list.item(index).text() for index in range(self.alias_list.count())]
        mitigations = [self._mitigation_from_row(row) for row in range(self.mitigation_table.rowCount())]
        ppe_items = [self._ppe_from_row(row) for row in range(self.ppe_table.rowCount())]
        references = [self._reference_from_row(row) for row in range(self.references_table.rowCount())]
        resource_defaults = [
            HazardTypeResourceDefault(
                hazard_type_id=self.hazard_type.id if self.hazard_type else 0,
                resource_type_id=int(self.resource_defaults_table.item(row, 0).data(Qt.UserRole)),
                resource_type_name=self.resource_defaults_table.item(row, 0).text(),
                resource_type_category=self.resource_defaults_table.item(row, 1).text(),
                notes=self.resource_defaults_table.item(row, 2).text(),
            )
            for row in range(self.resource_defaults_table.rowCount())
        ]
        return HazardType(
            id=self.hazard_type.id if self.hazard_type else None,
            name=self.name_edit.text(),
            display_name=self.display_edit.text(),
            category=self.category_combo.currentText(),
            source=self.source_combo.currentText(),
            owner_agency=self.owner_edit.text(),
            description=self.description_edit.toPlainText(),
            default_risk_level=self.risk_combo.currentText(),
            default_likelihood=self.likelihood_combo.currentText(),
            default_severity=self.severity_combo.currentText(),
            default_control_measure=self.control_measure_edit.toPlainText(),
            default_ppe=self.default_ppe_edit.toPlainText(),
            default_safety_message=self.safety_message_edit.toPlainText(),
            is_active=self.active_check.isChecked(),
            notes=self.notes_edit.toPlainText(),
            aliases=aliases,
            mitigations=mitigations,
            ppe_items=ppe_items,
            references=references,
            resource_defaults=resource_defaults,
            created_at=self.hazard_type.created_at if self.hazard_type else "",
            updated_at=self.hazard_type.updated_at if self.hazard_type else "",
            created_by=self.hazard_type.created_by if self.hazard_type else "",
            updated_by=self.hazard_type.updated_by if self.hazard_type else "",
        )

    def _accept_save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Hazard Type", "Name is required.")
            self.tabs.setCurrentIndex(0)
            return
        if not self.category_combo.currentText().strip():
            QMessageBox.warning(self, "Hazard Type", "Category is required.")
            self.tabs.setCurrentIndex(0)
            return
        if not self.source_combo.currentText().strip():
            QMessageBox.warning(self, "Hazard Type", "Source is required.")
            self.tabs.setCurrentIndex(0)
            return
        if self.risk_combo.currentText() not in HAZARD_RISK_LEVELS:
            QMessageBox.warning(self, "Hazard Type", "Default risk level must be a supported value.")
            self.tabs.setCurrentIndex(0)
            return
        if self.likelihood_combo.currentText() not in HAZARD_LIKELIHOODS:
            QMessageBox.warning(self, "Hazard Type", "Default likelihood must be a supported value.")
            self.tabs.setCurrentIndex(0)
            return
        if self.severity_combo.currentText() not in HAZARD_SEVERITIES:
            QMessageBox.warning(self, "Hazard Type", "Default severity must be a supported value.")
            self.tabs.setCurrentIndex(0)
            return
        for row in range(self.mitigation_table.rowCount()):
            if not self.mitigation_table.item(row, 0).text().strip():
                QMessageBox.warning(self, "Hazard Type", "Empty mitigation text cannot be saved.")
                self.tabs.setCurrentIndex(2)
                return
        for row in range(self.ppe_table.rowCount()):
            if not self.ppe_table.item(row, 0).text().strip():
                QMessageBox.warning(self, "Hazard Type", "Empty PPE text cannot be saved.")
                self.tabs.setCurrentIndex(3)
                return
        self.accept()
