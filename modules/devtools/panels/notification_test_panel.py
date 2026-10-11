from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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

from notifications.models import Notification
from notifications.models import CATEGORY_DEFAULTS, SEVERITY_RANK
from notifications.services import get_notifier
from utils.api_client import APIError, api_client
from utils.state import AppState
from utils.styles import get_palette, subscribe_theme


LOCAL_DESKTOP_TARGET = "local_desktop"

NOTIFICATION_PRESETS: tuple[dict[str, object], ...] = (
    {
        "label": "Routine Operations",
        "title": "Test operations notification",
        "message": "This is a routine operations test notification.",
        "category": "operations",
        "severity": "routine",
        "requires_acknowledgement": False,
    },
    {
        "label": "Priority Safety",
        "title": "Test safety priority",
        "message": "This is a priority safety test notification.",
        "category": "safety",
        "severity": "priority",
        "requires_acknowledgement": True,
    },
    {
        "label": "Emergency Alert",
        "title": "Test emergency alert",
        "message": "This is an emergency test notification.",
        "category": "operations",
        "severity": "emergency",
        "requires_acknowledgement": True,
    },
    {
        "label": "Informational System",
        "title": "Test system information",
        "message": "This is an informational system test notification.",
        "category": "system",
        "severity": "informational",
        "requires_acknowledgement": False,
    },
)


def connection_display_name(connection: dict[str, Any]) -> str:
    """Return a compact label for a connected user/device row."""
    if connection.get("target_type") == LOCAL_DESKTOP_TARGET:
        return "Current desktop session"
    person = connection.get("person_id") or connection.get("person_record") or "Unknown user"
    device = connection.get("device_name") or connection.get("device_id") or "Unknown device"
    return f"{person} - {device}"


def build_notification_payload(
    *,
    connection: dict[str, Any],
    title: str,
    message: str,
    category: str,
    severity: str,
    source_id: str,
    source_label: str,
    requires_acknowledgement: bool,
) -> dict[str, Any]:
    person_record = connection.get("person_record")
    if person_record is None:
        raise ValueError("Selected connection does not have a person_record.")
    return {
        "title": title.strip(),
        "message": message.strip(),
        "category": category,
        "severity": severity,
        "source_type": "dev_notification_test",
        "source_id": source_id.strip(),
        "source_label": source_label.strip() or "Developer Notification Tester",
        "audience_user_id": int(person_record),
        "requires_acknowledgement": requires_acknowledgement,
    }


class NotificationTestPanel(QWidget):
    """Developer utility for sending real notification records to active users."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Notification Tester")
        self._connections: list[dict[str, Any]] = []
        self._build_ui()
        subscribe_theme(self, self._apply_theme)
        self.refresh_connections()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.incident_label = QLabel(self._incident_text())
        header.addWidget(self.incident_label)
        header.addStretch(1)
        refresh_btn = QPushButton("Refresh Connections")
        refresh_btn.clicked.connect(self.refresh_connections)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.connections_table = QTableWidget(0, 7)
        self.connections_table.setHorizontalHeaderLabels(
            ["Target", "User", "Device", "Platform", "Role", "Incident", "Last Seen"]
        )
        self.connections_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.connections_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.connections_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.connections_table.verticalHeader().setVisible(False)
        header_view = self.connections_table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setStretchLastSection(True)
        self.connections_table.setMinimumHeight(180)
        layout.addWidget(self.connections_table)

        form_box = QGroupBox("Notification")
        form = QFormLayout(form_box)

        self.preset_combo = QComboBox()
        for preset in NOTIFICATION_PRESETS:
            self.preset_combo.addItem(str(preset["label"]), preset)
        self.preset_combo.currentIndexChanged.connect(self._apply_selected_preset)
        form.addRow("Preset", self.preset_combo)

        self.category_combo = QComboBox()
        self.category_combo.addItems(sorted(CATEGORY_DEFAULTS.keys()))
        form.addRow("Category", self.category_combo)

        self.severity_combo = QComboBox()
        self.severity_combo.addItems(SEVERITY_RANK.keys())
        form.addRow("Severity", self.severity_combo)

        self.title_edit = QLineEdit()
        form.addRow("Title", self.title_edit)

        self.message_edit = QTextEdit()
        self.message_edit.setAcceptRichText(False)
        self.message_edit.setMinimumHeight(90)
        form.addRow("Message", self.message_edit)

        self.ack_check = QCheckBox("Requires acknowledgement")
        form.addRow("", self.ack_check)

        self.source_id_edit = QLineEdit()
        self.source_id_edit.setPlaceholderText("Generated automatically if left blank")
        form.addRow("Source ID", self.source_id_edit)

        self.source_label_edit = QLineEdit("Developer Notification Tester")
        form.addRow("Source Label", self.source_label_edit)

        layout.addWidget(form_box)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.send_btn = QPushButton("Send Test Notification")
        self.send_btn.clicked.connect(self.send_notification)
        actions.addWidget(self.send_btn)
        layout.addLayout(actions)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(90)
        layout.addWidget(self.result_text)

        self._apply_selected_preset()

    def _incident_text(self) -> str:
        incident_id = AppState.get_active_incident()
        if not incident_id:
            return "Active incident: none"
        return f"Active incident: {incident_id}"

    def _apply_theme(self, _name: str) -> None:
        palette = get_palette()
        border = palette["ctrl_focus"].name()
        hover = palette["ctrl_hover"].name()
        self.connections_table.setStyleSheet(
            "QTableWidget::item:selected {"
            f"border: 1px solid {border};"
            f"background: {hover};"
            "}"
        )

    def _apply_selected_preset(self) -> None:
        preset = self.preset_combo.currentData()
        if not isinstance(preset, dict):
            return
        self.title_edit.setText(str(preset.get("title") or ""))
        self.message_edit.setPlainText(str(preset.get("message") or ""))
        self.ack_check.setChecked(bool(preset.get("requires_acknowledgement")))
        self._set_combo_value(self.category_combo, str(preset.get("category") or "operations"))
        self._set_combo_value(self.severity_combo, str(preset.get("severity") or "routine"))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def refresh_connections(self) -> None:
        self.incident_label.setText(self._incident_text())
        try:
            rows = api_client.get("/api/client-connections") or []
        except APIError as exc:
            QMessageBox.warning(self, "Notification Tester", f"Unable to load connections: {exc}")
            return
        except Exception as exc:
            QMessageBox.warning(self, "Notification Tester", f"Unable to load connections: {exc}")
            return
        self._connections = [self._current_desktop_connection()]
        self._connections.extend(row for row in rows if isinstance(row, dict))
        self._populate_connections()

    def _current_desktop_connection(self) -> dict[str, Any]:
        return {
            "target_type": LOCAL_DESKTOP_TARGET,
            "person_record": AppState.get_active_user_id(),
            "person_id": AppState.get_active_user_display() or AppState.get_active_user_id() or "Current user",
            "device_name": "Desktop app",
            "device_id": "current-desktop-session",
            "platform": "desktop",
            "role": AppState.get_active_user_role() or "",
            "incident_id": AppState.get_active_incident() or "",
            "last_seen_at": "now",
        }

    def _populate_connections(self) -> None:
        self.connections_table.setRowCount(len(self._connections))
        for row_index, connection in enumerate(self._connections):
            values = [
                "This desktop" if connection.get("target_type") == LOCAL_DESKTOP_TARGET else "Connected client",
                connection.get("person_id") or connection.get("person_record") or "",
                connection.get("device_name") or connection.get("device_id") or "",
                connection.get("platform") or "",
                connection.get("role") or "",
                connection.get("incident_id") or "",
                connection.get("last_seen_at") or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row_index)
                self.connections_table.setItem(row_index, column, item)
        if self._connections:
            self.connections_table.selectRow(0)
        self.connections_table.resizeColumnsToContents()

    def _selected_connection(self) -> dict[str, Any] | None:
        row = self.connections_table.currentRow()
        if row < 0 or row >= len(self._connections):
            return None
        return self._connections[row]

    def _source_id(self) -> str:
        explicit = self.source_id_edit.text().strip()
        if explicit:
            return explicit
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return f"dev-test-{stamp}"

    def send_notification(self) -> None:
        incident_id = AppState.get_active_incident()
        connection = self._selected_connection()
        if not connection:
            QMessageBox.warning(self, "Notification Tester", "Select a notification target first.")
            return
        title = self.title_edit.text().strip()
        message = self.message_edit.toPlainText().strip()
        if not title or not message:
            QMessageBox.warning(self, "Notification Tester", "Title and message are required.")
            return
        if connection.get("target_type") == LOCAL_DESKTOP_TARGET:
            self._send_local_desktop_notification(
                {
                    "title": title,
                    "message": message,
                    "category": self.category_combo.currentText(),
                    "severity": self.severity_combo.currentText(),
                    "source_type": "dev_notification_test",
                    "source_id": self._source_id(),
                    "source_label": self.source_label_edit.text().strip() or "Developer Notification Tester",
                },
                connection,
            )
            return
        if not incident_id:
            QMessageBox.warning(self, "Notification Tester", "Select an active incident before sending to a connected client.")
            return
        try:
            payload = build_notification_payload(
                connection=connection,
                title=title,
                message=message,
                category=self.category_combo.currentText(),
                severity=self.severity_combo.currentText(),
                source_id=self._source_id(),
                source_label=self.source_label_edit.text(),
                requires_acknowledgement=self.ack_check.isChecked(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Notification Tester", str(exc))
            return
        try:
            result = api_client.post(f"/api/incidents/{incident_id}/notifications", json=payload)
        except APIError as exc:
            QMessageBox.critical(self, "Notification Tester", f"Send failed: {exc}")
            return
        except Exception as exc:
            QMessageBox.critical(self, "Notification Tester", f"Send failed: {exc}")
            return
        delivery = (result or {}).get("delivery") if isinstance(result, dict) else {}
        notification_id = (result or {}).get("notification_id") if isinstance(result, dict) else None
        self.result_text.setPlainText(
            "\n".join(
                [
                    f"Sent notification {notification_id or '(unknown id)'}",
                    f"Target: {connection_display_name(connection)}",
                    f"Recipients: {delivery.get('recipients', []) if isinstance(delivery, dict) else []}",
                    f"Push attempted: {delivery.get('push_attempted', 0) if isinstance(delivery, dict) else 0}",
                    f"Push sent: {delivery.get('push_sent', 0) if isinstance(delivery, dict) else 0}",
                ]
            )
        )

    def _send_local_desktop_notification(self, payload: dict[str, Any], connection: dict[str, Any]) -> None:
        get_notifier().notify(
            Notification(
                title=payload["title"],
                message=payload["message"],
                severity=payload["severity"],
                category=payload["category"],
                source=payload["source_label"],
                entity_type=payload["source_type"],
                entity_id=payload["source_id"],
            )
        )
        self.result_text.setPlainText(
            "\n".join(
                [
                    "Sent local desktop notification",
                    f"Target: {connection_display_name(connection)}",
                    "Delivery: local notifier",
                    "Push attempted: 0",
                    "Push sent: 0",
                ]
            )
        )


__all__ = [
    "NotificationTestPanel",
    "LOCAL_DESKTOP_TARGET",
    "build_notification_payload",
    "connection_display_name",
]
