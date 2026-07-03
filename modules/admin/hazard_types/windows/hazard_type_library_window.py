"""QtWidgets admin window for the Hazard Type Library and Safety Analysis Templates.

Implements ``Design Documents/edit_window_style_guide.md`` for each tab: card
shell, header (Add/Duplicate/Deactivate/Import/Export), filter bar with empty
states, pill delegate for the Active column, pagination footer, generic import
wizard, and export dialog with async export. Mitigations/PPE/hazard-entry
detail lives in the full editor dialogs (``HazardTypeEditorWindow`` /
``TemplateEditDialog``), not in a permanent detail pane.
"""
from __future__ import annotations

import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QStyle,
    QTableView,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from notifications.models import Notification
from notifications.services import get_notifier
from utils.edit_window_kit import (
    ExportDialog,
    FieldSpec,
    ImportWizard,
    PillDelegate,
    PaginationControls,
    run_async,
    write_export_file,
)
from utils.itemview_delegates import RowOutlineSelectionDelegate

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

try:
    from modules.admin.hazard_types.widgets import HazardTypeSearchBox
except Exception:
    HazardTypeSearchBox = None  # type: ignore[assignment]

ACTIVE_COLORS: dict[str, tuple[str, str]] = {
    "yes": ("#2e7d32", "#ffffff"),
    "no": ("#757575", "#ffffff"),
}

HAZARD_FIELDS: list[FieldSpec] = [
    FieldSpec("name", "Name", required=True),
    FieldSpec("category", "Category"),
    FieldSpec("source", "Source"),
    FieldSpec("default_risk_level", "Default Risk"),
    FieldSpec("description", "Description"),
]
_HAZARD_FIELD_LABELS = {spec.key: spec.label for spec in HAZARD_FIELDS}

TEMPLATE_FIELDS: list[FieldSpec] = [
    FieldSpec("name", "Name", required=True),
    FieldSpec("scenario_type", "Scenario Type"),
    FieldSpec("description", "Description"),
    FieldSpec("notes", "Notes"),
]
_TEMPLATE_FIELD_LABELS = {spec.key: spec.label for spec in TEMPLATE_FIELDS}


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
        "hazard_name",
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

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        record = self._records[index.row()]
        key = self.keys[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
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

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        record = self._records[index.row()]
        key = self.keys[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
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

        self._hazard_list = QListWidget()
        self._hazard_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        if template:
            for entry in sorted(template.hazard_entries, key=lambda e: e.sort_order):
                self._add_entry_item(entry)

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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
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
        item.setData(Qt.ItemDataRole.UserRole, {
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
            for i in range(self._hazard_list.count()):
                d = self._hazard_list.item(i).data(Qt.ItemDataRole.UserRole)
                if d and d.get("hazard_type_id") == int(hid):
                    QMessageBox.information(self, "Add Hazard", "That hazard is already in this template.")
                    return
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
            d = self._hazard_list.item(i).data(Qt.ItemDataRole.UserRole) or {}
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
        super().__init__(parent, Qt.WindowType.Window)
        self._hazard_repo = repository or ApiHazardTypeRepository()
        self._template_repo = ApiSafetyTemplateRepository()
        self._notifier = get_notifier()
        self.setWindowTitle("Safety Analysis Library")
        self.resize(1240, 780)

        self._ht_records: list[dict[str, Any]] = []
        self._ht_page = 1
        self._ht_page_size = 20

        self._tpl_records: list[dict[str, Any]] = []
        self._tpl_page = 1
        self._tpl_page_size = 20

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_hazard_types_tab(), "Hazard Types")
        self._tabs.addTab(self._build_templates_tab(), "Scenario Templates")
        outer.addWidget(self._tabs)

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
        tab = QFrame()
        tab.setObjectName("hazardTypesCard")
        tab.setStyleSheet(
            "#hazardTypesCard { border-radius: 12px; background: palette(Base); } QTableView { border: none; }"
        )
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addStretch(1)
        self.ht_new_btn = QPushButton("Add")
        self.ht_new_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.ht_duplicate_btn = QPushButton("Duplicate")
        self.ht_toggle_btn = QPushButton("Deactivate")
        self.ht_import_btn = QPushButton("Import")
        self.ht_import_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.ht_export_btn = QPushButton("Export")
        self.ht_export_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        for btn in (self.ht_new_btn, self.ht_duplicate_btn, self.ht_toggle_btn, self.ht_import_btn, self.ht_export_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            header.addWidget(btn)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(12)
        self.ht_search_edit = QLineEdit()
        self.ht_search_edit.setPlaceholderText("Search name, aliases, mitigations, PPE, notes…")
        self.ht_search_edit.setClearButtonEnabled(True)
        filters.addWidget(self.ht_search_edit, stretch=2)
        self.ht_category_filter = QComboBox()
        self.ht_category_filter.addItems(("All",) + HAZARD_CATEGORIES)
        filters.addWidget(self.ht_category_filter)
        self.ht_source_filter = QComboBox()
        self.ht_source_filter.addItems(("All",) + HAZARD_SOURCES)
        filters.addWidget(self.ht_source_filter)
        self.ht_risk_filter = QComboBox()
        self.ht_risk_filter.addItems(("All",) + HAZARD_RISK_LEVELS)
        filters.addWidget(self.ht_risk_filter)
        self.ht_active_filter = QComboBox()
        self.ht_active_filter.addItems(("Active", "Inactive", "All"))
        filters.addWidget(self.ht_active_filter)
        self.ht_reset_btn = QToolButton()
        self.ht_reset_btn.setText("Reset filters")
        self.ht_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ht_reset_btn.setStyleSheet("QToolButton { text-decoration: underline; border: none; padding: 4px; }")
        self.ht_reset_btn.hide()
        filters.addWidget(self.ht_reset_btn)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.ht_error_banner = QFrame()
        self.ht_error_banner.setStyleSheet("background: #fdecea; border-radius: 8px; border: 1px solid #f5c6cb;")
        self.ht_error_banner.hide()
        eb_layout = QHBoxLayout(self.ht_error_banner)
        eb_layout.setContentsMargins(12, 8, 12, 8)
        self.ht_error_label = QLabel("Failed to load data.")
        self.ht_error_label.setStyleSheet("color: #b71c1c;")
        eb_layout.addWidget(self.ht_error_label, stretch=1)
        self.ht_retry_btn = QPushButton("Retry")
        eb_layout.addWidget(self.ht_retry_btn)
        layout.addWidget(self.ht_error_banner)

        self.ht_table_model = HazardTypeTableModel(self)
        self.ht_table = QTableView()
        self.ht_table.setModel(self.ht_table_model)
        self.ht_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ht_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ht_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ht_table.setAlternatingRowColors(False)
        self.ht_table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self.ht_table.setItemDelegate(RowOutlineSelectionDelegate(self.ht_table, QColor("#FFFFFF")))
        self.ht_table.setItemDelegateForColumn(
            HazardTypeTableModel.keys.index("is_active"), PillDelegate(self.ht_table, ACTIVE_COLORS)
        )
        self.ht_table.verticalHeader().setVisible(False)
        self.ht_table.verticalHeader().setDefaultSectionSize(40)
        self.ht_table.horizontalHeader().setStretchLastSection(True)
        self.ht_table.doubleClicked.connect(self._ht_edit_selected)

        self.ht_table_stack = QStackedLayout()
        ht_table_container = QWidget()
        ht_table_layout = QVBoxLayout(ht_table_container)
        ht_table_layout.setContentsMargins(0, 0, 0, 0)
        ht_table_layout.addWidget(self.ht_table)
        self.ht_table_stack.addWidget(ht_table_container)

        self.ht_no_results = QWidget()
        nr_layout = QVBoxLayout(self.ht_no_results)
        nr_layout.addStretch(1)
        nr_label = QLabel("No hazard types match your filters.")
        nr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nr_label.setStyleSheet("font-size: 16px; color: palette(Mid);")
        nr_layout.addWidget(nr_label)
        ht_clear_btn = QPushButton("Clear filters")
        ht_clear_btn.setFixedWidth(160)
        ht_clear_btn.clicked.connect(self._ht_reset_filters)
        nr_layout.addWidget(ht_clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        nr_layout.addStretch(1)
        self.ht_table_stack.addWidget(self.ht_no_results)

        self.ht_first_run = QWidget()
        fr_layout = QVBoxLayout(self.ht_first_run)
        fr_layout.addStretch(1)
        fr_label = QLabel("Add your first hazard type.")
        fr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fr_label.setStyleSheet("font-size: 16px; color: palette(Mid);")
        fr_layout.addWidget(fr_label)
        fr_btn = QPushButton("Add hazard type")
        fr_btn.setFixedWidth(180)
        fr_btn.clicked.connect(self._ht_new)
        fr_layout.addWidget(fr_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        fr_layout.addStretch(1)
        self.ht_table_stack.addWidget(self.ht_first_run)

        layout.addLayout(self.ht_table_stack, 1)

        self.ht_pagination = PaginationControls(self)
        layout.addWidget(self.ht_pagination)

        self.ht_new_btn.clicked.connect(self._ht_new)
        self.ht_duplicate_btn.clicked.connect(self._ht_clone_selected)
        self.ht_toggle_btn.clicked.connect(self._ht_toggle_active)
        self.ht_import_btn.clicked.connect(self._ht_import)
        self.ht_export_btn.clicked.connect(self._ht_export)
        self.ht_retry_btn.clicked.connect(self.refresh_hazard_types)
        self.ht_reset_btn.clicked.connect(self._ht_reset_filters)

        self._ht_debounce = QTimer(self)
        self._ht_debounce.setInterval(250)
        self._ht_debounce.setSingleShot(True)
        self._ht_debounce.timeout.connect(self.refresh_hazard_types)
        self.ht_search_edit.textChanged.connect(lambda: self._ht_debounce.start())
        self.ht_category_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_source_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_risk_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_active_filter.currentTextChanged.connect(self.refresh_hazard_types)
        self.ht_table.selectionModel().selectionChanged.connect(self._ht_update_buttons)
        self.ht_pagination.pageRequested.connect(self._ht_on_page_requested)
        self.ht_pagination.pageSizeChanged.connect(self._ht_on_page_size_changed)

        return tab

    def _ht_reset_filters(self) -> None:
        self.ht_search_edit.clear()
        self.ht_category_filter.setCurrentIndex(0)
        self.ht_source_filter.setCurrentIndex(0)
        self.ht_risk_filter.setCurrentIndex(0)
        self.ht_active_filter.setCurrentText("Active")
        self.refresh_hazard_types()

    def refresh_hazard_types(self) -> None:
        self._ht_debounce.stop()
        needle = self.ht_search_edit.text().strip()
        self.ht_reset_btn.setVisible(
            bool(needle) or self.ht_category_filter.currentText() != "All"
            or self.ht_source_filter.currentText() != "All" or self.ht_risk_filter.currentText() != "All"
            or self.ht_active_filter.currentText() != "Active"
        )
        try:
            records = self._hazard_repo.list_hazard_types({
                "search_text": needle,
                "category": self.ht_category_filter.currentText(),
                "source": self.ht_source_filter.currentText(),
                "risk_level": self.ht_risk_filter.currentText(),
                "active_filter": self.ht_active_filter.currentText(),
            })
        except Exception as exc:
            self.ht_error_label.setText(f"Unable to load hazard types: {exc}")
            self.ht_error_banner.show()
            return
        self.ht_error_banner.hide()
        self._ht_records = records
        self._ht_page = 1
        self._ht_render_page()

    def _ht_render_page(self) -> None:
        total = len(self._ht_records)
        max_page = max(1, math.ceil(total / self._ht_page_size)) if self._ht_page_size else 1
        self._ht_page = min(max(1, self._ht_page), max_page)
        start = (self._ht_page - 1) * self._ht_page_size
        self.ht_table_model.set_records(self._ht_records[start:start + self._ht_page_size])
        self.ht_pagination.update_state(total=total, page=self._ht_page, page_size=self._ht_page_size)
        if total == 0:
            if self.ht_reset_btn.isVisible():
                self.ht_table_stack.setCurrentWidget(self.ht_no_results)
            else:
                self.ht_table_stack.setCurrentWidget(self.ht_first_run)
        else:
            self.ht_table_stack.setCurrentIndex(0)
        self._ht_update_buttons()

    def _ht_on_page_requested(self, page: int) -> None:
        self._ht_page = page
        self._ht_render_page()

    def _ht_on_page_size_changed(self, page_size: int) -> None:
        self._ht_page_size = page_size
        self._ht_page = 1
        self._ht_render_page()

    def _ht_selected_record(self) -> Optional[dict[str, Any]]:
        idx = self.ht_table.currentIndex()
        if not idx.isValid():
            return None
        return self.ht_table_model.record_at(idx.row())

    def _ht_update_buttons(self) -> None:
        record = self._ht_selected_record()
        has = record is not None
        self.ht_duplicate_btn.setEnabled(has)
        self.ht_toggle_btn.setEnabled(has)
        self.ht_toggle_btn.setText("Reactivate" if record and not record.get("is_active") else "Deactivate")

    def _ht_new(self) -> None:
        dialog = HazardTypeEditorWindow(self._hazard_repo, parent=self)
        if dialog.exec() == HazardTypeEditorWindow.DialogCode.Accepted:
            self._ht_save(dialog)

    def _ht_edit_selected(self) -> None:
        record = self._ht_selected_record()
        if not record:
            return
        ht = self._hazard_repo.get_hazard_type(int(record["id"]))
        if ht is None:
            QMessageBox.warning(self, "Hazard Type Library", "The selected record no longer exists.")
            self.refresh_hazard_types()
            return
        dialog = HazardTypeEditorWindow(self._hazard_repo, ht, self)
        if dialog.exec() == HazardTypeEditorWindow.DialogCode.Accepted:
            self._ht_save(dialog)

    def _ht_save(self, dialog: HazardTypeEditorWindow) -> None:
        try:
            ht = dialog.to_model()
            if ht.id is None:
                self._hazard_repo.create_hazard_type(ht)
            else:
                self._hazard_repo.update_hazard_type(ht.id, ht)
            self.refresh_hazard_types()
            self._show_toast("Hazard type saved", f"'{ht.name}' saved successfully.")
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))

    def _ht_clone_selected(self) -> None:
        record = self._ht_selected_record()
        if not record:
            return
        try:
            self._hazard_repo.clone_hazard_type(int(record["id"]))
            self.refresh_hazard_types()
            self._show_toast("Hazard type duplicated", f"Duplicated '{record.get('name', '')}'.")
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))

    def _ht_toggle_active(self) -> None:
        record = self._ht_selected_record()
        if not record:
            return
        if record.get("is_active"):
            self._hazard_repo.deactivate_hazard_type(int(record["id"]))
        else:
            self._hazard_repo.reactivate_hazard_type(int(record["id"]))
        self.refresh_hazard_types()

    def _ht_import(self) -> None:
        def _import_row(payload: dict[str, Any]) -> Any:
            return self._hazard_repo.create_hazard_type(payload)

        wizard = ImportWizard(fields=HAZARD_FIELDS, import_row=_import_row, title="Import Hazard Types", parent=self)
        result = wizard.exec()
        created = wizard.created_records()
        errors = wizard.error_count()
        if result == QDialog.DialogCode.Accepted and (created or errors):
            self.refresh_hazard_types()
            if created and errors:
                self._show_toast("Import complete", f"{len(created)} hazard types imported with {errors} errors.", severity="warning")
            elif created:
                self._show_toast("Import complete", f"Imported {len(created)} hazard types.")
            elif errors:
                self._show_toast("Import issues", "No rows were imported. Check the error report.", severity="warning")

    def _ht_export(self) -> None:
        selection_model = self.ht_table.selectionModel()
        allow_selected = bool(selection_model and selection_model.hasSelection())
        dialog = ExportDialog(fields=HAZARD_FIELDS, allow_selected=allow_selected, title="Export Hazard Types", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        scope = dialog.selected_scope()
        file_format = dialog.selected_format()
        fields = dialog.selected_fields()

        if scope == "selected":
            rec = self._ht_selected_record()
            if rec is None:
                QMessageBox.information(self, "No selection", "Select a row to export or choose a different scope.")
                return
            rows = [rec]
        else:
            rows = list(self._ht_records)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path(tempfile.gettempdir()) / f"hazard-types-{scope}-{timestamp}.{file_format}"

        def _task() -> dict[str, Any]:
            write_export_file(path, rows, fields, _HAZARD_FIELD_LABELS, file_format)
            return {"path": str(path), "count": len(rows)}

        self.ht_export_btn.setEnabled(False)
        run_async(self, _task, self._ht_on_export_done, self._ht_on_export_failed)

    def _ht_on_export_done(self, result: dict[str, Any]) -> None:
        self.ht_export_btn.setEnabled(True)
        message = f"{result.get('count', 0)} hazard types exported. Saved to {result.get('path')}."
        self._show_toast("Export ready", message)
        QMessageBox.information(self, "Export ready", message)

    def _ht_on_export_failed(self, message: str) -> None:
        self.ht_export_btn.setEnabled(True)
        self._show_toast("Export failed", message, severity="error")
        QMessageBox.critical(self, "Export failed", message)

    # ------------------------------------------------------------------
    # Scenario Templates tab
    # ------------------------------------------------------------------

    def _build_templates_tab(self) -> QWidget:
        tab = QFrame()
        tab.setObjectName("templatesCard")
        tab.setStyleSheet(
            "#templatesCard { border-radius: 12px; background: palette(Base); } QTableView { border: none; }"
        )
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addStretch(1)
        self.tpl_new_btn = QPushButton("Add")
        self.tpl_new_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.tpl_duplicate_btn = QPushButton("Duplicate")
        self.tpl_delete_btn = QPushButton("Delete")
        self.tpl_toggle_btn = QPushButton("Deactivate")
        self.tpl_import_btn = QPushButton("Import")
        self.tpl_import_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.tpl_export_btn = QPushButton("Export")
        self.tpl_export_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        for btn in (self.tpl_new_btn, self.tpl_duplicate_btn, self.tpl_delete_btn, self.tpl_toggle_btn, self.tpl_import_btn, self.tpl_export_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            header.addWidget(btn)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(12)
        self.tpl_search_edit = QLineEdit()
        self.tpl_search_edit.setPlaceholderText("Search by name or description…")
        self.tpl_search_edit.setClearButtonEnabled(True)
        filters.addWidget(self.tpl_search_edit, stretch=2)
        self.tpl_scenario_filter = QComboBox()
        self.tpl_scenario_filter.addItems(("All",) + SAFETY_SCENARIO_TYPES)
        filters.addWidget(self.tpl_scenario_filter)
        self.tpl_active_filter = QComboBox()
        self.tpl_active_filter.addItems(("Active", "All", "Inactive"))
        filters.addWidget(self.tpl_active_filter)
        self.tpl_reset_btn = QToolButton()
        self.tpl_reset_btn.setText("Reset filters")
        self.tpl_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tpl_reset_btn.setStyleSheet("QToolButton { text-decoration: underline; border: none; padding: 4px; }")
        self.tpl_reset_btn.hide()
        filters.addWidget(self.tpl_reset_btn)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.tpl_error_banner = QFrame()
        self.tpl_error_banner.setStyleSheet("background: #fdecea; border-radius: 8px; border: 1px solid #f5c6cb;")
        self.tpl_error_banner.hide()
        eb_layout = QHBoxLayout(self.tpl_error_banner)
        eb_layout.setContentsMargins(12, 8, 12, 8)
        self.tpl_error_label = QLabel("Failed to load data.")
        self.tpl_error_label.setStyleSheet("color: #b71c1c;")
        eb_layout.addWidget(self.tpl_error_label, stretch=1)
        self.tpl_retry_btn = QPushButton("Retry")
        eb_layout.addWidget(self.tpl_retry_btn)
        layout.addWidget(self.tpl_error_banner)

        self.tpl_table_model = TemplateTableModel(self)
        self.tpl_table = QTableView()
        self.tpl_table.setModel(self.tpl_table_model)
        self.tpl_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tpl_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tpl_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tpl_table.setAlternatingRowColors(False)
        self.tpl_table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self.tpl_table.setItemDelegate(RowOutlineSelectionDelegate(self.tpl_table, QColor("#FFFFFF")))
        self.tpl_table.setItemDelegateForColumn(
            TemplateTableModel.keys.index("is_active"), PillDelegate(self.tpl_table, ACTIVE_COLORS)
        )
        self.tpl_table.verticalHeader().setVisible(False)
        self.tpl_table.verticalHeader().setDefaultSectionSize(40)
        self.tpl_table.horizontalHeader().setStretchLastSection(True)
        self.tpl_table.doubleClicked.connect(self._tpl_edit_selected)

        self.tpl_table_stack = QStackedLayout()
        tpl_table_container = QWidget()
        tpl_table_layout = QVBoxLayout(tpl_table_container)
        tpl_table_layout.setContentsMargins(0, 0, 0, 0)
        tpl_table_layout.addWidget(self.tpl_table)
        self.tpl_table_stack.addWidget(tpl_table_container)

        self.tpl_no_results = QWidget()
        nr_layout = QVBoxLayout(self.tpl_no_results)
        nr_layout.addStretch(1)
        nr_label = QLabel("No templates match your filters.")
        nr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nr_label.setStyleSheet("font-size: 16px; color: palette(Mid);")
        nr_layout.addWidget(nr_label)
        tpl_clear_btn = QPushButton("Clear filters")
        tpl_clear_btn.setFixedWidth(160)
        tpl_clear_btn.clicked.connect(self._tpl_reset_filters)
        nr_layout.addWidget(tpl_clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        nr_layout.addStretch(1)
        self.tpl_table_stack.addWidget(self.tpl_no_results)

        self.tpl_first_run = QWidget()
        fr_layout = QVBoxLayout(self.tpl_first_run)
        fr_layout.addStretch(1)
        fr_label = QLabel("Add your first scenario template.")
        fr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fr_label.setStyleSheet("font-size: 16px; color: palette(Mid);")
        fr_layout.addWidget(fr_label)
        fr_btn = QPushButton("Add template")
        fr_btn.setFixedWidth(180)
        fr_btn.clicked.connect(self._tpl_new)
        fr_layout.addWidget(fr_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        fr_layout.addStretch(1)
        self.tpl_table_stack.addWidget(self.tpl_first_run)

        layout.addLayout(self.tpl_table_stack, 1)

        self.tpl_pagination = PaginationControls(self)
        layout.addWidget(self.tpl_pagination)

        self.tpl_new_btn.clicked.connect(self._tpl_new)
        self.tpl_duplicate_btn.clicked.connect(self._tpl_clone_selected)
        self.tpl_delete_btn.clicked.connect(self._tpl_delete_selected)
        self.tpl_toggle_btn.clicked.connect(self._tpl_toggle_active)
        self.tpl_import_btn.clicked.connect(self._tpl_import)
        self.tpl_export_btn.clicked.connect(self._tpl_export)
        self.tpl_retry_btn.clicked.connect(self.refresh_templates)
        self.tpl_reset_btn.clicked.connect(self._tpl_reset_filters)

        self._tpl_debounce = QTimer(self)
        self._tpl_debounce.setInterval(250)
        self._tpl_debounce.setSingleShot(True)
        self._tpl_debounce.timeout.connect(self.refresh_templates)
        self.tpl_search_edit.textChanged.connect(lambda: self._tpl_debounce.start())
        self.tpl_scenario_filter.currentTextChanged.connect(self.refresh_templates)
        self.tpl_active_filter.currentTextChanged.connect(self.refresh_templates)
        self.tpl_table.selectionModel().selectionChanged.connect(self._tpl_update_buttons)
        self.tpl_pagination.pageRequested.connect(self._tpl_on_page_requested)
        self.tpl_pagination.pageSizeChanged.connect(self._tpl_on_page_size_changed)

        return tab

    def _tpl_reset_filters(self) -> None:
        self.tpl_search_edit.clear()
        self.tpl_scenario_filter.setCurrentIndex(0)
        self.tpl_active_filter.setCurrentText("Active")
        self.refresh_templates()

    def refresh_templates(self) -> None:
        self._tpl_debounce.stop()
        status = self.tpl_active_filter.currentText()
        needle = self.tpl_search_edit.text().strip()
        self.tpl_reset_btn.setVisible(
            bool(needle) or self.tpl_scenario_filter.currentText() != "All" or status != "Active"
        )
        try:
            records = self._template_repo.list_templates(
                search_text=needle,
                scenario_type=self.tpl_scenario_filter.currentText(),
                include_inactive=status in ("All", "Inactive"),
            )
        except Exception as exc:
            self.tpl_error_label.setText(f"Unable to load templates: {exc}")
            self.tpl_error_banner.show()
            return
        self.tpl_error_banner.hide()
        if status == "Inactive":
            records = [r for r in records if not r.get("is_active")]
        self._tpl_records = records
        self._tpl_page = 1
        self._tpl_render_page()

    def _tpl_render_page(self) -> None:
        total = len(self._tpl_records)
        max_page = max(1, math.ceil(total / self._tpl_page_size)) if self._tpl_page_size else 1
        self._tpl_page = min(max(1, self._tpl_page), max_page)
        start = (self._tpl_page - 1) * self._tpl_page_size
        self.tpl_table_model.set_records(self._tpl_records[start:start + self._tpl_page_size])
        self.tpl_pagination.update_state(total=total, page=self._tpl_page, page_size=self._tpl_page_size)
        if total == 0:
            if self.tpl_reset_btn.isVisible():
                self.tpl_table_stack.setCurrentWidget(self.tpl_no_results)
            else:
                self.tpl_table_stack.setCurrentWidget(self.tpl_first_run)
        else:
            self.tpl_table_stack.setCurrentIndex(0)
        self._tpl_update_buttons()

    def _tpl_on_page_requested(self, page: int) -> None:
        self._tpl_page = page
        self._tpl_render_page()

    def _tpl_on_page_size_changed(self, page_size: int) -> None:
        self._tpl_page_size = page_size
        self._tpl_page = 1
        self._tpl_render_page()

    def _tpl_selected_record(self) -> Optional[dict[str, Any]]:
        idx = self.tpl_table.currentIndex()
        if not idx.isValid():
            return None
        return self.tpl_table_model.record_at(idx.row())

    def _tpl_update_buttons(self) -> None:
        record = self._tpl_selected_record()
        has = record is not None
        self.tpl_duplicate_btn.setEnabled(has)
        self.tpl_delete_btn.setEnabled(has)
        self.tpl_toggle_btn.setEnabled(has)
        self.tpl_toggle_btn.setText("Reactivate" if record and not record.get("is_active") else "Deactivate")

    def _tpl_new(self) -> None:
        dialog = TemplateEditDialog(self._hazard_repo, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._template_repo.create_template(dialog.to_api_doc())
                self.refresh_templates()
                self._show_toast("Template saved", f"'{dialog.to_api_doc().get('name')}' saved successfully.")
            except Exception as exc:
                QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_edit_selected(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            return
        tpl = self._template_repo.get_template(int(record["template_id"]))
        if tpl is None:
            QMessageBox.warning(self, "Safety Analysis Templates", "Template no longer exists.")
            self.refresh_templates()
            return
        dialog = TemplateEditDialog(self._hazard_repo, tpl, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._template_repo.update_template(tpl.id, dialog.to_api_doc())
                self.refresh_templates()
                self._show_toast("Template saved", f"'{dialog.to_api_doc().get('name')}' updated.")
            except Exception as exc:
                QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_clone_selected(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            return
        try:
            self._template_repo.clone_template(int(record["template_id"]))
            self.refresh_templates()
            self._show_toast("Template duplicated", f"Duplicated '{record.get('name', '')}'.")
        except Exception as exc:
            QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_delete_selected(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            return
        answer = QMessageBox.question(
            self, "Delete Template",
            f"Delete '{record.get('name', '')}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._template_repo.delete_template(int(record["template_id"]))
            self.refresh_templates()
            self._show_toast("Template deleted", f"'{record.get('name', '')}' was deleted.")
        except Exception as exc:
            QMessageBox.warning(self, "Safety Analysis Templates", str(exc))

    def _tpl_toggle_active(self) -> None:
        record = self._tpl_selected_record()
        if not record:
            return
        self._template_repo.set_active(int(record["template_id"]), not record.get("is_active", True))
        self.refresh_templates()

    def _tpl_import(self) -> None:
        def _import_row(payload: dict[str, Any]) -> Any:
            doc = {
                "name": payload["name"],
                "description": payload.get("description", ""),
                "scenario_type": payload.get("scenario_type") or SAFETY_SCENARIO_TYPES[0],
                "notes": payload.get("notes", ""),
                "target_forms": [],
                "hazard_entries": [],
                "is_active": True,
            }
            return self._template_repo.create_template(doc)

        wizard = ImportWizard(fields=TEMPLATE_FIELDS, import_row=_import_row, title="Import Scenario Templates", parent=self)
        result = wizard.exec()
        created = wizard.created_records()
        errors = wizard.error_count()
        if result == QDialog.DialogCode.Accepted and (created or errors):
            self.refresh_templates()
            if created and errors:
                self._show_toast("Import complete", f"{len(created)} templates imported with {errors} errors.", severity="warning")
            elif created:
                self._show_toast(
                    "Import complete",
                    f"Imported {len(created)} templates. Target forms and hazard entries weren't included — "
                    "add those via Edit.",
                )
            elif errors:
                self._show_toast("Import issues", "No rows were imported. Check the error report.", severity="warning")

    def _tpl_export(self) -> None:
        selection_model = self.tpl_table.selectionModel()
        allow_selected = bool(selection_model and selection_model.hasSelection())
        dialog = ExportDialog(fields=TEMPLATE_FIELDS, allow_selected=allow_selected, title="Export Scenario Templates", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        scope = dialog.selected_scope()
        file_format = dialog.selected_format()
        fields = dialog.selected_fields()

        if scope == "selected":
            rec = self._tpl_selected_record()
            if rec is None:
                QMessageBox.information(self, "No selection", "Select a row to export or choose a different scope.")
                return
            rows = [rec]
        else:
            rows = list(self._tpl_records)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path(tempfile.gettempdir()) / f"scenario-templates-{scope}-{timestamp}.{file_format}"

        def _task() -> dict[str, Any]:
            write_export_file(path, rows, fields, _TEMPLATE_FIELD_LABELS, file_format)
            return {"path": str(path), "count": len(rows)}

        self.tpl_export_btn.setEnabled(False)
        run_async(self, _task, self._tpl_on_export_done, self._tpl_on_export_failed)

    def _tpl_on_export_done(self, result: dict[str, Any]) -> None:
        self.tpl_export_btn.setEnabled(True)
        message = f"{result.get('count', 0)} templates exported. Saved to {result.get('path')}."
        self._show_toast("Export ready", message)
        QMessageBox.information(self, "Export ready", message)

    def _tpl_on_export_failed(self, message: str) -> None:
        self.tpl_export_btn.setEnabled(True)
        self._show_toast("Export failed", message, severity="error")
        QMessageBox.critical(self, "Export failed", message)

    # ------------------------------------------------------------------
    # Shared toast helper
    # ------------------------------------------------------------------

    def _show_toast(self, title: str, message: str, *, severity: str = "success") -> None:
        try:
            self._notifier.notify(
                Notification(
                    title=title,
                    message=message,
                    severity=severity if severity in {"info", "success", "warning", "error"} else "info",
                    source="Safety Analysis Library",
                )
            )
        except Exception:
            pass


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
