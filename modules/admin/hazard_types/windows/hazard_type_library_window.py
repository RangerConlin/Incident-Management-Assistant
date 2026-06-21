"""QtWidgets admin window for the Hazard Type Library and Safety Analysis Templates."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..data.hazard_type_repository import ApiHazardTypeRepository, ApiSafetyTemplateRepository
from ..models.hazard_type_models import (
    HAZARD_CATEGORIES,
    HAZARD_RISK_LEVELS,
    HAZARD_SOURCES,
    SAFETY_SCENARIO_TYPES,
    SAFETY_TARGET_FORMS,
    SafetyAnalysisTemplate,
    SafetyTemplateHazardEntry,
)
from .hazard_type_editor_window import HazardTypeEditorWindow
from utils.itemview_delegates import RowOutlineSelectionDelegate

try:
    from modules.admin.hazard_types.widgets import HazardTypeSearchBox
except Exception:
    HazardTypeSearchBox = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Hazard Types tab — table model
# ---------------------------------------------------------------------------

class HazardTypeTableModel(QAbstractTableModel):
    """Table model for the main Hazard Type Library browser."""

    headers = [
        "Name",
        "Display Name",
        "Category",
        "Source",
        "Default Risk",
        "Mitigations",
        "Active",
        "Updated At",
    ]
    keys = [
        "name",
        "display_name",
        "category",
        "source",
        "default_risk_level",
        "mitigation_count",
        "is_active",
        "updated_at",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._records: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        record = self._records[index.row()]
        key = self.keys[index.column()]
        if role == Qt.DisplayRole:
            if key == "is_active":
                return "Yes" if record.get(key) else "No"
            return record.get(key, "")
        return None

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def record_at(self, row: int) -> Optional[dict[str, Any]]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


# ---------------------------------------------------------------------------
# Safety Templates tab — table model + editor dialog
# ---------------------------------------------------------------------------

class TemplateTableModel(QAbstractTableModel):
    headers = ["Name", "Scenario Type", "Target Forms", "Hazards", "Active", "Updated At"]
    keys = ["name", "scenario_type", "target_forms_display", "hazard_count", "is_active", "updated_at"]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._records: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        record = self._records[index.row()]
        key = self.keys[index.column()]
        if role == Qt.DisplayRole:
            if key == "is_active":
                return "Yes" if record.get("is_active") else "No"
            if key == "target_forms_display":
                return ", ".join(record.get("target_forms") or [])
            if key == "hazard_count":
                return str(len(record.get("hazard_entries") or []))
            return str(record.get(key, "") or "")
        return None

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def record_at(self, row: int) -> Optional[dict[str, Any]]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


class TemplateEditDialog(QDialog):
    """Create/edit dialog for a single Safety Analysis Template."""

    def __init__(
        self,
        hazard_repo: ApiHazardTypeRepository,
        template: Optional[SafetyAnalysisTemplate] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._hazard_repo = hazard_repo
        self._template = template
        self.setWindowTitle("Edit Template" if template else "New Template")
        self.resize(780, 600)

        # Basic fields
        self.name_edit = QLineEdit(template.name if template else "")
        self.name_edit.setPlaceholderText("e.g. Wildfire Ground Operations")
        self.description_edit = QTextEdit(template.description if template else "")
        self.description_edit.setFixedHeight(60)
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(SAFETY_SCENARIO_TYPES)
        if template:
            self.scenario_combo.setCurrentText(template.scenario_type)
        self.notes_edit = QTextEdit(template.notes if template else "")
        self.notes_edit.setFixedHeight(50)
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(template.is_active if template else True)

        # Target forms checkboxes
        forms_widget = QWidget()
        forms_layout = QHBoxLayout(forms_widget)
        forms_layout.setContentsMargins(0, 0, 0, 0)
        self._form_checks: dict[str, QCheckBox] = {}
        selected_forms = set(template.target_forms if template else [])
        for form in SAFETY_TARGET_FORMS:
            cb = QCheckBox(form)
            cb.setChecked(form in selected_forms)
            self._form_checks[form] = cb
            forms_layout.addWidget(cb)
        forms_layout.addStretch()

        # Hazard entries list
        self._hazard_list = QListWidget()
        self._hazard_list.setSelectionMode(QListWidget.SingleSelection)
        if template:
            for entry in sorted(template.hazard_entries, key=lambda e: e.sort_order):
                self._add_entry_item(entry)

        # Hazard search bar
        if HazardTypeSearchBox is not None:
            self._hazard_search = HazardTypeSearchBox(parent=self)
        else:
            self._hazard_search = None  # type: ignore[assignment]

        self._override_notes_edit = QLineEdit()
        self._override_notes_edit.setPlaceholderText("Override notes for this entry (optional)")

        add_hazard_btn = QPushButton("Add Hazard")
        add_hazard_btn.clicked.connect(self._add_hazard)
        remove_hazard_btn = QPushButton("Remove Selected")
        remove_hazard_btn.clicked.connect(self._remove_selected_hazard)
        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self._move_up)
        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self._move_down)

        hazard_actions = QHBoxLayout()
        hazard_actions.addWidget(add_hazard_btn)
        hazard_actions.addWidget(remove_hazard_btn)
        hazard_actions.addWidget(move_up_btn)
        hazard_actions.addWidget(move_down_btn)
        hazard_actions.addStretch()

        search_row = QHBoxLayout()
        if self._hazard_search is not None:
            search_row.addWidget(QLabel("Add hazard:"))
            search_row.addWidget(self._hazard_search, 1)
        search_row.addWidget(self._override_notes_edit, 1)

        hazards_section = QVBoxLayout()
        hazards_section.addWidget(QLabel("Hazards in this template (ordered):"))
        hazards_section.addLayout(search_row)
        hazards_section.addWidget(self._hazard_list, 1)
        hazards_section.addLayout(hazard_actions)

        form = QFormLayout()
        form.addRow("Name *", self.name_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Scenario type", self.scenario_combo)
        form.addRow("Target forms", forms_widget)
        form.addRow("Notes", self.notes_edit)
        form.addRow("", self.active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(hazards_section)
        layout.addWidget(buttons)

    def _add_entry_item(self, entry: SafetyTemplateHazardEntry) -> None:
        label = entry.hazard_name or f"Hazard #{entry.hazard_type_id}"
        if entry.hazard_category:
            label += f"  [{entry.hazard_category}]"
        if entry.default_risk_level:
            label += f"  Risk: {entry.default_risk_level}"
        if entry.override_notes:
            label += f"  — {entry.override_notes}"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, {
            "hazard_type_id": entry.hazard_type_id,
            "override_notes": entry.override_notes,
            "hazard_name": entry.hazard_name,
            "hazard_category": entry.hazard_category,
            "default_risk_level": entry.default_risk_level,
        })
        self._hazard_list.addItem(item)

    def _add_hazard(self) -> None:
        if self._hazard_search is not None:
            hid = self._hazard_search.hazard_type_id
            if hid is None:
                QMessageBox.information(self, "Add Hazard", "Search and select a hazard first.")
                return
            htext = self._hazard_search.hazard_type_text
            # check duplicate
            for i in range(self._hazard_list.count()):
                d = self._hazard_list.item(i).data(Qt.UserRole)
                if d and d.get("hazard_type_id") == int(hid):
                    QMessageBox.information(self, "Add Hazard", "That hazard is already in this template.")
                    return
            # fetch category and risk from repo
            hazard = self._hazard_repo.get_hazard_type(int(hid))
            entry = SafetyTemplateHazardEntry(
                hazard_type_id=int(hid),
                sort_order=self._hazard_list.count(),
                override_notes=self._override_notes_edit.text().strip(),
                hazard_name=htext,
                hazard_category=hazard.category if hazard else "",
                default_risk_level=hazard.default_risk_level if hazard else "",
            )
            self._add_entry_item(entry)
            self._hazard_search.clear()
            self._override_notes_edit.clear()
        else:
            QMessageBox.information(self, "Add Hazard", "Hazard search widget not available.")

    def _remove_selected_hazard(self) -> None:
        row = self._hazard_list.currentRow()
        if row >= 0:
            self._hazard_list.takeItem(row)

    def _move_up(self) -> None:
        row = self._hazard_list.currentRow()
        if row > 0:
            item = self._hazard_list.takeItem(row)
            self._hazard_list.insertItem(row - 1, item)
            self._hazard_list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self._hazard_list.currentRow()
        if 0 <= row < self._hazard_list.count() - 1:
            item = self._hazard_list.takeItem(row)
            self._hazard_list.insertItem(row + 1, item)
            self._hazard_list.setCurrentRow(row + 1)

    def _validate_then_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Template", "Name is required.")
            return
        self.accept()

    def to_api_doc(self, existing_id: Optional[int] = None) -> dict[str, Any]:
        entries = []
        for i in range(self._hazard_list.count()):
            d = self._hazard_list.item(i).data(Qt.UserRole) or {}
            entries.append({
                "hazard_type_id": d.get("hazard_type_id", 0),
                "sort_order": i,
                "override_notes": d.get("override_notes", ""),
                "hazard_name": d.get("hazard_name", ""),
                "hazard_category": d.get("hazard_category", ""),
                "default_risk_level": d.get("default_risk_level", ""),
            })
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText(),
            "scenario_type": self.scenario_combo.currentText(),
            "target_forms": [f for f, cb in self._form_checks.items() if cb.isChecked()],
            "hazard_entries": entries,
            "is_active": self.active_check.isChecked(),
            "notes": self.notes_edit.toPlainText(),
        }


# ---------------------------------------------------------------------------
# Main library window
# ---------------------------------------------------------------------------

class HazardTypeLibraryWindow(QWidget):
    """Tabbed admin window: Hazard Types + Safety Analysis Templates."""

    def __init__(
        self,
        repository: Optional[ApiHazardTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, Qt.Window)
        self._hazard_repo = repository or ApiHazardTypeRepository()
        self._template_repo = ApiSafetyTemplateRepository()
        self.setWindowTitle("Safety Analysis Library")
        self.resize(1200, 760)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_hazard_types_tab(), "Hazard Types")
        self._tabs.addTab(self._build_templates_tab(), "Scenario Templates")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._tabs)

        self.refresh_hazard_types()
        self.refresh_templates()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_templates_tab(self) -> None:
        self._tabs.setCurrentIndex(1)

    def show_hazard_types_tab(self) -> None:
        self._tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Hazard Types tab
    # ------------------------------------------------------------------

    def _build_hazard_types_tab(self) -> QWidget:
        tab = QWidget()

        self.ht_search_edit = QLineEdit()
        self.ht_search_edit.setPlaceholderText("Search name, aliases, mitigations, PPE, notes...")
        self.ht_category_filter = QComboBox()
        self.ht_category_filter.addItems(("All",) + HAZARD_CATEGORIES)
        self.ht_source_filter = QComboBox()
        self.ht_source_filter.addItems(("All",) + HAZARD_SOURCES)
        self.ht_risk_filter = QComboBox()
        self.ht_risk_filter.addItems(("All",) + HAZARD_RISK_LEVELS)
        self.ht_active_filter = QComboBox()
        self.ht_active_filter.addItems(("Active", "Inactive", "All"))

        self.ht_table_model = HazardTypeTableModel(self)
        self.ht_proxy = QSortFilterProxyModel(self)
        self.ht_proxy.setSourceModel(self.ht_table_model)
        self.ht_table = QTableView()
        self.ht_table.setModel(self.ht_proxy)
        self.ht_table.setSelectionBehavior(QTableView.SelectRows)
        self.ht_table.setSelectionMode(QTableView.SingleSelection)
        self.ht_table.setSortingEnabled(True)
        self.ht_table.sortByColumn(0, Qt.AscendingOrder)
        self.ht_table.setAlternatingRowColors(False)
        self.ht_table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self.ht_table.setItemDelegate(RowOutlineSelectionDelegate(self.ht_table, QColor("#FFFFFF")))
        header = self.ht_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.ht_table.doubleClicked.connect(self._ht_edit_selected)

        self.ht_preview = QTextEdit()
        self.ht_preview.setReadOnly(True)
        self.ht_preview.setPlaceholderText("Select a hazard type to preview.")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.ht_table)
        splitter.addWidget(self.ht_preview)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)

        self.ht_toggle_btn = QPushButton("Deactivate")
        new_btn = QPushButton("New")
        edit_btn = QPushButton("Edit")
        clone_btn = QPushButton("Clone")
        refresh_btn = QPushButton("Refresh")

        new_btn.clicked.connect(self._ht_new)
        edit_btn.clicked.connect(self._ht_edit_selected)
        clone_btn.clicked.connect(self._ht_clone_selected)
        self.ht_toggle_btn.clicked.connect(self._ht_toggle_active)
        refresh_btn.clicked.connect(self.refresh_hazard_types)

        self.ht_search_edit.textChanged.connect(self.refresh_hazard_types)
        self.ht_category_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_source_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_risk_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_active_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_table.selectionModel().selectionChanged.connect(self._ht_on_selection)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.ht_search_edit, 2)
        filters.addWidget(QLabel("Category"))
        filters.addWidget(self.ht_category_filter)
        filters.addWidget(QLabel("Source"))
        filters.addWidget(self.ht_source_filter)
        filters.addWidget(QLabel("Risk"))
        filters.addWidget(self.ht_risk_filter)
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self.ht_active_filter)

        import_btn = QPushButton("Import CSV...")
        import_btn.clicked.connect(self._ht_import_csv)
        export_btn = QPushButton("Export CSV...")
        export_btn.clicked.connect(self._ht_export_csv)

        actions = QHBoxLayout()
        actions.addWidget(new_btn)
        actions.addWidget(edit_btn)
        actions.addWidget(clone_btn)
        actions.addWidget(self.ht_toggle_btn)
        actions.addWidget(refresh_btn)
        actions.addWidget(import_btn)
        actions.addWidget(export_btn)
        actions.addStretch()

        layout = QVBoxLayout(tab)
        layout.addLayout(filters)
        layout.addWidget(splitter, 1)
        layout.addLayout(actions)
        return tab

    def _ht_import_csv(self) -> None:
        from utils.edit_menu_io import HazardTypesIO, do_import_csv
        do_import_csv(HazardTypesIO(), self)
        self.refresh_hazard_types()

    def _ht_export_csv(self) -> None:
        from utils.edit_menu_io import HazardTypesIO, do_export_csv
        do_export_csv(HazardTypesIO(), self)

    def refresh_hazard_types(self) -> None:
        records = self._hazard_repo.list_hazard_types({
            "search_text": self.ht_search_edit.text(),
            "category": self.ht_category_filter.currentText(),
            "source": self.ht_source_filter.currentText(),
            "risk_level": self.ht_risk_filter.currentText(),
            "active_filter": self.ht_active_filter.currentText(),
        })
        self.ht_table_model.set_records(records)
        self._ht_on_selection()

    def _ht_selected_record(self) -> Optional[dict[str, Any]]:
        idx = self.ht_table.currentIndex()
        if not idx.isValid():
            return None
        return self.ht_table_model.record_at(self.ht_proxy.mapToSource(idx).row())

    def _ht_on_selection(self) -> None:
        record = self._ht_selected_record()
        self.ht_toggle_btn.setText("Reactivate" if record and not record.get("is_active") else "Deactivate")
        if record:
            try:
                ht = self._hazard_repo.get_hazard_type(int(record["id"]))
            except Exception:
                ht = None
            if ht:
                mitigations = "\n".join(f"- {m.mitigation_text}" for m in ht.mitigations) or "-"
                refs = "\n".join(
                    f"- {r.title}: {r.url_or_path}".rstrip(": ") for r in ht.references
                ) or "-"
                self.ht_preview.setPlainText("\n".join([
                    f"Description:\n{ht.description or '-'}",
                    "",
                    f"Default control measure:\n{ht.default_control_measure or '-'}",
                    "",
                    f"Default PPE:\n{ht.default_ppe or '-'}",
                    "",
                    f"Safety message:\n{ht.default_safety_message or '-'}",
                    "",
                    f"Mitigations:\n{mitigations}",
                    "",
                    f"References:\n{refs}",
                ]))
                return
        self.ht_preview.clear()

    def _ht_new(self) -> None:
        dialog = HazardTypeEditorWindow(self._hazard_repo, parent=self)
        if dialog.exec() == HazardTypeEditorWindow.Accepted:
            self._ht_save(dialog)

    def _ht_edit_selected(self) -> None:
        record = self._ht_selected_record()
        if not record:
            QMessageBox.information(self, "Hazard Type Library", "Select a hazard type to edit.")
            return
        ht = self._hazard_repo.get_hazard_type(int(record["id"]))
        if ht is None:
            QMessageBox.warning(self, "Hazard Type Library", "The selected record no longer exists.")
            self.refresh_hazard_types()
            return
        dialog = HazardTypeEditorWindow(self._hazard_repo, ht, self)
        if dialog.exec() == HazardTypeEditorWindow.Accepted:
            self._ht_save(dialog)

    def _ht_save(self, dialog: HazardTypeEditorWindow) -> None:
        try:
            ht = dialog.to_model()
            if ht.id is None:
                self._hazard_repo.create_hazard_type(ht)
            else:
                self._hazard_repo.update_hazard_type(ht.id, ht)
            self.refresh_hazard_types()
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))

    def _ht_clone_selected(self) -> None:
        record = self._ht_selected_record()
        if not record:
            QMessageBox.information(self, "Hazard Type Library", "Select a hazard type to clone.")
            return
        try:
            new_id = self._hazard_repo.clone_hazard_type(int(record["id"]))
            self.refresh_hazard_types()
            QMessageBox.information(self, "Hazard Type Library", f"Cloned. New ID: {new_id}")
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))

    def _ht_toggle_active(self) -> None:
        record = self._ht_selected_record()
        if not record:
            QMessageBox.information(self, "Hazard Type Library", "Select a hazard type first.")
            return
        if record.get("is_active"):
            self._hazard_repo.deactivate_hazard_type(int(record["id"]))
        else:
            self._hazard_repo.reactivate_hazard_type(int(record["id"]))
        self.refresh_hazard_types()

    # ------------------------------------------------------------------
    # Scenario Templates tab
    # ------------------------------------------------------------------

    def _build_templates_tab(self) -> QWidget:
        tab = QWidget()

        self.tpl_search_edit = QLineEdit()
        self.tpl_search_edit.setPlaceholderText("Search by name or description...")
        self.tpl_scenario_filter = QComboBox()
        self.tpl_scenario_filter.addItems(("All",) + SAFETY_SCENARIO_TYPES)
        self.tpl_active_filter = QComboBox()
        self.tpl_active_filter.addItems(("Active", "All", "Inactive"))

        self.tpl_table_model = TemplateTableModel(self)
        self.tpl_proxy = QSortFilterProxyModel(self)
        self.tpl_proxy.setSourceModel(self.tpl_table_model)
        self.tpl_table = QTableView()
        self.tpl_table.setModel(self.tpl_proxy)
        self.tpl_table.setSelectionBehavior(QTableView.SelectRows)
        self.tpl_table.setSelectionMode(QTableView.SingleSelection)
        self.tpl_table.setSortingEnabled(True)
        self.tpl_table.sortByColumn(0, Qt.AscendingOrder)
        self.tpl_table.setAlternatingRowColors(False)
        self.tpl_table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self.tpl_table.setItemDelegate(RowOutlineSelectionDelegate(self.tpl_table, QColor("#FFFFFF")))
        self.tpl_table.horizontalHeader().setStretchLastSection(True)
        self.tpl_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tpl_table.doubleClicked.connect(self._tpl_edit_selected)

        self.tpl_preview = QTextEdit()
        self.tpl_preview.setReadOnly(True)
        self.tpl_preview.setPlaceholderText("Select a template to preview its hazard entries.")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.tpl_table)
        splitter.addWidget(self.tpl_preview)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)

        self.tpl_toggle_btn = QPushButton("Deactivate")
        new_btn = QPushButton("New")
        edit_btn = QPushButton("Edit")
        clone_btn = QPushButton("Clone")
        delete_btn = QPushButton("Delete")
        refresh_btn = QPushButton("Refresh")

        new_btn.clicked.connect(self._tpl_new)
        edit_btn.clicked.connect(self._tpl_edit_selected)
        clone_btn.clicked.connect(self._tpl_clone_selected)
        delete_btn.clicked.connect(self._tpl_delete_selected)
        self.tpl_toggle_btn.clicked.connect(self._tpl_toggle_active)
        refresh_btn.clicked.connect(self.refresh_templates)

        self.tpl_search_edit.textChanged.connect(self.refresh_templates)
        self.tpl_scenario_filter.currentTextChanged.connect(self.refresh_templates)
        self.tpl_active_filter.currentTextChanged.connect(self.refresh_templates)
        self.tpl_table.selectionModel().selectionChanged.connect(self._tpl_on_selection)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.tpl_search_edit, 2)
        filters.addWidget(QLabel("Scenario"))
        filters.addWidget(self.tpl_scenario_filter)
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self.tpl_active_filter)

        import_btn = QPushButton("Import CSV...")
        import_btn.clicked.connect(self._tpl_import_csv)
        export_btn = QPushButton("Export CSV...")
        export_btn.clicked.connect(self._tpl_export_csv)

        actions = QHBoxLayout()
        actions.addWidget(new_btn)
        actions.addWidget(edit_btn)
        actions.addWidget(clone_btn)
        actions.addWidget(delete_btn)
        actions.addWidget(self.tpl_toggle_btn)
        actions.addWidget(refresh_btn)
        actions.addWidget(import_btn)
        actions.addWidget(export_btn)
        actions.addStretch()

        layout = QVBoxLayout(tab)
        layout.addLayout(filters)
        layout.addWidget(splitter, 1)
        layout.addLayout(actions)
        return tab

    def _tpl_import_csv(self) -> None:
        from utils.edit_menu_io import SafetyTemplatesIO, do_import_csv
        do_import_csv(SafetyTemplatesIO(), self)
        self.refresh_templates()

    def _tpl_export_csv(self) -> None:
        from utils.edit_menu_io import SafetyTemplatesIO, do_export_csv
        do_export_csv(SafetyTemplatesIO(), self)

    def refresh_templates(self) -> None:
        status = self.tpl_active_filter.currentText()
        records = self._template_repo.list_templates(
            search_text=self.tpl_search_edit.text(),
            scenario_type=self.tpl_scenario_filter.currentText(),
            include_inactive=status in ("All", "Inactive"),
        )
        if status == "Inactive":
            records = [r for r in records if not r.get("is_active")]
        self.tpl_table_model.set_records(records)
        self._tpl_on_selection()

    def _tpl_selected_record(self) -> Optional[dict[str, Any]]:
        idx = self.tpl_table.currentIndex()
        if not idx.isValid():
            return None
        return self.tpl_table_model.record_at(self.tpl_proxy.mapToSource(idx).row())

    def _tpl_on_selection(self) -> None:
        record = self._tpl_selected_record()
        self.tpl_toggle_btn.setText("Reactivate" if record and not record.get("is_active") else "Deactivate")
        if record:
            entries = record.get("hazard_entries") or []
            lines = [
                f"{record.get('name', '')}",
                f"Scenario: {record.get('scenario_type', '')}",
                f"Target forms: {', '.join(record.get('target_forms') or []) or 'None'}",
                f"Description: {record.get('description', '') or '-'}",
                "",
                f"Hazards ({len(entries)}):",
            ]
            for i, e in enumerate(sorted(entries, key=lambda x: x.get("sort_order", 0)), 1):
                name = e.get("hazard_name") or f"Hazard #{e.get('hazard_type_id')}"
                cat = e.get("hazard_category", "")
                risk = e.get("default_risk_level", "")
                note = e.get("override_notes", "")
                detail = "  ".join(filter(None, [f"[{cat}]" if cat else "", f"Risk: {risk}" if risk else "", f"— {note}" if note else ""]))
                lines.append(f"  {i}. {name}  {detail}".rstrip())
            self.tpl_preview.setPlainText("\n".join(lines))
        else:
            self.tpl_preview.clear()

    def _tpl_new(self) -> None:
        dialog = TemplateEditDialog(self._hazard_repo, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self._template_repo.create_template(dialog.to_api_doc())
                self.refresh_templates()
            except Exception as exc:
                QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_edit_selected(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            QMessageBox.information(self, "Safety Analysis Templates", "Select a template to edit.")
            return
        tpl = self._template_repo.get_template(int(record["template_id"]))
        if tpl is None:
            QMessageBox.warning(self, "Safety Analysis Templates", "Template no longer exists.")
            self.refresh_templates()
            return
        dialog = TemplateEditDialog(self._hazard_repo, tpl, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self._template_repo.update_template(tpl.id, dialog.to_api_doc())
                self.refresh_templates()
            except Exception as exc:
                QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_clone_selected(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            QMessageBox.information(self, "Safety Analysis Templates", "Select a template to clone.")
            return
        try:
            new_id = self._template_repo.clone_template(int(record["template_id"]))
            self.refresh_templates()
            QMessageBox.information(self, "Safety Analysis Templates", f"Cloned. New ID: {new_id}")
        except Exception as exc:
            QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_delete_selected(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            QMessageBox.information(self, "Safety Analysis Templates", "Select a template to delete.")
            return
        answer = QMessageBox.question(
            self, "Delete Template",
            f"Delete '{record.get('name', '')}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self._template_repo.delete_template(int(record["template_id"]))
            self.refresh_templates()
        except Exception as exc:
            QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_toggle_active(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            QMessageBox.information(self, "Safety Analysis Templates", "Select a template first.")
            return
        self._template_repo.set_active(int(record["template_id"]), not record.get("is_active", True))
        self.refresh_templates()


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def open_hazard_type_library(
    parent: Optional[QWidget] = None,
    tab: int = 0,
) -> HazardTypeLibraryWindow:
    """Open (or raise) the Safety Analysis Library window."""
    existing = getattr(parent, "_hazard_type_library_window", None) if parent is not None else None
    if isinstance(existing, HazardTypeLibraryWindow) and existing.isVisible():
        existing._tabs.setCurrentIndex(tab)
        existing.raise_()
        existing.activateWindow()
        return existing

    window = HazardTypeLibraryWindow(parent=parent)
    window._tabs.setCurrentIndex(tab)
    if parent is not None:
        setattr(parent, "_hazard_type_library_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window
