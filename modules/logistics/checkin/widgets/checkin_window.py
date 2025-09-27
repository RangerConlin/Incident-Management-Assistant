"""QtWidgets implementation of the streamlined Logistics Check-In window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..services import CheckInService, EntityConfig, iter_entity_configs


class NewRecordDialog(QDialog):
    """Collect the fields required to create a new master record."""

    def __init__(self, service: CheckInService, config: EntityConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(f"New {config.title}")
        self._service = service
        self._config = config
        self._id_input: Optional[QLineEdit] = None
        self._inputs: Dict[str, QLineEdit] = {}
        self.created_record: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        if config.id_field is not None:
            id_edit = QLineEdit(self)
            id_edit.setObjectName(f"Input{config.id_column.title()}Id")
            if config.id_field.placeholder:
                id_edit.setPlaceholderText(config.id_field.placeholder)
            form.addRow(config.id_field.label, id_edit)
            self._id_input = id_edit
        elif config.autoincrement:
            note = QLabel("Identifier will be assigned automatically.", self)
            note.setObjectName("LblAutoIdNote")
            form.addRow("Identifier", note)

        for field in config.form_fields:
            edit = QLineEdit(self)
            edit.setObjectName(f"Input{field.name.title()}")
            if field.placeholder:
                edit.setPlaceholderText(field.placeholder)
            form.addRow(field.label, edit)
            self._inputs[field.name] = edit

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _collect_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self._id_input is not None:
            payload[self._config.id_column] = self._id_input.text().strip()
        for name, widget in self._inputs.items():
            payload[name] = widget.text().strip()
        return payload

    def accept(self) -> None:  # pragma: no cover - exercised via UI events
        try:
            record = self._service.create_master_record(self._config.key, self._collect_payload())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Input", str(exc), QMessageBox.Ok)
            return
        self.created_record = record
        super().accept()


class EntityTab(QWidget):
    """Widget that searches master records for a single entity type."""

    def __init__(
        self, config: EntityConfig, service: CheckInService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.service = service
        self._records: List[Dict[str, Any]] = []
        self._current_record: Optional[Dict[str, Any]] = None
        self._field_placeholders: Dict[str, Optional[str]] = {
            field.name: field.placeholder for field in config.form_fields if field.placeholder
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        search_layout = QHBoxLayout()
        search_label = QLabel("Search", self)
        search_layout.addWidget(search_label)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(
            f"Search {config.title.lower()} by name, ID, or keyword"
        )
        self.search_edit.setObjectName("SearchBox")
        self.search_edit.returnPressed.connect(self._on_search_requested)
        search_layout.addWidget(self.search_edit, 1)
        self.btn_search = QPushButton("Search", self)
        self.btn_search.setObjectName("BtnSearch")
        self.btn_search.clicked.connect(self._on_search_requested)
        search_layout.addWidget(self.btn_search)
        layout.addLayout(search_layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(config.display_columns) + 1)
        headers = [title for _, title in config.display_columns] + ["Checked In"]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        preview_group = QGroupBox("Preview & Edit", self)
        preview_group.setObjectName("GrpPreview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(8)

        self.preview_placeholder = QLabel(
            "Search for a record, then select a result to preview and edit it before check-in.",
            preview_group,
        )
        self.preview_placeholder.setObjectName("LblPreviewPlaceholder")
        self.preview_placeholder.setWordWrap(True)
        preview_layout.addWidget(self.preview_placeholder)

        self.preview_form_widget = QWidget(preview_group)
        self.preview_form = QFormLayout(self.preview_form_widget)
        self.preview_form.setContentsMargins(0, 0, 0, 0)
        self.preview_fields: Dict[str, QLineEdit] = {}
        for column_name, label, editable in self._preview_columns():
            edit = QLineEdit(self.preview_form_widget)
            edit.setObjectName(f"Preview{column_name.title()}Value")
            edit.setReadOnly(not editable)
            placeholder = self._field_placeholders.get(column_name)
            if placeholder:
                edit.setPlaceholderText(placeholder)
            self.preview_form.addRow(label, edit)
            self.preview_fields[column_name] = edit
        preview_layout.addWidget(self.preview_form_widget)
        self.preview_form_widget.hide()

        layout.addWidget(preview_group)

        button_bar = QHBoxLayout()
        button_bar.addStretch(1)
        self.btn_check_in = QPushButton("Check In", self)
        self.btn_check_in.setObjectName("BtnCheckIn")
        self.btn_check_in.setEnabled(False)
        self.btn_check_in.clicked.connect(self._check_in)
        self.btn_add = QPushButton(f"Add {config.title}", self)
        self.btn_add.setObjectName("BtnAddMaster")
        self.btn_add.clicked.connect(self._add_new)
        button_bar.addWidget(self.btn_check_in)
        button_bar.addWidget(self.btn_add)
        layout.addLayout(button_bar)

        self._clear_preview()

    def refresh(self, *, select_id: Optional[str] = None) -> None:
        self._run_search(select_id=select_id)

    def _preview_columns(self) -> List[Tuple[str, str, bool]]:
        columns: List[Tuple[str, str, bool]] = []
        seen: set[str] = set()

        id_label = next(
            (title for column, title in self.config.display_columns if column == self.config.id_column),
            self.config.id_column.replace("_", " ").title(),
        )
        columns.append((self.config.id_column, id_label, False))
        seen.add(self.config.id_column)

        for column_name, title in self.config.display_columns:
            if column_name in seen:
                continue
            columns.append((column_name, title, True))
            seen.add(column_name)

        for field in self.config.form_fields:
            if field.name in seen:
                continue
            columns.append((field.name, field.label, True))
            seen.add(field.name)

        return columns

    def _on_search_requested(self) -> None:  # pragma: no cover - UI signal
        self._run_search()

    def _run_search(self, *, select_id: Optional[str] = None) -> None:
        query = self.search_edit.text().strip()
        if not query:
            self._records = []
            self._populate_table(select_id=None)
            return
        try:
            results = self.service.search_master_records(self.config.key, query)
        except ValueError as exc:
            QMessageBox.warning(self, "Search Failed", str(exc), QMessageBox.Ok)
            return
        self._records = results
        self._populate_table(select_id=select_id)

    def _populate_table(self, *, select_id: Optional[str]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._records))
        for row_index, record in enumerate(self._records):
            identifier = str(record.get(self.config.id_column, ""))
            for col_index, (column_name, _) in enumerate(self.config.display_columns):
                value = record.get(column_name)
                text = "—" if value in (None, "") else str(value)
                item = QTableWidgetItem(text)
                if col_index == 0:
                    item.setData(Qt.UserRole, identifier)
                self.table.setItem(row_index, col_index, item)
            status_item = QTableWidgetItem("Yes" if record.get("_checked_in") else "No")
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_index, len(self.config.display_columns), status_item)
        self.table.blockSignals(False)

        target_row = -1
        if select_id is not None:
            target_row = self._row_for_identifier(select_id)
        if target_row >= 0:
            self.table.selectRow(target_row)
        else:
            self.table.clearSelection()
        self._on_selection_changed()

    def _row_for_identifier(self, identifier: str) -> int:
        target = str(identifier)
        for index, record in enumerate(self._records):
            value = record.get(self.config.id_column)
            if str(value) == target:
                return index
        return -1

    def _selected_identifier(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        identifier = self._records[row].get(self.config.id_column)
        return str(identifier) if identifier is not None else None

    def _on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._records):
            self._current_record = None
            self.btn_check_in.setEnabled(False)
            self._clear_preview()
            return
        self._current_record = self._records[row]
        self.btn_check_in.setEnabled(True)
        self._load_preview(self._current_record)

    def _load_preview(self, record: Dict[str, Any]) -> None:
        self.preview_placeholder.hide()
        self.preview_form_widget.show()
        for name, widget in self.preview_fields.items():
            value = record.get(name)
            widget.setText("" if value in (None, "") else str(value))

    def _clear_preview(self) -> None:
        self.preview_form_widget.hide()
        self.preview_placeholder.show()
        for widget in self.preview_fields.values():
            widget.clear()
        self._current_record = None

    def _collect_overrides(self) -> Dict[str, Any]:
        if self._current_record is None:
            return {}
        overrides: Dict[str, Any] = {}
        for name, widget in self.preview_fields.items():
            if name == self.config.id_column:
                continue
            new_text = widget.text()
            new_value: Any = None if new_text == "" else new_text
            original_value = self._current_record.get(name)
            original_text = "" if original_value in (None, "") else str(original_value)
            if new_text == original_text:
                continue
            overrides[name] = new_value
        return overrides

    def _describe_record(self, record: Dict[str, Any]) -> str:
        for column_name, _ in self.config.display_columns:
            if column_name == self.config.id_column:
                continue
            value = record.get(column_name)
            if value:
                return str(value)
        identifier = record.get(self.config.id_column)
        return str(identifier) if identifier is not None else self.config.title

    def _check_in(self) -> None:  # pragma: no cover - exercised via UI events
        record_id = self._selected_identifier()
        if not record_id:
            QMessageBox.information(self, "Select Record", "Choose an entry to check in.")
            return
        overrides = self._collect_overrides()
        try:
            record = self.service.check_in(
                self.config.key, record_id, overrides=overrides if overrides else None
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Check-In Failed", str(exc), QMessageBox.Ok)
            return
        description = self._describe_record(record)
        if overrides:
            message = f"{description} was updated and checked into the incident."
        else:
            message = f"{description} is now part of the active incident."
        QMessageBox.information(self, "Checked In", message)
        row_index = self._row_for_identifier(record_id)
        if row_index >= 0:
            self._records[row_index] = record
        self._current_record = record
        self._populate_table(select_id=str(record.get(self.config.id_column, "")))

    def _add_new(self) -> None:  # pragma: no cover - exercised via UI events
        dialog = NewRecordDialog(self.service, self.config, self)
        if dialog.exec() != QDialog.Accepted or dialog.created_record is None:
            return
        record = dialog.created_record
        record_id = str(record.get(self.config.id_column, ""))
        try:
            record = self.service.check_in(self.config.key, record_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Check-In Failed", str(exc), QMessageBox.Ok)
        else:
            description = self._describe_record(record)
            QMessageBox.information(
                self,
                "Record Added",
                f"{description} was added to the master list and checked into the incident.",
            )
        if record_id:
            self.search_edit.setText(record_id)
        self._run_search(select_id=record_id if record_id else None)


class CheckInWindow(QWidget):
    """Main window that exposes tabs for personnel, vehicles, equipment, and aircraft."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CheckInWindow")
        self.setWindowTitle("Incident Check-In")
        self.service = CheckInService()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        intro = QLabel(
            "Search the master registry, preview results, and copy them into the active incident database.",
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("TabsEntities")
        layout.addWidget(self.tabs, 1)

        for config in iter_entity_configs():
            tab = EntityTab(config, self.service, self)
            self.tabs.addTab(tab, config.title)

    def refresh_all(self) -> None:
        """Refresh all tabs from the underlying databases."""

        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, EntityTab):
                widget.refresh()


__all__ = ["CheckInWindow"]
