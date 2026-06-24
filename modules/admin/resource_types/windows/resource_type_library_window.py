"""QtWidgets admin window for the Resource Type Library.

Implements ``Design Documents/edit_window_style_guide.md``: card shell,
header (Add/Duplicate/Deactivate/Import/Export), filter bar with empty
states, pill delegate for the Active column, pagination footer, generic
import wizard, and export dialog with async export. The Capability Manager
and the full resource-type editor (components, FEMA/NIMS mappings) stay as
separate dialogs — those relational fields don't fit a flat CSV/wizard.
"""
from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QStyle,
    QTableView,
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

from ..data.resource_type_repository import ApiResourceTypeRepository
from ..models.resource_type_models import RESOURCE_CATEGORIES, RESOURCE_SOURCES, ResourceType
from .capability_manager_window import CapabilityManagerWindow
from .resource_type_editor_window import ResourceTypeEditorWindow

ACTIVE_COLORS: dict[str, tuple[str, str]] = {
    "yes": ("#2e7d32", "#ffffff"),
    "no": ("#757575", "#ffffff"),
}

FIELDS: list[FieldSpec] = [
    FieldSpec("name", "Name", required=True),
    FieldSpec("planning_display_name", "Planning Display Name"),
    FieldSpec("category", "Category"),
    FieldSpec("source", "Source"),
    FieldSpec("owner_agency", "Owner Agency"),
    FieldSpec("description", "Description"),
    FieldSpec("notes", "Notes"),
]
_FIELD_LABELS = {spec.key: spec.label for spec in FIELDS}


class ResourceTypeTableModel(QAbstractTableModel):
    """Table model for the main Resource Type Library browser."""

    headers = [
        "Name",
        "Planning Display Name",
        "Category",
        "Source",
        "Owner Agency",
        "Capabilities",
        "Kit/Cache",
        "Active",
        "Updated At",
    ]
    keys = [
        "name",
        "planning_display_name",
        "category",
        "source",
        "owner_agency",
        "capabilities",
        "is_kit_cache",
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
            if key == "is_kit_cache":
                count = int(record.get("component_count") or 0)
                if record.get("is_kit_cache"):
                    return f"Yes ({count})" if count else "Yes"
                return "No"
            if key == "is_active":
                return "Yes" if record.get(key) else "No"
            return record.get(key, "")
        if role == Qt.ItemDataRole.ToolTipRole and key == "capabilities":
            return record.get("capabilities", "")
        return None

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def record_at(self, row: int) -> Optional[dict[str, Any]]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


class ResourceTypeLibraryWindow(QWidget):
    """Standalone modeless admin window for resource type master data."""

    def __init__(
        self,
        repository: Optional[ApiResourceTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.repository = repository or ApiResourceTypeRepository()
        self._notifier = get_notifier()
        self.setWindowTitle("Resource Type Library")
        self.resize(1180, 700)

        self._all_records: list[dict[str, Any]] = []
        self._page = 1
        self._page_size = 20

        self._build_ui()
        self.refresh()

    # ----- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        card = QFrame(self)
        card.setObjectName("resourceTypeCard")
        card.setStyleSheet(
            """
            #resourceTypeCard {
                border-radius: 16px;
                background: palette(Base);
                border: 1px solid palette(Midlight);
            }
            QTableView { border: none; }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Resource Type Library")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)

        self.add_button = QPushButton("Add")
        self.add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setToolTip("Add a resource type")
        header.addWidget(self.add_button)

        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.duplicate_button.setToolTip("Duplicate the selected resource type")
        self.duplicate_button.setEnabled(False)
        header.addWidget(self.duplicate_button)

        self.toggle_active_button = QPushButton("Deactivate")
        self.toggle_active_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_active_button.setEnabled(False)
        header.addWidget(self.toggle_active_button)

        self.capability_button = QPushButton("Capability Manager")
        self.capability_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capability_button.setToolTip("Manage shared capability definitions")
        header.addWidget(self.capability_button)

        self.import_button = QPushButton("Import")
        self.import_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.import_button)

        self.export_button = QPushButton("Export")
        self.export_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.export_button)

        card_layout.addLayout(header)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Search name, display name, aliases, category, capabilities, agency, or FEMA/NIMS mapping…"
        )
        self.search_edit.setClearButtonEnabled(True)
        filter_bar.addWidget(self.search_edit, stretch=2)

        self.category_filter = QComboBox()
        self.category_filter.addItems(("All",) + RESOURCE_CATEGORIES)
        filter_bar.addWidget(self.category_filter)

        self.source_filter = QComboBox()
        self.source_filter.addItems(("All",) + RESOURCE_SOURCES)
        filter_bar.addWidget(self.source_filter)

        self.active_filter = QComboBox()
        self.active_filter.addItems(("Active", "Inactive", "All"))
        filter_bar.addWidget(self.active_filter)

        self.reset_button = QToolButton()
        self.reset_button.setText("Reset filters")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setStyleSheet("QToolButton { text-decoration: underline; border: none; padding: 4px; }")
        self.reset_button.hide()
        filter_bar.addWidget(self.reset_button)
        filter_bar.addStretch(1)
        card_layout.addLayout(filter_bar)

        # Error banner
        self.error_banner = QFrame()
        self.error_banner.setObjectName("resourceTypeErrorBanner")
        self.error_banner.setStyleSheet(
            "#resourceTypeErrorBanner { background: #fdecea; border-radius: 8px; border: 1px solid #f5c6cb; }"
        )
        self.error_banner.hide()
        error_layout = QHBoxLayout(self.error_banner)
        error_layout.setContentsMargins(12, 8, 12, 8)
        self.error_label = QLabel("Failed to load data.")
        self.error_label.setStyleSheet("color: #b71c1c;")
        error_layout.addWidget(self.error_label, stretch=1)
        self.retry_button = QPushButton("Retry")
        error_layout.addWidget(self.retry_button)
        card_layout.addWidget(self.error_banner)

        # Table + empty states
        self.table_model = ResourceTypeTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self._sel_delegate = RowOutlineSelectionDelegate(self.table, QColor("#FFFFFF"))
        self.table.setItemDelegate(self._sel_delegate)
        self.table.setItemDelegateForColumn(
            ResourceTypeTableModel.keys.index("is_active"), PillDelegate(self.table, ACTIVE_COLORS)
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionsClickable(True)
        self.table.doubleClicked.connect(self._edit_selected)

        self.table_stack = QStackedLayout()
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)
        self.table_stack.addWidget(table_container)

        self.no_results_widget = QWidget()
        nr_layout = QVBoxLayout(self.no_results_widget)
        nr_layout.addStretch(1)
        nr_message = QLabel("No resource types match your filters.")
        nr_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nr_message.setStyleSheet("font-size: 16px; color: palette(Mid);")
        nr_layout.addWidget(nr_message)
        clear_btn = QPushButton("Clear filters")
        clear_btn.setFixedWidth(160)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._on_reset_filters)
        nr_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        nr_layout.addStretch(1)
        self.table_stack.addWidget(self.no_results_widget)

        self.first_run_widget = QWidget()
        fr_layout = QVBoxLayout(self.first_run_widget)
        fr_layout.addStretch(1)
        fr_message = QLabel("Add your first resource type.")
        fr_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fr_message.setStyleSheet("font-size: 16px; color: palette(Mid);")
        fr_layout.addWidget(fr_message)
        fr_add_button = QPushButton("Add resource type")
        fr_add_button.setFixedWidth(180)
        fr_add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        fr_add_button.clicked.connect(self._new_resource_type)
        fr_layout.addWidget(fr_add_button, alignment=Qt.AlignmentFlag.AlignCenter)
        fr_layout.addStretch(1)
        self.table_stack.addWidget(self.first_run_widget)

        card_layout.addLayout(self.table_stack, stretch=1)

        self.pagination = PaginationControls(self)
        card_layout.addWidget(self.pagination)

        outer.addWidget(card)

        # Signals
        self._debounce = QTimer(self)
        self._debounce.setInterval(250)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.refresh)
        self.search_edit.textChanged.connect(self._on_filter_text_changed)
        self.category_filter.currentTextChanged.connect(self.refresh)
        self.source_filter.currentTextChanged.connect(self.refresh)
        self.active_filter.currentTextChanged.connect(self.refresh)
        self.reset_button.clicked.connect(self._on_reset_filters)

        self.add_button.clicked.connect(self._new_resource_type)
        self.duplicate_button.clicked.connect(self._clone_selected)
        self.toggle_active_button.clicked.connect(self._toggle_selected_active)
        self.capability_button.clicked.connect(self._open_capability_manager)
        self.import_button.clicked.connect(self._import)
        self.export_button.clicked.connect(self._export)
        self.retry_button.clicked.connect(self.refresh)

        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._update_buttons)

        self.pagination.pageRequested.connect(self._on_page_requested)
        self.pagination.pageSizeChanged.connect(self._on_page_size_changed)

    # ----- Data loading ------------------------------------------------------
    def refresh(self) -> None:
        self._debounce.stop()
        needle = self.search_edit.text().strip()
        self.reset_button.setVisible(
            bool(needle) or self.category_filter.currentText() != "All"
            or self.source_filter.currentText() != "All" or self.active_filter.currentText() != "Active"
        )
        try:
            records = self.repository.list_resource_types(
                search_text=needle,
                category=self.category_filter.currentText(),
                source=self.source_filter.currentText(),
                active_filter=self.active_filter.currentText(),
            )
        except Exception as exc:
            self._show_error(f"Unable to load resource types: {exc}")
            return
        self._hide_error()
        self._all_records = records
        self._page = 1
        self._render_page()

    def _on_filter_text_changed(self) -> None:
        self._debounce.start()

    def _on_reset_filters(self) -> None:
        self.search_edit.clear()
        self.category_filter.setCurrentIndex(0)
        self.source_filter.setCurrentIndex(0)
        self.active_filter.setCurrentText("Active")
        self.refresh()

    def _render_page(self) -> None:
        total = len(self._all_records)
        max_page = max(1, math.ceil(total / self._page_size)) if self._page_size else 1
        self._page = min(max(1, self._page), max_page)
        start = (self._page - 1) * self._page_size
        self.table_model.set_records(self._all_records[start:start + self._page_size])
        self.pagination.update_state(total=total, page=self._page, page_size=self._page_size)

        if total == 0:
            needle = self.search_edit.text().strip()
            if needle or self.category_filter.currentText() != "All" or self.source_filter.currentText() != "All":
                self.table_stack.setCurrentWidget(self.no_results_widget)
            else:
                self.table_stack.setCurrentWidget(self.first_run_widget)
        else:
            self.table_stack.setCurrentIndex(0)
        self._update_buttons()

    def _on_page_requested(self, page: int) -> None:
        self._page = page
        self._render_page()

    def _on_page_size_changed(self, page_size: int) -> None:
        self._page_size = page_size
        self._page = 1
        self._render_page()

    # ----- Selection ----------------------------------------------------
    def _selected_record(self) -> Optional[dict[str, Any]]:
        current = self.table.currentIndex()
        if not current.isValid():
            return None
        return self.table_model.record_at(current.row())

    def _update_buttons(self) -> None:
        record = self._selected_record()
        has = record is not None
        self.duplicate_button.setEnabled(has)
        self.toggle_active_button.setEnabled(has)
        self.toggle_active_button.setText("Reactivate" if record and not record.get("is_active") else "Deactivate")

    # ----- Error banner ---------------------------------------------------
    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_banner.show()

    def _hide_error(self) -> None:
        self.error_banner.hide()

    # ----- Add / Edit / Duplicate / Deactivate ----------------------------
    def _new_resource_type(self) -> None:
        dialog = ResourceTypeEditorWindow(self.repository, parent=self)
        if dialog.exec() == ResourceTypeEditorWindow.DialogCode.Accepted:
            self._save_editor(dialog)

    def _edit_selected(self) -> None:
        record = self._selected_record()
        if not record:
            return
        resource_type = self.repository.get_resource_type(int(record["id"]))
        if resource_type is None:
            QMessageBox.warning(self, "Resource Type Library", "The selected resource type no longer exists.")
            self.refresh()
            return
        dialog = ResourceTypeEditorWindow(self.repository, resource_type, self)
        if dialog.exec() == ResourceTypeEditorWindow.DialogCode.Accepted:
            self._save_editor(dialog)

    def _save_editor(self, dialog: ResourceTypeEditorWindow) -> None:
        try:
            resource_type = dialog.to_model()
            components = dialog.components()
            resource_type_id = self.repository.save_resource_type(resource_type)
            self.repository.replace_components(resource_type_id, components)
            self.refresh()
            self._show_toast("Resource type saved", f"'{resource_type.name}' saved successfully.")
        except Exception as exc:
            QMessageBox.warning(self, "Resource Type Library", str(exc))

    def _clone_selected(self) -> None:
        record = self._selected_record()
        if not record:
            return
        try:
            self.repository.clone_resource_type(int(record["id"]))
            self.refresh()
            self._show_toast("Resource type duplicated", f"Duplicated '{record.get('name', '')}'.")
        except Exception as exc:
            QMessageBox.warning(self, "Resource Type Library", str(exc))

    def _toggle_selected_active(self) -> None:
        record = self._selected_record()
        if not record:
            return
        if record.get("is_active"):
            self.repository.deactivate_resource_type(int(record["id"]))
        else:
            self.repository.activate_resource_type(int(record["id"]))
        self.refresh()

    def _open_capability_manager(self) -> None:
        CapabilityManagerWindow(self.repository, self).exec()
        self.refresh()

    # ----- Import ------------------------------------------------------------
    def _import(self) -> None:
        def _import_row(payload: dict[str, Any]) -> Any:
            resource_type = ResourceType(
                name=payload["name"],
                planning_display_name=payload.get("planning_display_name", ""),
                category=payload.get("category") or "Other",
                source=payload.get("source") or "AHJ Custom",
                owner_agency=payload.get("owner_agency", ""),
                description=payload.get("description", ""),
                notes=payload.get("notes", ""),
            )
            return self.repository.save_resource_type(resource_type)

        wizard = ImportWizard(fields=FIELDS, import_row=_import_row, title="Import Resource Types", parent=self)
        result = wizard.exec()
        created = wizard.created_records()
        errors = wizard.error_count()
        if result == QDialog.DialogCode.Accepted and (created or errors):
            self.refresh()
            if created and errors:
                self._show_toast(
                    "Import complete", f"{len(created)} resource types imported with {errors} errors.", severity="warning"
                )
            elif created:
                self._show_toast("Import complete", f"Imported {len(created)} resource types.")
            elif errors:
                self._show_toast("Import issues", "No rows were imported. Check the error report.", severity="warning")

    # ----- Export ------------------------------------------------------------
    def _export(self) -> None:
        selection_model = self.table.selectionModel()
        allow_selected = bool(selection_model and selection_model.hasSelection())
        dialog = ExportDialog(fields=FIELDS, allow_selected=allow_selected, title="Export Resource Types", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        scope = dialog.selected_scope()
        file_format = dialog.selected_format()
        fields = dialog.selected_fields()

        if scope == "selected":
            rec = self._selected_record()
            if rec is None:
                QMessageBox.information(self, "No selection", "Select a row to export or choose a different scope.")
                return
            rows = [rec]
        else:
            rows = list(self._all_records)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path(tempfile.gettempdir()) / f"resource-types-{scope}-{timestamp}.{file_format}"

        def _task() -> dict[str, Any]:
            write_export_file(path, rows, fields, _FIELD_LABELS, file_format)
            return {"path": str(path), "count": len(rows)}

        self.export_button.setEnabled(False)
        run_async(self, _task, self._on_export_done, self._on_export_failed)

    def _on_export_done(self, result: dict[str, Any]) -> None:
        self.export_button.setEnabled(True)
        message = f"{result.get('count', 0)} resource types exported. Saved to {result.get('path')}."
        self._show_toast("Export ready", message)
        QMessageBox.information(self, "Export ready", message)

    def _on_export_failed(self, message: str) -> None:
        self.export_button.setEnabled(True)
        self._show_toast("Export failed", message, severity="error")
        QMessageBox.critical(self, "Export failed", message)

    # ----- Toast helper ------------------------------------------------------
    def _show_toast(self, title: str, message: str, *, severity: str = "success") -> None:
        try:
            self._notifier.notify(
                Notification(
                    title=title,
                    message=message,
                    severity=severity if severity in {"info", "success", "warning", "error"} else "info",
                    source="Resource Type Library",
                )
            )
        except Exception:
            pass


def open_resource_type_library(parent: Optional[QWidget] = None) -> ResourceTypeLibraryWindow:
    """Open a modeless Resource Type Library window and keep it referenced.

    Main-menu code can call this helper later without duplicating construction
    and lifetime-management details.  When a parent is provided, the window is
    stored on the parent to prevent Python garbage collection from closing it.
    Subsequent calls raise the existing window instead of opening a duplicate.
    """

    existing = getattr(parent, "_resource_type_library_window", None) if parent is not None else None
    if isinstance(existing, ResourceTypeLibraryWindow) and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return existing

    window = ResourceTypeLibraryWindow(parent=parent)
    if parent is not None:
        setattr(parent, "_resource_type_library_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window
