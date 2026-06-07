"""Reusable widgets and form helpers for Public Information panels."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def combo(values: list[str], current: str = "") -> QComboBox:
    box = QComboBox()
    box.addItems(values)
    if current and current in values:
        box.setCurrentText(current)
    return box


def fill_table(table: QTableWidget, rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    table.setRowCount(0)
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels([label for label, _ in columns])
    table.setProperty("rows", rows)
    for row_index, row in enumerate(rows):
        table.insertRow(row_index)
        for column_index, (_, key) in enumerate(columns):
            item = QTableWidgetItem(str(row.get(key, "") if row.get(key) is not None else ""))
            item.setData(Qt.UserRole, row.get("id"))
            table.setItem(row_index, column_index, item)
    table.resizeColumnsToContents()


def selected_row_data(table: QTableWidget) -> dict[str, Any] | None:
    rows = table.property("rows") or []
    row_index = table.currentRow()
    if row_index < 0 or row_index >= len(rows):
        return None
    return rows[row_index]


class SummaryCard(QWidget):
    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.value = QLabel(str(value))
        self.value.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        self.setStyleSheet("SummaryCard { border: 1px solid #999; border-radius: 4px; padding: 6px; }")

    def set_value(self, value: Any) -> None:
        self.value.setText(str(value))


class SimpleRecordDialog(QDialog):
    def __init__(self, title: str, fields: list[tuple[str, str, str, list[str] | None]], data: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.data = dict(data or {})
        self.inputs: dict[str, QWidget] = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for label, key, kind, values in fields:
            if kind == "combo":
                widget = combo(values or [], str(self.data.get(key, "")))
            elif kind == "text":
                widget = QTextEdit(str(self.data.get(key, "")))
                widget.setMinimumHeight(90)
            elif kind == "check":
                widget = QCheckBox()
                widget.setChecked(bool(self.data.get(key, 0)))
            else:
                widget = QLineEdit(str(self.data.get(key, "") if self.data.get(key) is not None else ""))
            self.inputs[key] = widget
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def values(self) -> dict[str, Any]:
        values = dict(self.data)
        for key, widget in self.inputs.items():
            if isinstance(widget, QComboBox):
                values[key] = widget.currentText()
            elif isinstance(widget, QTextEdit):
                values[key] = widget.toPlainText()
            elif isinstance(widget, QCheckBox):
                values[key] = 1 if widget.isChecked() else 0
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text()
        return values
