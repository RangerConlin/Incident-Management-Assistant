"""QtWidgets implementation of the streamlined Logistics Check-In window."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
    """Widget that lists master records for a single entity type."""

    def __init__(self, config: EntityConfig, service: CheckInService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config = config
        self.service = service
        self._records: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        search_layout = QHBoxLayout()
        search_label = QLabel("Search", self)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Type to filter records")
        self.search_edit.textChanged.connect(self._apply_filter)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
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
        layout.addWidget(self.table, 1)

        button_bar = QHBoxLayout()
        button_bar.addStretch(1)
        self.btn_check_in = QPushButton("Check In", self)
        self.btn_check_in.clicked.connect(self._check_in)
        self.btn_add = QPushButton(f"Add {config.title}", self)
        self.btn_add.clicked.connect(self._add_new)
        button_bar.addWidget(self.btn_check_in)
        button_bar.addWidget(self.btn_add)
        layout.addLayout(button_bar)

        self.refresh()

    def refresh(self, *, select_id: Optional[str] = None) -> None:
        self._records = self.service.list_master_records(self.config.key)
        self._apply_filter(select_id=select_id)

    def _apply_filter(self, _text: str | None = None, *, select_id: Optional[str] = None) -> None:
        needle = self.search_edit.text().strip().lower()
        if not needle:
            self._filtered = list(self._records)
        else:
            filtered: List[Dict[str, Any]] = []
            for record in self._records:
                haystack = " ".join(
                    str(record.get(column, "")) for column, _ in self.config.display_columns
                ).lower()
                if needle in haystack:
                    filtered.append(record)
            self._filtered = filtered
        self._populate_table(select_id=select_id)

    def _populate_table(self, *, select_id: Optional[str]) -> None:
        self.table.setRowCount(len(self._filtered))
        target_id = select_id
        for row_index, record in enumerate(self._filtered):
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
            if target_id and identifier == target_id:
                self.table.selectRow(row_index)
        if target_id and self.table.currentRow() < 0 and self.table.rowCount() > 0:
            self.table.selectRow(0)

    def _selected_identifier(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        identifier = item.data(Qt.UserRole)
        return str(identifier) if identifier is not None else None

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
        try:
            record = self.service.check_in(self.config.key, record_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Check-In Failed", str(exc), QMessageBox.Ok)
            return
        description = self._describe_record(record)
        QMessageBox.information(
            self,
            "Checked In",
            f"{description} is now part of the active incident.",
        )
        self.refresh(select_id=str(record.get(self.config.id_column, "")))

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
        self.refresh(select_id=record_id)


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
            "Select records from the master registry and copy them into the active incident database.",
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
