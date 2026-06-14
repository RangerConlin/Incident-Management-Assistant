from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
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
from utils.api_client import APIError
from utils.state import AppState

from ..models import ReflexActionCreate, ReflexActionRead
from .. import services


class ReflexTaskingPanel(QWidget):
    """Panel for managing reflex tasking triggers and automated actions."""

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReflexTaskingPanel")
        del incident_id

        self._trigger = QLineEdit()
        self._action = QTextEdit()
        self._notify = QCheckBox("Send communications alert")
        self._notify.setChecked(True)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #375a2b;")
        self._status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        title = QLabel("Reflex Tasking Workspace")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        subtitle = QLabel("Capture automatic or near-automatic actions for known triggers during the first operational minutes.")
        subtitle.setWordWrap(True)

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
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch(1)
        header.addWidget(self._status)
        layout.addLayout(header)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(QLabel("Reflex taskings"))
        layout.addWidget(self._table)

        self.reload()

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Initial response API unavailable: {exc}"
            return f"Initial response API error {exc.status_code}: {exc}"
        return str(exc)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _incident(self) -> str | None:
        return AppState.get_active_incident()

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
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before creating reflex actions.", error=True)
            return
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
            self._set_status(self._describe_error(exc), error=True)
            QMessageBox.critical(self, "Save failed", self._describe_error(exc))
            return

        self._clear_form()
        self.reload()

    def reload(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._table.setRowCount(0)
            self._set_status("Select an incident to use the reflex workspace.", error=True)
            return
        try:
            rows = services.list_reflex_action_entries(incident_id)
        except Exception as exc:  # pragma: no cover - UI guard
            self._set_status(self._describe_error(exc), error=True)
            QMessageBox.critical(self, "Load failed", self._describe_error(exc))
            return
        self._populate(rows)
        alert_links = sum(1 for row in rows if row.communications_alert_id)
        self._set_status(f"{len(rows)} reflex actions | {alert_links} alert links")
