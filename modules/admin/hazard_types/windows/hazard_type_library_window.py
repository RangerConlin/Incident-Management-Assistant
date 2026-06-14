"""QtWidgets admin window for the Hazard Type Library."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..data.hazard_type_repository import ApiHazardTypeRepository
from ..models.hazard_type_models import HAZARD_CATEGORIES, HAZARD_RISK_LEVELS, HAZARD_SOURCES
from .hazard_type_editor_window import HazardTypeEditorWindow


class HazardTypeTableModel(QAbstractTableModel):
    """Table model for the main Hazard Type Library browser."""

    headers = [
        "Name",
        "Display Name",
        "Category",
        "Source",
        "Default Risk",
        "Default PPE",
        "Default Mitigations Count",
        "Active",
        "Updated At",
    ]
    keys = [
        "name",
        "display_name",
        "category",
        "source",
        "default_risk_level",
        "ppe_preview",
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
        if role == Qt.ToolTipRole and key == "ppe_preview":
            return record.get("ppe_preview", "")
        return None

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def record_at(self, row: int) -> Optional[dict[str, Any]]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


class HazardTypeLibraryWindow(QWidget):
    """Standalone modeless admin window for hazard type master data."""

    def __init__(
        self,
        repository: Optional[ApiHazardTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, Qt.Window)
        self.repository = repository or ApiHazardTypeRepository()
        self.setWindowTitle("Hazard Type Library")
        self.resize(1200, 760)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Search name, display name, aliases, category, source, mitigations, PPE, notes, or safety message..."
        )
        self.category_filter = QComboBox()
        self.category_filter.addItems(("All",) + HAZARD_CATEGORIES)
        self.source_filter = QComboBox()
        self.source_filter.addItems(("All",) + HAZARD_SOURCES)
        self.risk_filter = QComboBox()
        self.risk_filter.addItems(("All",) + HAZARD_RISK_LEVELS)
        self.active_filter = QComboBox()
        self.active_filter.addItems(("Active", "Inactive", "All"))

        self.table_model = HazardTypeTableModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(60)
        self.table.doubleClicked.connect(self._edit_selected)

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText("Select a hazard type to preview description, controls, PPE, and references.")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.preview_edit)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)

        new_button = QPushButton("New")
        edit_button = QPushButton("Edit")
        clone_button = QPushButton("Clone")
        self.toggle_active_button = QPushButton("Deactivate")
        refresh_button = QPushButton("Refresh")
        close_button = QPushButton("Close")

        new_button.clicked.connect(self._new_hazard_type)
        edit_button.clicked.connect(self._edit_selected)
        clone_button.clicked.connect(self._clone_selected)
        self.toggle_active_button.clicked.connect(self._toggle_selected_active)
        refresh_button.clicked.connect(self.refresh)
        close_button.clicked.connect(self.close)

        self.search_edit.textChanged.connect(self.refresh)
        self.category_filter.currentTextChanged.connect(self.refresh)
        self.source_filter.currentTextChanged.connect(self.refresh)
        self.risk_filter.currentTextChanged.connect(self.refresh)
        self.active_filter.currentTextChanged.connect(self.refresh)
        self.table.selectionModel().selectionChanged.connect(self._update_selection_state)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search"))
        filters.addWidget(self.search_edit, 2)
        filters.addWidget(QLabel("Category"))
        filters.addWidget(self.category_filter)
        filters.addWidget(QLabel("Source"))
        filters.addWidget(self.source_filter)
        filters.addWidget(QLabel("Risk"))
        filters.addWidget(self.risk_filter)
        filters.addWidget(QLabel("Status"))
        filters.addWidget(self.active_filter)

        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(edit_button)
        actions.addWidget(clone_button)
        actions.addWidget(self.toggle_active_button)
        actions.addWidget(refresh_button)
        actions.addStretch()
        actions.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(splitter)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        self.table_model.set_records(
            self.repository.list_hazard_types(
                {
                    "search_text": self.search_edit.text(),
                    "category": self.category_filter.currentText(),
                    "source": self.source_filter.currentText(),
                    "risk_level": self.risk_filter.currentText(),
                    "active_filter": self.active_filter.currentText(),
                }
            )
        )
        self._update_selection_state()

    def _selected_record(self) -> Optional[dict[str, Any]]:
        current = self.table.currentIndex()
        if not current.isValid():
            return None
        source_index = self.proxy_model.mapToSource(current)
        return self.table_model.record_at(source_index.row())

    def _new_hazard_type(self) -> None:
        dialog = HazardTypeEditorWindow(self.repository, parent=self)
        if dialog.exec() == HazardTypeEditorWindow.Accepted:
            self._save_editor(dialog)

    def _edit_selected(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Hazard Type Library", "Select a hazard type to edit.")
            return
        hazard_type = self.repository.get_hazard_type(int(record["id"]))
        if hazard_type is None:
            QMessageBox.warning(self, "Hazard Type Library", "The selected hazard type no longer exists.")
            self.refresh()
            return
        dialog = HazardTypeEditorWindow(self.repository, hazard_type, self)
        if dialog.exec() == HazardTypeEditorWindow.Accepted:
            self._save_editor(dialog)

    def _save_editor(self, dialog: HazardTypeEditorWindow) -> None:
        try:
            hazard = dialog.to_model()
            if hazard.id is None:
                self.repository.create_hazard_type(hazard)
            else:
                self.repository.update_hazard_type(hazard.id, hazard)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))

    def _clone_selected(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Hazard Type Library", "Select a hazard type to clone.")
            return
        try:
            new_id = self.repository.clone_hazard_type(int(record["id"]))
            self.refresh()
            QMessageBox.information(
                self,
                "Hazard Type Library",
                f"Cloned hazard type. New record ID: {new_id}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Hazard Type Library", str(exc))

    def _toggle_selected_active(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Hazard Type Library", "Select a hazard type first.")
            return
        if record.get("is_active"):
            self.repository.deactivate_hazard_type(int(record["id"]))
        else:
            self.repository.reactivate_hazard_type(int(record["id"]))
        self.refresh()

    def _update_selection_state(self) -> None:
        record = self._selected_record()
        if record and not record.get("is_active"):
            self.toggle_active_button.setText("Reactivate")
        else:
            self.toggle_active_button.setText("Deactivate")
        self._refresh_preview(record)

    def _refresh_preview(self, record: Optional[dict[str, Any]]) -> None:
        if not record:
            self.preview_edit.clear()
            return
        hazard = self.repository.get_hazard_type(int(record["id"]))
        if hazard is None:
            self.preview_edit.clear()
            return
        mitigations = "\n".join(f"- {item.mitigation_text}" for item in hazard.mitigations) or "-"
        references = "\n".join(
            f"- {item.title}: {item.url_or_path}".rstrip(": ")
            for item in hazard.references
        ) or "-"
        preview = "\n".join(
            [
                f"Description:\n{hazard.description or '-'}",
                "",
                f"Default control measure:\n{hazard.default_control_measure or '-'}",
                "",
                f"Default PPE:\n{hazard.default_ppe or '-'}",
                "",
                f"Safety message:\n{hazard.default_safety_message or '-'}",
                "",
                f"Mitigations:\n{mitigations}",
                "",
                f"References:\n{references}",
            ]
        )
        self.preview_edit.setPlainText(preview)


def open_hazard_type_library(parent: Optional[QWidget] = None) -> HazardTypeLibraryWindow:
    """Open a modeless Hazard Type Library window and keep it referenced."""

    existing = getattr(parent, "_hazard_type_library_window", None) if parent is not None else None
    if isinstance(existing, HazardTypeLibraryWindow) and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return existing

    window = HazardTypeLibraryWindow(parent=parent)
    if parent is not None:
        setattr(parent, "_hazard_type_library_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window
