"""Widget-based window for managing canned communication entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bridge.catalog_bridge import CatalogBridge
from utils.constants import TEAM_STATUSES


NOTIFICATION_LEVEL_CHOICES: List[tuple[int, str]] = [
    (0, "None"),
    (1, "Notification"),
    (2, "Emergency Alert"),
]


@dataclass(slots=True)
class TableColumn:
    key: str
    title: str
    width: int | None = None


TABLE_COLUMNS: List[TableColumn] = [
    TableColumn("id", "ID", 70),
    TableColumn("title", "Title", 240),
    TableColumn("category", "Category", 180),
    TableColumn("message", "Message", 320),
    TableColumn("notification_level", "Notify Level", 160),
    TableColumn("status_update", "Status Update", 200),
    TableColumn("is_active", "Active", 80),
]


def notification_label(value: int | None) -> str:
    try:
        numeric = 0 if value is None else int(value)
    except (TypeError, ValueError):
        numeric = 0
    for key, label in NOTIFICATION_LEVEL_CHOICES:
        if key == numeric:
            return label
    return NOTIFICATION_LEVEL_CHOICES[0][1]


class CannedCommEntryDialog(QDialog):
    """Dialog for creating or editing a canned communication entry."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        entry: Optional[dict] = None,
        status_options: Iterable[str] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Required")
        form.addRow("Title", self.title_input)

        self.category_input = QLineEdit()
        form.addRow("Category", self.category_input)

        self.notification_combo = QComboBox()
        for value, label in NOTIFICATION_LEVEL_CHOICES:
            self.notification_combo.addItem(label, value)
        form.addRow("Notify Level", self.notification_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItem("", None)
        for option in status_options:
            self.status_combo.addItem(option, option)
        form.addRow("Status Update", self.status_combo)

        self.message_edit = QTextEdit()
        self.message_edit.setAcceptRichText(False)
        self.message_edit.setPlaceholderText("Required")
        self.message_edit.setMinimumHeight(140)
        form.addRow("Message", self.message_edit)

        self.active_checkbox = QCheckBox("Active entry")
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if entry:
            self._load_entry(entry)
        else:
            self.active_checkbox.setChecked(True)

    def _load_entry(self, entry: dict) -> None:
        self.title_input.setText(entry.get("title", ""))
        self.category_input.setText(entry.get("category", ""))
        message = entry.get("message") or ""
        self.message_edit.setPlainText(message)
        self.active_checkbox.setChecked(bool(entry.get("is_active", True)))

        notify_value = entry.get("notification_level")
        index = self.notification_combo.findData(notify_value if notify_value is not None else 0)
        if index < 0:
            index = 0
        self.notification_combo.setCurrentIndex(index)

        status_value = entry.get("status_update")
        status_index = self.status_combo.findData(status_value if status_value else None)
        if status_index < 0:
            status_index = 0
        self.status_combo.setCurrentIndex(status_index)

    def _on_accept(self) -> None:
        title_text = self.title_input.text().strip()
        message_text = self.message_edit.toPlainText()
        if not title_text:
            QMessageBox.warning(self, "Canned Communications", "Title is required.")
            self.title_input.setFocus()
            return
        if not message_text.strip():
            QMessageBox.warning(self, "Canned Communications", "Message is required.")
            self.message_edit.setFocus()
            return
        self.accept()

    def data(self) -> dict:
        title_text = self.title_input.text().strip()
        category_text = self.category_input.text().strip()
        message_text = self.message_edit.toPlainText()
        status_value = self.status_combo.currentData()

        return {
            "title": title_text,
            "category": category_text or None,
            "message": message_text,
            "notification_level": int(self.notification_combo.currentData() or 0),
            "status_update": status_value or None,
            "is_active": bool(self.active_checkbox.isChecked()),
        }


class CannedCommEntriesWindow(QMainWindow):
    """Qt Widgets implementation of the canned communication entries window."""

    def __init__(
        self,
        catalog_bridge: CatalogBridge | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Canned Communication Entries")
        self.resize(960, 620)

        self._bridge = catalog_bridge or CatalogBridge()
        self._entries: list[dict] = []

        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        search_label = QLabel("Search")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search canned entries")
        self.search_input.textChanged.connect(self.refresh_entries)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_entry)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_entry)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_entry)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_button_states)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_entry())

        header_labels = [column.title for column in TABLE_COLUMNS]
        self.table.setHorizontalHeaderLabels(header_labels)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        for index, column in enumerate(TABLE_COLUMNS):
            if column.width is not None:
                header.resizeSection(index, column.width)

        layout.addWidget(self.table)

        self._update_button_states()
        self.refresh_entries()

    def current_entry(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        row_index = rows[0].row()
        if 0 <= row_index < len(self._entries):
            return self._entries[row_index]
        return None

    def refresh_entries(self, text: str | None = None) -> None:
        query = text.strip() if isinstance(text, str) else self.search_input.text().strip()
        try:
            entries = self._bridge.listCannedCommEntries(query)
        except Exception as exc:  # pragma: no cover - display error dialog
            QMessageBox.critical(
                self,
                "Canned Communications",
                f"Failed to load canned entries:\n{exc}",
            )
            entries = []

        entries = sorted(entries, key=lambda item: (str(item.get("title") or "").lower(), item.get("id", 0)))
        self._entries = entries
        self._populate_table(entries)

    def _populate_table(self, entries: list[dict]) -> None:
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            for column_index, column in enumerate(TABLE_COLUMNS):
                display = self._display_value(column.key, entry)
                item = QTableWidgetItem(display)
                if column.key == "id":
                    item.setData(Qt.UserRole, entry.get("id"))
                if column.key == "is_active" and not bool(entry.get("is_active", True)):
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                if column.key == "message":
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.table.setItem(row, column_index, item)

        self.table.setSortingEnabled(True)
        self._update_button_states()

    def _display_value(self, key: str, entry: dict) -> str:
        value = entry.get(key)
        if key == "notification_level":
            return notification_label(value)
        if key == "is_active":
            return "Yes" if bool(value) else "No"
        if value is None:
            return ""
        return str(value)

    def _update_button_states(self) -> None:
        has_selection = bool(self.current_entry())
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def add_entry(self) -> None:
        dialog = CannedCommEntryDialog(
            self,
            title="Add Canned Entry",
            status_options=TEAM_STATUSES,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.data()
        try:
            created_id = self._bridge.createCannedCommEntry(payload)
        except Exception as exc:  # pragma: no cover - display error dialog
            QMessageBox.critical(self, "Canned Communications", f"Failed to create entry:\n{exc}")
            return

        self.refresh_entries()
        if created_id:
            self._select_entry_by_id(created_id)

    def edit_entry(self) -> None:
        entry = self.current_entry()
        if not entry:
            QMessageBox.information(self, "Canned Communications", "Select an entry to edit.")
            return

        dialog = CannedCommEntryDialog(
            self,
            title="Edit Canned Entry",
            entry=entry,
            status_options=TEAM_STATUSES,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        payload = dialog.data()
        try:
            self._bridge.updateCannedCommEntry(int(entry["id"]), payload)
        except Exception as exc:  # pragma: no cover - display error dialog
            QMessageBox.critical(self, "Canned Communications", f"Failed to update entry:\n{exc}")
            return

        self.refresh_entries()
        self._select_entry_by_id(entry.get("id"))

    def delete_entry(self) -> None:
        entry = self.current_entry()
        if not entry:
            QMessageBox.information(self, "Canned Communications", "Select an entry to delete.")
            return

        title = entry.get("title") or "this entry"
        confirm = QMessageBox.question(
            self,
            "Delete Canned Entry",
            f"Are you sure you want to delete {title!r}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self._bridge.deleteCannedCommEntry(int(entry["id"]))
        except Exception as exc:  # pragma: no cover - display error dialog
            QMessageBox.critical(self, "Canned Communications", f"Failed to delete entry:\n{exc}")
            return

        self.refresh_entries()

    def _select_entry_by_id(self, entry_id: int | None) -> None:
        if entry_id is None:
            return
        for row, entry in enumerate(self._entries):
            if int(entry.get("id", -1)) == int(entry_id):
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 0))
                break


def open_canned_comm_entries_window(parent: QWidget | None = None) -> CannedCommEntriesWindow:
    """Utility to instantiate and show the canned communications window."""

    app = QApplication.instance()
    bridge = None
    if parent is not None and hasattr(parent, "_catalog_bridge"):
        bridge = getattr(parent, "_catalog_bridge")

    window = CannedCommEntriesWindow(catalog_bridge=bridge, parent=parent)
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    window.show()
    if app is not None:
        window.raise_()
        window.activateWindow()
    return window


__all__ = ["CannedCommEntriesWindow", "open_canned_comm_entries_window"]


if __name__ == "__main__":  # pragma: no cover - manual smoke test helper
    import sys

    app = QApplication(sys.argv)
    win = CannedCommEntriesWindow()
    win.show()
    sys.exit(app.exec())