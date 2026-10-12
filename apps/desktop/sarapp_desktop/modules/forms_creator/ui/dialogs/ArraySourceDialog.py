"""Dialog for creating or editing a single array source in the binding catalog."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_COL_TYPES = [("Text", "text"), ("Checkbox (X / blank)", "checkbox")]


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "group"


class ArraySourceDialog(QDialog):
    """Create or edit an array source definition."""

    def __init__(self, existing: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self._is_edit = existing is not None
        self.setWindowTitle("Edit Array Source" if self._is_edit else "New Array Source")
        self.setMinimumWidth(600)
        self.resize(640, 500)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. Teams")
        self._label_edit.textChanged.connect(self._on_label_changed)
        form.addRow("Label", self._label_edit)

        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("auto-generated from label")
        if self._is_edit:
            self._id_edit.setReadOnly(True)
            self._id_edit.setStyleSheet("color: gray;")
        form.addRow("Array ID", self._id_edit)

        self._data_key_edit = QLineEdit()
        self._data_key_edit.setPlaceholderText("same as Array ID if blank")
        form.addRow("Data Key", self._data_key_edit)

        self._chars_spin = QSpinBox()
        self._chars_spin.setMinimum(20)
        self._chars_spin.setMaximum(300)
        self._chars_spin.setValue(80)
        form.addRow("Wrap at N chars", self._chars_spin)

        # Columns table
        cols_group = QGroupBox("Columns")
        cols_layout = QVBoxLayout(cols_group)
        layout.addWidget(cols_group)

        self._col_table = QTableWidget(0, 5)
        self._col_table.setHorizontalHeaderLabels(
            ["ID / Source Key", "Label", "Data Field", "Type", ""]
        )
        hh = self._col_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._col_table.verticalHeader().setVisible(False)
        self._col_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._col_table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        cols_layout.addWidget(self._col_table)

        col_note = QLabel(
            "ID / Source Key — used in col_patterns and data lookup. "
            "Data Field — the actual key in each data row (leave blank = same as ID). "
            "Type — Checkbox columns output X or blank based on truthiness."
        )
        col_note.setWordWrap(True)
        col_note.setStyleSheet("font-size: 11px; color: #888;")
        cols_layout.addWidget(col_note)

        col_btn_row = QHBoxLayout()
        add_col_btn = QPushButton("+ Add Column")
        add_col_btn.clicked.connect(self._add_column_row)
        col_btn_row.addWidget(add_col_btn)
        col_btn_row.addStretch()
        cols_layout.addLayout(col_btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing:
            self._populate(existing)

    def _on_label_changed(self, text: str) -> None:
        if not self._is_edit:
            slug = _slugify(text)
            self._id_edit.setText(slug)
            if not self._data_key_edit.text():
                self._data_key_edit.setPlaceholderText(slug)

    def _add_column_row(
        self,
        col_id: str = "",
        label: str = "",
        source_key: str = "",
        col_type: str = "text",
    ) -> None:
        row = self._col_table.rowCount()
        self._col_table.insertRow(row)

        self._col_table.setItem(row, 0, QTableWidgetItem(col_id))
        self._col_table.setItem(row, 1, QTableWidgetItem(label))
        self._col_table.setItem(row, 2, QTableWidgetItem(source_key))

        type_combo = QComboBox()
        for lbl, val in _COL_TYPES:
            type_combo.addItem(lbl, val)
        idx = type_combo.findData(col_type)
        type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._col_table.setCellWidget(row, 3, type_combo)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedHeight(24)
        self._col_table.setCellWidget(row, 4, remove_btn)

        self._rebind_remove_buttons()

    def _remove_column_row(self, row: int) -> None:
        self._col_table.removeRow(row)
        self._rebind_remove_buttons()

    def _rebind_remove_buttons(self) -> None:
        for r in range(self._col_table.rowCount()):
            btn = self._col_table.cellWidget(r, 4)
            if btn:
                try:
                    btn.clicked.disconnect()
                except RuntimeError:
                    pass
                btn.clicked.connect(lambda _=False, row=r: self._remove_column_row(row))

    def _populate(self, data: dict) -> None:
        self._label_edit.setText(data.get("label", data.get("id", "")))
        self._id_edit.setText(data.get("id", ""))
        dk = data.get("data_key", "")
        self._data_key_edit.setText(dk if dk != data.get("id", dk) else "")
        self._chars_spin.setValue(data.get("chars_per_row", 80))
        for col in data.get("columns", []):
            col_id = col.get("id", col.get("source_key", ""))
            source_key = col.get("source_key", "")
            # Only show source_key separately if it differs from id
            self._add_column_row(
                col_id=col_id,
                label=col.get("label", ""),
                source_key=source_key if source_key != col_id else "",
                col_type=col.get("type", "text"),
            )

    def _collect_columns(self) -> list[dict]:
        cols = []
        for r in range(self._col_table.rowCount()):
            def _text(c):
                it = self._col_table.item(r, c)
                return it.text().strip() if it else ""
            col_id     = _text(0)
            col_label  = _text(1)
            col_sk     = _text(2) or col_id
            type_w     = self._col_table.cellWidget(r, 3)
            col_type   = type_w.currentData() if type_w else "text"
            entry = {
                "id":         col_id,
                "label":      col_label,
                "source_key": col_sk,
            }
            if col_type != "text":
                entry["type"] = col_type
            cols.append(entry)
        return cols

    def _on_accept(self) -> None:
        group_id = self._id_edit.text().strip()
        if not group_id:
            QMessageBox.warning(self, "Array Source", "Array ID is required.")
            return
        columns = self._collect_columns()
        if not columns:
            QMessageBox.warning(self, "Array Source", "At least one column is required.")
            return
        empty_ids = [c for c in columns if not c["id"]]
        if empty_ids:
            QMessageBox.warning(self, "Array Source", "All columns must have an ID.")
            return
        data_key = self._data_key_edit.text().strip() or group_id
        self._result = {
            "id":           group_id,
            "label":        self._label_edit.text().strip() or group_id,
            "data_key":     data_key,
            "chars_per_row": self._chars_spin.value(),
            "columns":      columns,
        }
        self.accept()

    def result_data(self) -> dict | None:
        return getattr(self, "_result", None)
