from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import APIError, api_client
from utils.app_signals import app_signals
from utils.state import AppState


class ResourcesPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        del incident_id
        self._status = QLabel("")
        self._context = QLabel("No active incident selected")
        self._context.setStyleSheet("font-weight: 600;")
        self._build_ui()
        try:
            app_signals.incidentChanged.connect(lambda *_: self.reload())
        except Exception:
            pass
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setStyleSheet("QFrame { border: 1px solid #d0d0d0; border-radius: 4px; padding: 8px; }")
        header_layout = QVBoxLayout(header)
        top = QHBoxLayout()
        title = QLabel("Resources")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self._status)
        header_layout.addLayout(top)
        subtitle = QLabel("Track early capability on scene, immediate needs, and support requests that should be moving now.")
        subtitle.setWordWrap(True)
        header_layout.addWidget(self._context)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        current_box = QGroupBox("Current Resources")
        current_layout = QVBoxLayout(current_box)
        current_form = QFormLayout()
        self._resource_name = QLineEdit()
        self._resource_type = QComboBox()
        self._resource_type.addItems(["Ground Team", "Vehicle", "Aircraft", "K9", "Comms", "Medical", "Planning", "Other"])
        self._resource_status = QComboBox()
        self._resource_status.addItems(["Requested", "Responding", "On Scene", "Assigned", "Unavailable"])
        self._resource_owner = QLineEdit()
        self._resource_notes = QTextEdit()
        self._resource_notes.setFixedHeight(70)
        current_form.addRow("Resource Name", self._resource_name)
        current_form.addRow("Type", self._resource_type)
        current_form.addRow("Status", self._resource_status)
        current_form.addRow("Assigned / Owner", self._resource_owner)
        current_form.addRow("Notes", self._resource_notes)
        current_layout.addLayout(current_form)
        current_actions = QHBoxLayout()
        btn_add_resource = QPushButton("Add Current Resource")
        btn_add_resource.clicked.connect(self._add_current_resource)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.reload)
        current_actions.addWidget(btn_add_resource)
        current_actions.addWidget(btn_refresh)
        current_actions.addStretch(1)
        current_layout.addLayout(current_actions)
        self._resource_table = QTableWidget(0, 5)
        self._resource_table.setHorizontalHeaderLabels(["Name", "Type", "Status", "Owner", "Updated"])
        self._resource_table.horizontalHeader().setStretchLastSection(True)
        self._resource_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._resource_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        current_layout.addWidget(self._resource_table)
        top_layout.addWidget(current_box, 1)

        needs_box = QGroupBox("Immediate Needs / Support Requests")
        needs_layout = QVBoxLayout(needs_box)
        needs_form = QFormLayout()
        self._request_title = QLineEdit()
        self._request_kind = QComboBox()
        self._request_kind.addItems(["Ground Teams", "Aircraft", "K9", "ATV / UTV", "Medical", "Comms", "Lighting", "Mapping / GIS", "Transport", "Other"])
        self._request_priority = QComboBox()
        self._request_priority.addItems(["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self._request_qty = QLineEdit("1")
        self._request_justification = QTextEdit()
        self._request_justification.setFixedHeight(70)
        needs_form.addRow("Request Title", self._request_title)
        needs_form.addRow("Need Type", self._request_kind)
        needs_form.addRow("Priority", self._request_priority)
        needs_form.addRow("Quantity", self._request_qty)
        needs_form.addRow("Justification", self._request_justification)
        needs_layout.addLayout(needs_form)
        needs_actions = QHBoxLayout()
        btn_create_request = QPushButton("Create Support Request")
        btn_create_request.clicked.connect(self._create_support_request)
        needs_actions.addWidget(btn_create_request)
        needs_actions.addStretch(1)
        needs_layout.addLayout(needs_actions)
        self._request_table = QTableWidget(0, 5)
        self._request_table.setHorizontalHeaderLabels(["Title", "Priority", "Status", "Section", "Updated"])
        self._request_table.horizontalHeader().setStretchLastSection(True)
        self._request_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._request_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        needs_layout.addWidget(self._request_table)
        top_layout.addWidget(needs_box, 1)

        splitter.addWidget(top_widget)

        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)

        teams_box = QGroupBox("Teams Already Engaged")
        teams_layout = QVBoxLayout(teams_box)
        self._team_table = QTableWidget(0, 4)
        self._team_table.setHorizontalHeaderLabels(["Team", "Status", "Last Check-In", "Assistance"])
        self._team_table.horizontalHeader().setStretchLastSection(True)
        self._team_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._team_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        teams_layout.addWidget(self._team_table)
        bottom_layout.addWidget(teams_box, 1)

        gaps_box = QGroupBox("Resource Picture")
        gaps_layout = QVBoxLayout(gaps_box)
        self._resource_summary = QTextEdit()
        self._resource_summary.setReadOnly(True)
        gaps_layout.addWidget(self._resource_summary)
        bottom_layout.addWidget(gaps_box, 1)

        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    def _incident(self) -> str | None:
        return AppState.get_active_incident()

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Resources API unavailable: {exc}"
            return f"Resources API error {exc.status_code}: {exc}"
        return str(exc)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _api_get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return api_client.get(path, params=params)

    def _api_post(self, path: str, *, json: dict[str, Any]) -> Any:
        return api_client.post(path, json=json)

    def _add_current_resource(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before adding resources.", error=True)
            return
        name = self._resource_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Resources", "Resource name is required.")
            return
        payload = {
            "incident_id": incident_id,
            "resource_name": name,
            "resource_type": self._resource_type.currentText(),
            "status": self._resource_status.currentText(),
            "assigned_to": self._resource_owner.text().strip(),
            "notes": self._resource_notes.toPlainText().strip(),
            "source_entity_type": "initial_response",
        }
        try:
            self._api_post(f"/api/incidents/{incident_id}/logistics/resource-status", json=payload)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._resource_name.clear()
        self._resource_owner.clear()
        self._resource_notes.clear()
        self.reload()

    def _create_support_request(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before creating support requests.", error=True)
            return
        title = self._request_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Resources", "Request title is required.")
            return
        quantity = self._request_qty.text().strip() or "1"
        payload = {
            "incident_id": incident_id,
            "title": title,
            "requesting_section": "Initial Response",
            "priority": self._request_priority.currentText(),
            "status": "SUBMITTED",
            "justification": self._request_justification.toPlainText().strip(),
            "items": [
                {
                    "kind": self._request_kind.currentText(),
                    "description": title,
                    "quantity": int(quantity) if quantity.isdigit() else 1,
                    "unit": "Requested",
                }
            ],
        }
        try:
            self._api_post(f"/api/incidents/{incident_id}/logistics/resource-requests", json=payload)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._request_title.clear()
        self._request_justification.clear()
        self.reload()

    def _populate_resources(self, rows: list[dict[str, Any]]) -> None:
        self._resource_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            values = [
                str(row.get("resource_name", "")),
                str(row.get("resource_type", "")),
                str(row.get("status", "")),
                str(row.get("assigned_to", "")),
                str(row.get("updated_at") or row.get("last_updated") or ""),
            ]
            for col_idx, value in enumerate(values):
                self._resource_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _populate_requests(self, rows: list[dict[str, Any]]) -> None:
        self._request_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            values = [
                str(row.get("title", "")),
                str(row.get("priority", "")),
                str(row.get("status", "")),
                str(row.get("requesting_section", "")),
                str(row.get("last_updated_utc") or row.get("created_utc") or ""),
            ]
            for col_idx, value in enumerate(values):
                self._request_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _populate_teams(self, rows: list[dict[str, Any]]) -> None:
        self._team_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            assistance = "Emergency" if row.get("emergency") else ("Needs Assistance" if row.get("needs_assistance") else "")
            values = [
                str(row.get("team_name", "")),
                str(row.get("status", "")),
                str(row.get("last_checkin_ts") or ""),
                assistance,
            ]
            for col_idx, value in enumerate(values):
                self._team_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _update_summary(self, resources: list[dict[str, Any]], requests: list[dict[str, Any]], teams: list[dict[str, Any]]) -> None:
        on_scene = sum(1 for row in resources if str(row.get("status", "")).lower() in {"on scene", "assigned", "responding"})
        open_requests = [row for row in requests if str(row.get("status", "")).upper() not in {"CLOSED", "DELIVERED", "DENIED", "CANCELLED"}]
        assistance = [row for row in teams if row.get("needs_assistance") or row.get("emergency")]
        lines = [
            f"Current resource entries: {len(resources)}",
            f"Resources responding / on scene / assigned: {on_scene}",
            f"Open support requests: {len(open_requests)}",
            f"Teams already engaged: {len(teams)}",
            f"Teams needing help or flagged: {len(assistance)}",
        ]
        if open_requests:
            lines.append("")
            lines.append("Priority needs in motion:")
            for row in open_requests[:5]:
                lines.append(f"- {row.get('priority', '')}: {row.get('title', '')} ({row.get('status', '')})")
        self._resource_summary.setPlainText("\n".join(lines))

    def reload(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._resource_table.setRowCount(0)
            self._request_table.setRowCount(0)
            self._team_table.setRowCount(0)
            self._resource_summary.clear()
            self._context.setText("No active incident selected")
            self._set_status("Select an incident to use Resources.", error=True)
            return
        try:
            resources = self._api_get(f"/api/incidents/{incident_id}/logistics/resource-status") or []
            requests = self._api_get(f"/api/incidents/{incident_id}/logistics/resource-requests") or []
            teams = self._api_get(f"/api/incidents/{incident_id}/teams") or []
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._context.setText(f"Incident {incident_id}")
        self._populate_resources(resources)
        self._populate_requests(requests)
        self._populate_teams(teams)
        self._update_summary(resources, requests, teams)
        self._set_status(f"{len(resources)} resources | {len(requests)} requests | {len(teams)} teams")
