"""QtWidgets capability manager for Resource Type Library tags."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..data.resource_type_io import export_capabilities_csv, import_capabilities_csv
from ..data.resource_type_repository import ApiResourceTypeRepository, ResourceTypeRepository
from ..models.resource_type_models import ResourceCapability


class CapabilityEditorDialog(QDialog):
    """Small form used for both creating and editing a capability tag."""

    def __init__(self, capability: Optional[dict[str, Any]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capability")
        self.capability_id = int(capability["id"]) if capability else None

        self.name_edit = QLineEdit(capability.get("name", "") if capability else "")
        self.category_edit = QLineEdit(capability.get("category", "") if capability else "")
        self.description_edit = QTextEdit(capability.get("description", "") if capability else "")
        self.aliases_edit = QLineEdit(capability.get("aliases", "") if capability else "")
        self.notes_edit = QTextEdit(capability.get("notes", "") if capability else "")
        self.active_check = QCheckBox("Active")
        self.active_check.setChecked(bool(capability.get("is_active", 1)) if capability else True)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Category", self.category_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Aliases (; separated)", self.aliases_edit)
        form.addRow("Notes", self.notes_edit)
        form.addRow("Status", self.active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_then_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def to_model(self) -> ResourceCapability:
        """Convert the form into the repository dataclass."""

        return ResourceCapability(
            id=self.capability_id,
            name=self.name_edit.text(),
            category=self.category_edit.text(),
            description=self.description_edit.toPlainText(),
            aliases=[item.strip() for item in self.aliases_edit.text().split(";")],
            is_active=self.active_check.isChecked(),
            notes=self.notes_edit.toPlainText(),
        )

    def _validate_then_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Capability", "Name is required.")
            return
        self.accept()


class CapabilityManagerWindow(QDialog):
    """Search, create, edit, deactivate, and reactivate capability tags."""

    headers = ["Name", "Category", "Aliases", "Active", "Updated At"]

    def __init__(
        self,
        repository: Optional[ResourceTypeRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository or ApiResourceTypeRepository()
        self.setWindowTitle("Capability Manager")
        self.resize(760, 480)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search capabilities, aliases, descriptions, or notes...")
        self.include_inactive_check = QCheckBox("Include inactive")

        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(60)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.doubleClicked.connect(self._edit_selected)

        new_button = QPushButton("New")
        edit_button = QPushButton("Edit")
        self.toggle_active_button = QPushButton("Deactivate")
        import_button = QPushButton("Import CSV…")
        export_button = QPushButton("Export CSV…")
        close_button = QPushButton("Close")

        new_button.clicked.connect(self._new_capability)
        edit_button.clicked.connect(self._edit_selected)
        self.toggle_active_button.clicked.connect(self._toggle_selected_active)
        import_button.clicked.connect(self._import_csv)
        export_button.clicked.connect(self._export_csv)
        close_button.clicked.connect(self.accept)
        self.search_edit.textChanged.connect(self.refresh)
        self.include_inactive_check.toggled.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._update_toggle_button)

        filters = QHBoxLayout()
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(self.include_inactive_check)

        actions = QHBoxLayout()
        actions.addWidget(new_button)
        actions.addWidget(edit_button)
        actions.addWidget(self.toggle_active_button)
        actions.addWidget(import_button)
        actions.addWidget(export_button)
        actions.addStretch()
        actions.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.table)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        """Reload the table from the repository using the current filters."""

        rows = self.repository.list_capabilities(
            self.search_edit.text(), self.include_inactive_check.isChecked()
        )
        self.table.setRowCount(0)
        for capability in rows:
            table_row = self.table.rowCount()
            self.table.insertRow(table_row)
            values = [
                capability.get("name", ""),
                capability.get("category", ""),
                capability.get("aliases", ""),
                "Yes" if capability.get("is_active") else "No",
                capability.get("updated_at", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if column == 0:
                    item.setData(Qt.UserRole, capability)
                self.table.setItem(table_row, column, item)
        self._update_toggle_button()

    def _selected_capability(self) -> Optional[dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _new_capability(self) -> None:
        dialog = CapabilityEditorDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._save_dialog(dialog)

    def _edit_selected(self) -> None:
        capability = self._selected_capability()
        if not capability:
            QMessageBox.information(self, "Capability Manager", "Select a capability to edit.")
            return
        dialog = CapabilityEditorDialog(capability, self)
        if dialog.exec() == QDialog.Accepted:
            self._save_dialog(dialog)

    def _save_dialog(self, dialog: CapabilityEditorDialog) -> None:
        try:
            self.repository.save_capability(dialog.to_model())
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Capability Manager", str(exc))

    def _toggle_selected_active(self) -> None:
        capability = self._selected_capability()
        if not capability:
            QMessageBox.information(self, "Capability Manager", "Select a capability first.")
            return
        capability_id = int(capability["id"])
        if capability.get("is_active"):
            self.repository.deactivate_capability(capability_id)
        else:
            self.repository.activate_capability(capability_id)
        self.refresh()

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Capabilities", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            result = import_capabilities_csv(self.repository, path)
            self.refresh()
            _show_import_result(self, "Import Capabilities", result)
        except Exception as exc:
            QMessageBox.critical(self, "Import Capabilities", f"Import failed:\n{exc}")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Capabilities", "resource_capabilities.csv", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            count = export_capabilities_csv(self.repository, path)
            QMessageBox.information(
                self, "Export Capabilities", f"Exported {count} capability record(s) to:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Capabilities", f"Export failed:\n{exc}")

    def _update_toggle_button(self) -> None:
        capability = self._selected_capability()
        if capability and not capability.get("is_active"):
            self.toggle_active_button.setText("Reactivate")
        else:
            self.toggle_active_button.setText("Deactivate")


def _show_import_result(parent: QWidget, title: str, result: dict[str, Any]) -> None:
    """Show a summary of an import operation. Errors are scrollable."""

    inserted = result.get("inserted", 0)
    updated = result.get("updated", 0)
    errors = result.get("errors", [])
    summary = f"Inserted: {inserted}   Updated: {updated}   Warnings/errors: {len(errors)}"
    if not errors:
        QMessageBox.information(parent, title, summary)
        return

    dialog = QWidget(parent, Qt.Window)
    dialog.setWindowTitle(title)
    dialog.resize(640, 420)
    body = QTextEdit()
    body.setReadOnly(True)
    body.setPlainText(summary + "\n\n" + "\n".join(errors))
    scroll = QScrollArea()
    scroll.setWidget(body)
    scroll.setWidgetResizable(True)
    close_button = QPushButton("Close")
    close_button.clicked.connect(dialog.close)

    layout = QVBoxLayout(dialog)
    layout.addWidget(scroll)
    layout.addWidget(close_button)
    dialog.show()
