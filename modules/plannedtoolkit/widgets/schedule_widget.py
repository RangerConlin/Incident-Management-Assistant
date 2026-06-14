from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from .. import services
from ..records import ScheduledItem, schedule_from_dict


class ScheduleWidget(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.incident_id = None if incident_id is None else str(incident_id)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Event Schedule")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.kind_edit = QLineEdit("Milestone")
        self.starts_edit = QLineEdit()
        self.ends_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(64)
        form.addRow("Name", self.name_edit)
        form.addRow("Kind", self.kind_edit)
        form.addRow("Starts", self.starts_edit)
        form.addRow("Ends", self.ends_edit)
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)

        actions = QHBoxLayout()
        add_btn = QPushButton("Add")
        refresh_btn = QPushButton("Refresh")
        add_btn.clicked.connect(self.add_item)
        refresh_btn.clicked.connect(self.refresh)
        actions.addWidget(add_btn)
        actions.addWidget(refresh_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Kind", "Starts", "Ends", "Notes"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def _iid(self) -> str | None:
        return self.incident_id

    def refresh(self) -> None:
        rows = services.list_schedule_items(self._iid())
        self._populate(rows)

    def add_item(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            return
        services.create_schedule_item(
            self._iid(),
            name=name,
            kind=self.kind_edit.text().strip() or "Milestone",
            starts_at=self.starts_edit.text().strip(),
            ends_at=self.ends_edit.text().strip(),
            notes=self.notes_edit.toPlainText().strip(),
        )
        self.name_edit.clear()
        self.notes_edit.clear()
        self.refresh()

    def _populate(self, rows: Iterable[ScheduledItem]) -> None:
        items = list(rows)
        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            values = [item.name, item.kind, item.starts_at, item.ends_at, item.notes]
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem("" if value is None else str(value))
                if col_idx < 4:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, cell)
