from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import APIError, api_client
from utils.app_signals import app_signals
from utils.state import AppState

from .. import services
from ..models import InitialOverviewUpdate


class HandoffPanel(QWidget):
    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        del incident_id
        self._status = QLabel("")
        self._context = QLabel("No active incident selected")
        self._context.setStyleSheet("font-weight: 600;")
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Add handoff notes, transfer priorities, or cleanup instructions.")
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
        title = QLabel("Handoff")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self._status)
        header_layout.addLayout(top)
        subtitle = QLabel("Assemble the current initial response picture into a clean transfer brief and push forward what needs to live beyond this module.")
        subtitle.setWordWrap(True)
        header_layout.addWidget(self._context)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        options = QGroupBox("Carry Forward")
        options_layout = QVBoxLayout(options)
        self._push_objectives = QCheckBox("Create incident objectives from the current early objectives")
        self._push_objectives.setChecked(True)
        self._push_214 = QCheckBox("Append the handoff to an ICS-214 stream")
        self._push_214.setChecked(True)
        self._include_tasks = QCheckBox("Include generated early tasks in the brief")
        self._include_tasks.setChecked(True)
        options_layout.addWidget(self._push_objectives)
        options_layout.addWidget(self._push_214)
        options_layout.addWidget(self._include_tasks)
        layout.addWidget(options)

        editor_box = QGroupBox("Transfer Notes")
        editor_layout = QVBoxLayout(editor_box)
        editor_layout.addWidget(self._editor)
        layout.addWidget(editor_box)

        actions = QHBoxLayout()
        btn_refresh = QPushButton("Refresh Brief")
        btn_refresh.clicked.connect(self.reload)
        btn_copy = QPushButton("Copy Brief")
        btn_copy.clicked.connect(self._copy_brief)
        btn_commit = QPushButton("Commit Handoff")
        btn_commit.clicked.connect(self._commit_handoff)
        actions.addWidget(btn_refresh)
        actions.addWidget(btn_copy)
        actions.addWidget(btn_commit)
        actions.addStretch(1)
        layout.addLayout(actions)

        preview_box = QGroupBox("Handoff Brief")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(self._preview)
        layout.addWidget(preview_box, 1)

    def _incident(self) -> str | None:
        return AppState.get_active_incident()

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Handoff API unavailable: {exc}"
            return f"Handoff API error {exc.status_code}: {exc}"
        return str(exc)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _api_get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return api_client.get(path, params=params)

    def _api_post(self, path: str, *, json: dict[str, Any]) -> Any:
        return api_client.post(path, json=json)

    def _api_put(self, path: str, *, json: dict[str, Any]) -> Any:
        return api_client.put(path, json=json)

    def _build_brief(self) -> str:
        incident_id = self._incident()
        if not incident_id:
            return ""
        overview = services.get_initial_overview_entry(incident_id)
        tasks = services.list_hasty_task_entries(incident_id)
        resources = self._api_get(f"/api/incidents/{incident_id}/logistics/resource-status") or []
        requests = self._api_get(f"/api/incidents/{incident_id}/logistics/resource-requests") or []
        hazards = self._api_get(f"/api/incidents/{incident_id}/safety/orm/hazards", params={"op": 1}) or []
        reports = self._api_get(f"/api/incidents/{incident_id}/safety/reports") or []

        subject = (
            overview.subject_info.get("name")
            if overview.incident_mode == "Missing Person"
            else overview.aircraft_info.get("tail_number")
        ) or "Not entered"
        anchor = " ".join(
            part for part in [
                str(overview.primary_anchor.get("anchor_type", "")).strip(),
                str(overview.primary_anchor.get("address", "")).strip(),
            ] if part
        ) or "Not established"
        objectives = [line.strip("- ").strip() for line in self._editor.toPlainText().splitlines() if line.strip()]
        task_lines = []
        if self._include_tasks.isChecked():
            for row in tasks[:8]:
                task_lines.append(f"- {row.priority or 'Unprioritized'} | {row.area}")
        resource_lines = [f"- {row.get('resource_type', '')}: {row.get('resource_name', '')} [{row.get('status', '')}]" for row in resources[:6]]
        request_lines = [f"- {row.get('priority', '')} | {row.get('title', '')} ({row.get('status', '')})" for row in requests[:6]]
        hazard_lines = [f"- {row.get('sub_activity', '')}: {row.get('hazard_outcome', '')} [{row.get('residual_risk', '')}]" for row in hazards[:6]]
        report_lines = [f"- {row.get('severity', '')} at {row.get('location', '')}: {row.get('notes', '')}" for row in reports[:4]]

        lines = [
            f"INITIAL RESPONSE HANDOFF",
            f"Incident: {incident_id}",
            f"Mode: {overview.incident_mode}",
            f"Subject / Aircraft: {subject}",
            f"Behavior Category: {overview.behavior_category or 'Not selected'}",
            f"Primary Anchor: {anchor}",
            "",
            "Current Picture:",
            f"- Reporting source: {overview.source_info.get('reporting_source', '') or overview.source_info.get('name', '') or 'Not entered'}",
            f"- Last seen / contact: {overview.timeline_info.get('last_seen_time', '') or overview.timeline_info.get('last_contact_time', '') or 'Not entered'}",
            f"- Direction / plans: {overview.timeline_info.get('direction_plans', '') or 'Not entered'}",
            f"- Clues: {overview.clues_environment.get('clues', '') or 'None captured'}",
            f"- Terrain / weather: {overview.clues_environment.get('terrain', '') or 'None captured'} | {overview.clues_environment.get('weather', '') or 'None captured'}",
            f"- Operations summary: {overview.operations_summary.get('actions_taken', '') or 'No actions entered'}",
        ]
        if objectives:
            lines.extend(["", "Transfer Notes:"])
            lines.extend(f"- {line}" for line in objectives)
        if task_lines:
            lines.extend(["", "Early Tasks:"])
            lines.extend(task_lines)
        if resource_lines:
            lines.extend(["", "Resources On Picture:"])
            lines.extend(resource_lines)
        if request_lines:
            lines.extend(["", "Open Resource Requests:"])
            lines.extend(request_lines)
        if hazard_lines:
            lines.extend(["", "Operational Hazards:"])
            lines.extend(hazard_lines)
        if report_lines:
            lines.extend(["", "Safety Reports:"])
            lines.extend(report_lines)
        return "\n".join(lines)

    def _default_transfer_notes(self) -> list[str]:
        incident_id = self._incident()
        if not incident_id:
            return []
        overview = services.get_initial_overview_entry(incident_id)
        notes = [
            f"Confirm and continue work from the current anchor: {' '.join(part for part in [str(overview.primary_anchor.get('anchor_type', '')).strip(), str(overview.primary_anchor.get('address', '')).strip()] if part) or 'anchor not established'}.",
            "Continue early task follow-up and convert high-value findings into durable assignments.",
            "Maintain current resource requests and reassess capability gaps after the next task returns.",
        ]
        if overview.behavior_category:
            notes.insert(1, f"Keep the current behavior category in play: {overview.behavior_category}.")
        return notes

    def _copy_brief(self) -> None:
        text = self._preview.toPlainText().strip()
        if not text:
            self._set_status("Nothing to copy yet.", error=True)
            return
        QGuiApplication.clipboard().setText(text)
        self._set_status("Handoff brief copied")

    def _ensure_214_stream(self, incident_id: str) -> str:
        streams = self._api_get(f"/api/incidents/{incident_id}/ics214/streams") or []
        for stream in streams:
            if str(stream.get("section", "")).lower() == "initial response":
                return str(stream.get("id"))
        created = self._api_post(
            f"/api/incidents/{incident_id}/ics214/streams",
            json={
                "incident_id": incident_id,
                "name": "Initial Response Handoff",
                "op_number": 1,
                "kind": "handoff",
                "section": "Initial Response",
            },
        )
        return str(created.get("id", ""))

    def _commit_handoff(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before committing handoff.", error=True)
            return
        try:
            overview = services.get_initial_overview_entry(incident_id)
            text = self._preview.toPlainText().strip()
            if not text:
                self.reload()
                text = self._preview.toPlainText().strip()
            created_objectives = 0
            if self._push_objectives.isChecked():
                for raw in [line.strip("- ").strip() for line in self._editor.toPlainText().splitlines() if line.strip()]:
                    self._api_post(
                        "/api/objectives",
                        json={
                            "incident_id": incident_id,
                            "text": raw,
                            "priority": "high",
                            "status": "draft",
                            "owner_section": "Initial Response",
                            "tags": ["initial-response"],
                        },
                    )
                    created_objectives += 1
            if self._push_214.isChecked():
                stream_id = self._ensure_214_stream(incident_id)
                self._api_post(
                    f"/api/incidents/{incident_id}/ics214/streams/{stream_id}/entries",
                    json={
                        "text": text,
                        "critical_flag": False,
                        "tags": ["initial-response", "handoff"],
                        "source": "manual",
                    },
                )
            services.save_initial_overview_entry(
                InitialOverviewUpdate(
                    incident_mode=overview.incident_mode,
                    behavior_category=overview.behavior_category,
                    source_info=overview.source_info,
                    subject_info=overview.subject_info,
                    aircraft_info=overview.aircraft_info,
                    timeline_info=overview.timeline_info,
                    primary_anchor=overview.primary_anchor,
                    related_locations=overview.related_locations,
                    clues_environment=overview.clues_environment,
                    operations_summary=overview.operations_summary,
                    narrative=f"{overview.narrative}\n\n{text}".strip(),
                ),
                incident_id,
            )
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            QMessageBox.critical(self, "Handoff", self._describe_error(exc))
            return
        self._set_status(f"Handoff committed | objectives created: {created_objectives}")

    def reload(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._preview.clear()
            self._editor.clear()
            self._context.setText("No active incident selected")
            self._set_status("Select an incident to use Handoff.", error=True)
            return
        try:
            if not self._editor.toPlainText().strip():
                self._editor.setPlainText("\n".join(f"- {line}" for line in self._default_transfer_notes()))
            self._preview.setPlainText(self._build_brief())
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._context.setText(f"Incident {incident_id}")
        self._set_status("Handoff brief ready")
