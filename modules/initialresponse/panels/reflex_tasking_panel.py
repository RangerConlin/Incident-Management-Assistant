from __future__ import annotations

from typing import Iterable

from PySide6.QtWidgets import (
    QCheckBox,
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

from ..models import ReflexActionCreate, ReflexActionRead
from .. import services


class ReflexTaskingPanel(QWidget):
    """Panel for managing reflex tasking triggers and automated actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReflexTaskingPanel")

        self._trigger = QLineEdit()
        self._action = QTextEdit()
        self._notify = QCheckBox("Send communications alert")
        self._notify.setChecked(True)

        form = QFormLayout()
        form.addRow("Trigger", self._trigger)
        form.addRow("Action", self._action)
        form.addRow(self._notify)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            "Trigger",
            "Action",
            "Alert",
            "Created",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)

        btn_save = QPushButton("Save reflex action")
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
        layout.addWidget(QLabel("Reflex taskings"))
        layout.addWidget(self._table)

        self.reload()

    # ------------------------------------------------------------------ helpers
    def _clear_form(self) -> None:
        self._trigger.clear()
        self._action.clear()
        self._notify.setChecked(True)

    def _populate(self, rows: Iterable[ReflexActionRead]) -> None:
        self._table.setRowCount(0)
        for record in rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = [
                record.trigger,
                record.action or "",
                record.communications_alert_id or "",
                record.created_at or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self._table.setItem(row, col, item)

    # ------------------------------------------------------------------ actions
    def _on_save(self) -> None:
        trigger = self._trigger.text().strip()
        if not trigger:
            QMessageBox.warning(self, "Validation", "Trigger is required")
            return

        payload = ReflexActionCreate(
            trigger=trigger,
            action=self._action.toPlainText().strip() or None,
            notify=self._notify.isChecked(),
        )
        try:
            services.create_reflex_action(payload)
        except Exception as exc:  # pragma: no cover - UI guard
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self._clear_form()
        self.reload()

    def reload(self) -> None:
        try:
            rows = services.list_reflex_action_entries()
        except Exception as exc:  # pragma: no cover - UI guard
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        self._populate(rows)
