from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import HastyTaskCreate, HastyTaskRead
from .. import services


class HastyToolsPanel(QWidget):
    """Panel providing data entry for hasty tasking during initial response."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HastyToolsPanel")

        self._area = QLineEdit()
        self._priority = QComboBox()
        self._priority.addItems(["Low", "Medium", "High", "Critical"])
        self._notes = QTextEdit()
        self._create_task = QCheckBox("Create operations task")
        self._create_task.setChecked(True)
        self._request_logistics = QCheckBox("Request logistics support if needed")

        form = QFormLayout()
        form.addRow("Operational area", self._area)
        form.addRow("Priority", self._priority)
        form.addRow("Notes", self._notes)
        form.addRow(self._create_task)
        form.addRow(self._request_logistics)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Area", "Priority", "Task", "Logistics", "Notes", "Created"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)

        btn_save = QPushButton("Save hasty task")
        btn_save.clicked.connect(self._on_save)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear_form)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        actions.addWidget(btn_save)
        actions.addWidget(btn_clear)
        actions.addStretch(1)
        actions.addWidget(btn_refresh)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(QLabel("Logged hasty tasks"))
        layout.addWidget(self._table)

        self.reload()

    # ------------------------------------------------------------------ helpers
    def _clear_form(self) -> None:
        self._area.clear()
        self._priority.setCurrentIndex(1)
        self._notes.clear()
        self._create_task.setChecked(True)
        self._request_logistics.setChecked(False)

    def _populate(self, rows: Iterable[HastyTaskRead]) -> None:
        self._table.setRowCount(0)
        for record in rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = [
                record.area,
                record.priority or "",
                str(record.operations_task_id or ""),
                record.logistics_request_id or "",
                record.notes or "",
                record.created_at or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in {2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row, col, item)

    # ------------------------------------------------------------------ actions
    def _on_save(self) -> None:
        area = self._area.text().strip()
        if not area:
            QMessageBox.warning(self, "Validation", "Operational area is required")
            return

        payload = HastyTaskCreate(
            area=area,
            priority=self._priority.currentText(),
            notes=self._notes.toPlainText().strip() or None,
            create_task=self._create_task.isChecked(),
            request_logistics=self._request_logistics.isChecked(),
        )
        try:
            services.create_hasty_task(payload)
        except Exception as exc:  # pragma: no cover - UI guard
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self._clear_form()
        self.reload()

    def reload(self) -> None:
        try:
            rows = services.list_hasty_task_entries()
        except Exception as exc:  # pragma: no cover - UI guard
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        self._populate(rows)
