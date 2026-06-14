"""Panel for storing and exporting official forms."""

from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QDialog,
    QLineEdit,
    QTextEdit,
    QFormLayout,
    QDialogButtonBox,
)
from ..models import FormEntry
from ..utils import export
from .. import services


class _FormDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Form")
        self.name_edit = QLineEdit()
        self.body_edit = QTextEdit()
        form = QFormLayout(self)
        form.addRow("Form Name", self.name_edit)
        form.addRow("Content", self.body_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def data(self) -> FormEntry:
        return FormEntry(form_name=self.name_edit.text(), data_json=self.body_edit.toPlainText())


class FormCenterPanel(QWidget):
    headers = ["Form", "Preview"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)

        self.add_btn = QPushButton("New Form")
        self.export_btn = QPushButton("Export")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self._add)
        self.export_btn.clicked.connect(self._export)

        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        try:
            forms = services.list_form_entries()
        except Exception:
            return
        for row, f in enumerate(forms):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f.form_name))
            preview = f.data_json[:40].replace("\n", " ")
            self.table.setItem(row, 1, QTableWidgetItem(preview))
            self.table.item(row, 0).setData(0x0100, f.id)  # Qt.UserRole

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(0x0100)) if item else None

    def _add(self) -> None:
        dlg = _FormDialog(self)
        if dlg.exec() == dlg.Accepted:
            try:
                services.add_form_entry(dlg.data)
                self.refresh()
            except Exception:
                pass

    def _export(self) -> None:
        fid = self._current_id()
        if fid is None:
            return
        form = services.get_form_entry(fid)
        if not form:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", filter="PDF Files (*.pdf)")
        if not path:
            return
        html = f"<h1>{form.form_name}</h1><pre>{form.data_json}</pre>"
        export.export_html_to_pdf(html, Path(path))
