"""List window for Resource Packages (Stage 3).

name / organization / resource kind (linked Resource Type Library entry,
when set) / personnel count / vehicle+asset count / active status, with
create/edit/duplicate/archive/inspect actions.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..data.repository import ApiResourcePackageRepository
from ..models import ResourcePackage
from .resource_package_editor_window import ResourcePackageEditorWindow

_COLUMNS = ["Name", "Organization", "Default Designation", "Personnel", "Vehicles/Assets", "Active"]


class ResourcePackageListWindow(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resource Packages")
        self.resize(1000, 640)
        self.repository = ApiResourcePackageRepository()
        self._packages: list[ResourcePackage] = []

        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search name, organization, designation…")
        self.active_combo = QComboBox()
        self.active_combo.addItems(["Active", "Inactive", "All"])
        filters.addWidget(QLabel("Search:"))
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(QLabel("Status:"))
        filters.addWidget(self.active_combo)
        layout.addLayout(filters)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.new_button = QPushButton("New Package…")
        self.edit_button = QPushButton("Edit…")
        self.duplicate_button = QPushButton("Duplicate")
        self.archive_button = QPushButton("Archive/Activate")
        actions.addWidget(self.new_button)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.duplicate_button)
        actions.addWidget(self.archive_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.search_edit.textChanged.connect(self.reload)
        self.active_combo.currentIndexChanged.connect(self.reload)
        self.new_button.clicked.connect(self._new_package)
        self.edit_button.clicked.connect(self._edit_selected)
        self.duplicate_button.clicked.connect(self._duplicate_selected)
        self.archive_button.clicked.connect(self._toggle_active_selected)
        self.table.itemDoubleClicked.connect(lambda *_: self._edit_selected())

        self.reload()

    def reload(self) -> None:
        try:
            self._packages = self.repository.list_packages(
                search=self.search_edit.text(),
                active_filter=self.active_combo.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Resource Packages", f"Failed to load packages: {exc}")
            self._packages = []
        self.table.setRowCount(len(self._packages))
        for row, pkg in enumerate(self._packages):
            values = [
                pkg.name,
                pkg.owning_organization,
                pkg.default_team_designation,
                str(pkg.personnel_count),
                str(pkg.asset_count),
                "Yes" if pkg.is_active else "No",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, pkg.id)
                self.table.setItem(row, col, item)

    def _selected_package(self) -> Optional[ResourcePackage]:
        sel = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        row = sel[0].row() if sel else self.table.currentRow()
        if row is None or row < 0 or row >= len(self._packages):
            return None
        return self._packages[row]

    def _new_package(self) -> None:
        dialog = ResourcePackageEditorWindow(self.repository, None, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.repository.save_package(dialog.to_model())
        except Exception as exc:
            QMessageBox.warning(self, "Resource Packages", f"Failed to save package: {exc}")
            return
        self.reload()

    def _edit_selected(self) -> None:
        pkg = self._selected_package()
        if pkg is None or pkg.id is None:
            return
        full = self.repository.get_package(pkg.id)
        if full is None:
            QMessageBox.warning(self, "Resource Packages", "That package could not be loaded.")
            return
        dialog = ResourcePackageEditorWindow(self.repository, full, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.repository.save_package(dialog.to_model())
        except Exception as exc:
            QMessageBox.warning(self, "Resource Packages", f"Failed to save package: {exc}")
            return
        self.reload()

    def _duplicate_selected(self) -> None:
        pkg = self._selected_package()
        if pkg is None or pkg.id is None:
            return
        try:
            self.repository.duplicate_package(pkg.id)
        except Exception as exc:
            QMessageBox.warning(self, "Resource Packages", f"Failed to duplicate package: {exc}")
            return
        self.reload()

    def _toggle_active_selected(self) -> None:
        pkg = self._selected_package()
        if pkg is None or pkg.id is None:
            return
        try:
            self.repository.set_active(pkg.id, not pkg.is_active)
        except Exception as exc:
            QMessageBox.warning(self, "Resource Packages", f"Failed to update package: {exc}")
            return
        self.reload()


_open_windows: list[ResourcePackageListWindow] = []


def open_resource_package_library(parent: Optional[QWidget] = None) -> ResourcePackageListWindow:
    window = ResourcePackageListWindow(parent=parent)
    window.show()
    _open_windows.append(window)

    def _cleanup() -> None:
        try:
            _open_windows.remove(window)
        except ValueError:
            pass

    window.destroyed.connect(lambda *_: _cleanup())
    return window
