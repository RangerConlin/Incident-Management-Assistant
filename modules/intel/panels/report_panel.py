"""Panel for composing and exporting intel reports."""

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
    QDialog,
    QLineEdit,
    QTextEdit,
    QFormLayout,
    QDialogButtonBox,
    QFileDialog,
)
from sqlmodel import select

from ..models import IntelReport
from ..utils import db_access, export


class _ReportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Report")
        self.title_edit = QLineEdit()
        self.body_edit = QTextEdit()
        form = QFormLayout(self)
        form.addRow("Title", self.title_edit)
        form.addRow("Body", self.body_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def report(self) -> IntelReport:
        return IntelReport(title=self.title_edit.text(), body_md=self.body_edit.toPlainText())


class ReportPanel(QWidget):
    headers = ["Title", "Preview"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)

        self.add_btn = QPushButton("New Report")
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
        with db_access.incident_session() as session:
            reports: List[IntelReport] = session.exec(select(IntelReport)).all()
        for row, r in enumerate(reports):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r.title))
            preview = r.body_md[:40].replace("\n", " ")
            self.table.setItem(row, 1, QTableWidgetItem(preview))
            self.table.item(row, 0).setData(0x0100, r.id)

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(0x0100)) if item else None

    def _add(self) -> None:
        dlg = _ReportDialog(self)
        if dlg.exec() == dlg.Accepted:
            with db_access.incident_session() as session:
                session.add(dlg.report)
                session.commit()
            self.refresh()

    def _export(self) -> None:
        rid = self._current_id()
        if rid is None:
            return
        with db_access.incident_session() as session:
            rep = session.get(IntelReport, rid)
        if not rep:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", filter="PDF Files (*.pdf)")
        if not path:
            return
        html = f"<h1>{rep.title}</h1><pre>{rep.body_md}</pre>"
        export.export_html_to_pdf(html, Path(path))
