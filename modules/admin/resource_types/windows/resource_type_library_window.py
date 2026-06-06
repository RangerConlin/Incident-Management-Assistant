"""QtWidgets admin window for the Resource Type Library."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..data.resource_type_repository import ResourceTypeRepository
from ..models.resource_type_models import RESOURCE_CATEGORIES, RESOURCE_SOURCES
from .capability_manager_window import CapabilityManagerWindow
from .resource_type_editor_window import ResourceTypeEditorWindow


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
            if key == "is_kit_cache":
                count = int(record.get("component_count") or 0)
                if record.get("is_kit_cache"):
                    return f"Yes ({count})" if count else "Yes"
                return "No"
            if key == "is_active":
                return "Yes" if record.get(key) else "No"
            return record.get(key, "")
        if role == Qt.ToolTipRole and key == "capabilities":
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
        repository: Optional[ResourceTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository or ResourceTypeRepository()
        self.setWindowTitle("Resource Type Library")
        self.resize(1120, 680)

        # Filters are grouped at the top so users can narrow a large library
        # without opening a separate advanced-search dialog.
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Search name, display name, aliases, category, capabilities, agency, or FEMA/NIMS mapping..."
        )
        self.category_filter = QComboBox()
        self.category_filter.addItems(("All",) + RESOURCE_CATEGORIES)
        self.source_filter = QComboBox()
        self.source_filter.addItems(("All",) + RESOURCE_SOURCES)
        self.active_filter = QComboBox()
        self.active_filter.addItems(("Active", "Inactive", "All"))

        self.table_model = ResourceTypeTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._edit_selected)

        new_button = QPushButton("New")
        edit_button = QPushButton("Edit")
        clone_button = QPushButton("Clone")
        self.toggle_active_button = QPushButton("Deactivate")
        refresh_button = QPushButton("Refresh")
        capability_button = QPushButton("Capability Manager")
        close_button = QPushButton("Close")

        new_button.clicked.connect(self._new_resource_type)
        edit_button.clicked.connect(self._edit_selected)
        clone_button.clicked.connect(self._clone_selected)
        self.toggle_active_button.clicked.connect(self._toggle_selected_active)
        refresh_button.clicked.connect(self.refresh)
        capability_button.clicked.connect(self._open_capability_manager)
        close_button.clicked.connect(self.close)

        self.search_edit.textChanged.connect(self.refresh)
        self.category_filter.currentTextChanged.connect(self.refresh)
        self.source_filter.currentTextChanged.connect(self.refresh)
        self.active_filter.currentTextChanged.connect(self.refresh)
        self.table.selectionModel().selectionChanged.connect(self._update_toggle_button)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.search_edit, 2)
        filters.addWidget(QLabel("Category"))
        filters.addWidget(self.category_filter)
        filters.addWidget(QLabel("Source"))
        filters.addWidget(self.source_filter)
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self.active_filter)

        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(edit_button)
        actions.addWidget(clone_button)
        actions.addWidget(self.toggle_active_button)
        actions.addWidget(refresh_button)
        actions.addStretch()
        actions.addWidget(capability_button)
        actions.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.table)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        """Reload the main table using the visible filter controls."""

        self.table_model.set_records(
            self.repository.list_resource_types(
                search_text=self.search_edit.text(),
                category=self.category_filter.currentText(),
                source=self.source_filter.currentText(),
                active_filter=self.active_filter.currentText(),
            )
        )
        self._update_toggle_button()

    def _selected_record(self) -> Optional[dict[str, Any]]:
        current = self.table.currentIndex()
        if not current.isValid():
            return None
        return self.table_model.record_at(current.row())

    def _new_resource_type(self) -> None:
        dialog = ResourceTypeEditorWindow(self.repository, parent=self)
        if dialog.exec() == ResourceTypeEditorWindow.Accepted:
            self._save_editor(dialog)

    def _edit_selected(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Resource Type Library", "Select a resource type to edit.")
            return
        resource_type = self.repository.get_resource_type(int(record["id"]))
        if resource_type is None:
            QMessageBox.warning(self, "Resource Type Library", "The selected resource type no longer exists.")
            self.refresh()
            return
        dialog = ResourceTypeEditorWindow(self.repository, resource_type, self)
        if dialog.exec() == ResourceTypeEditorWindow.Accepted:
            self._save_editor(dialog)

    def _save_editor(self, dialog: ResourceTypeEditorWindow) -> None:
        try:
            resource_type = dialog.to_model()
            components = dialog.components()
            resource_type_id = self.repository.save_resource_type(resource_type)
            self.repository.replace_components(resource_type_id, components)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Resource Type Library", str(exc))

    def _clone_selected(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Resource Type Library", "Select a resource type to clone.")
            return
        try:
            new_id = self.repository.clone_resource_type(int(record["id"]))
            self.refresh()
            QMessageBox.information(
                self,
                "Resource Type Library",
                f"Cloned resource type. New record ID: {new_id}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Resource Type Library", str(exc))

    def _toggle_selected_active(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Resource Type Library", "Select a resource type first.")
            return
        if record.get("is_active"):
            self.repository.deactivate_resource_type(int(record["id"]))
        else:
            self.repository.activate_resource_type(int(record["id"]))
        self.refresh()

    def _open_capability_manager(self) -> None:
        CapabilityManagerWindow(self.repository, self).exec()
        self.refresh()

    def _update_toggle_button(self) -> None:
        record = self._selected_record()
        if record and not record.get("is_active"):
            self.toggle_active_button.setText("Reactivate")
        else:
            self.toggle_active_button.setText("Deactivate")


def open_resource_type_library(parent: Optional[QWidget] = None) -> ResourceTypeLibraryWindow:
    """Open a modeless Resource Type Library window and keep it referenced.

    Main-menu code can call this helper later without duplicating construction
    and lifetime-management details.  When a parent is provided, the window is
    stored on the parent to prevent Python garbage collection from closing it.
    """

    window = ResourceTypeLibraryWindow(parent=parent)
    if parent is not None:
        setattr(parent, "_resource_type_library_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window
