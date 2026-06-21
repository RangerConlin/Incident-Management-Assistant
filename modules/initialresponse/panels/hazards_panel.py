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


class HazardsPanel(QWidget):
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
        title = QLabel("Hazards")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self._status)
        header_layout.addLayout(top)
        subtitle = QLabel("Capture early operational hazards, controls, and safety issues that should influence the first push.")
        subtitle.setWordWrap(True)
        header_layout.addWidget(self._context)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        orm_box = QGroupBox("Operational Hazards")
        orm_layout = QVBoxLayout(orm_box)
        orm_form = QFormLayout()
        self._hazard_sub_activity = QLineEdit()
        self._hazard_outcome = QTextEdit()
        self._hazard_outcome.setFixedHeight(64)
        self._initial_risk = QComboBox()
        self._initial_risk.addItems(["L", "M", "H", "EH"])
        self._controls = QTextEdit()
        self._controls.setFixedHeight(64)
        self._residual_risk = QComboBox()
        self._residual_risk.addItems(["L", "M", "H", "EH"])
        self._implement_how = QLineEdit()
        self._implement_who = QLineEdit()
        orm_form.addRow("Sub-Activity", self._hazard_sub_activity)
        orm_form.addRow("Hazard / Outcome", self._hazard_outcome)
        orm_form.addRow("Initial Risk", self._initial_risk)
        orm_form.addRow("Controls", self._controls)
        orm_form.addRow("Residual Risk", self._residual_risk)
        orm_form.addRow("Implement How", self._implement_how)
        orm_form.addRow("Implement Who", self._implement_who)
        orm_layout.addLayout(orm_form)
        orm_actions = QHBoxLayout()
        btn_add_hazard = QPushButton("Add Hazard")
        btn_add_hazard.clicked.connect(self._add_hazard)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.reload)
        orm_actions.addWidget(btn_add_hazard)
        orm_actions.addWidget(btn_refresh)
        orm_actions.addStretch(1)
        orm_layout.addLayout(orm_actions)
        self._hazard_table = QTableWidget(0, 5)
        self._hazard_table.setHorizontalHeaderLabels(["Activity", "Hazard", "Initial", "Residual", "Controls"])
        self._hazard_table.horizontalHeader().setStretchLastSection(True)
        self._hazard_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._hazard_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        orm_layout.addWidget(self._hazard_table)
        top_layout.addWidget(orm_box, 1)

        safety_box = QGroupBox("Safety Reports")
        safety_layout = QVBoxLayout(safety_box)
        safety_form = QFormLayout()
        self._report_time = QLineEdit()
        self._report_time.setPlaceholderText("2026-06-14T12:00:00")
        self._report_location = QLineEdit()
        self._report_severity = QComboBox()
        self._report_severity.addItems(["Low", "Moderate", "High", "Critical"])
        self._report_flagged = QComboBox()
        self._report_flagged.addItems(["No", "Yes"])
        self._report_notes = QTextEdit()
        self._report_notes.setFixedHeight(64)
        safety_form.addRow("Time", self._report_time)
        safety_form.addRow("Location", self._report_location)
        safety_form.addRow("Severity", self._report_severity)
        safety_form.addRow("Flagged", self._report_flagged)
        safety_form.addRow("Notes", self._report_notes)
        safety_layout.addLayout(safety_form)
        safety_actions = QHBoxLayout()
        btn_add_report = QPushButton("Log Safety Report")
        btn_add_report.clicked.connect(self._add_safety_report)
        safety_actions.addWidget(btn_add_report)
        safety_actions.addStretch(1)
        safety_layout.addLayout(safety_actions)
        self._report_table = QTableWidget(0, 4)
        self._report_table.setHorizontalHeaderLabels(["Time", "Location", "Severity", "Notes"])
        self._report_table.horizontalHeader().setStretchLastSection(True)
        self._report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._report_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        safety_layout.addWidget(self._report_table)
        top_layout.addWidget(safety_box, 1)

        splitter.addWidget(top_widget)

        summary_box = QGroupBox("Hazard Picture")
        summary_layout = QVBoxLayout(summary_box)
        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        summary_layout.addWidget(self._summary)
        splitter.addWidget(summary_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    def _incident(self) -> str | None:
        return AppState.get_active_incident()

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Hazards API unavailable: {exc}"
            return f"Hazards API error {exc.status_code}: {exc}"
        return str(exc)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _api_get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return api_client.get(path, params=params)

    def _api_post(self, path: str, *, json: dict[str, Any]) -> Any:
        return api_client.post(path, json=json)

    def _add_hazard(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before adding hazards.", error=True)
            return
        sub_activity = self._hazard_sub_activity.text().strip()
        hazard_outcome = self._hazard_outcome.toPlainText().strip()
        control_text = self._controls.toPlainText().strip()
        if not sub_activity or not hazard_outcome or not control_text:
            QMessageBox.warning(self, "Hazards", "Sub-activity, hazard, and controls are required.")
            return
        payload = {
            "op_period": 1,
            "sub_activity": sub_activity,
            "hazard_outcome": hazard_outcome,
            "initial_risk": self._initial_risk.currentText(),
            "control_text": control_text,
            "residual_risk": self._residual_risk.currentText(),
            "implement_how": self._implement_how.text().strip() or None,
            "implement_who": self._implement_who.text().strip() or None,
        }
        try:
            self._api_post(f"/api/incidents/{incident_id}/safety/orm/hazards", json=payload)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._hazard_sub_activity.clear()
        self._hazard_outcome.clear()
        self._controls.clear()
        self._implement_how.clear()
        self._implement_who.clear()
        self.reload()

    def _add_safety_report(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._set_status("Select an incident before logging safety reports.", error=True)
            return
        payload = {
            "time": self._report_time.text().strip() or None,
            "location": self._report_location.text().strip() or None,
            "severity": self._report_severity.currentText(),
            "notes": self._report_notes.toPlainText().strip() or None,
            "flagged": self._report_flagged.currentText() == "Yes",
        }
        if not payload["time"]:
            QMessageBox.warning(self, "Hazards", "Time is required for a safety report.")
            return
        try:
            self._api_post(f"/api/incidents/{incident_id}/safety/reports", json=payload)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._report_time.clear()
        self._report_location.clear()
        self._report_notes.clear()
        self.reload()

    def _populate_hazards(self, rows: list[dict[str, Any]]) -> None:
        self._hazard_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            values = [
                str(row.get("sub_activity", "")),
                str(row.get("hazard_outcome", "")),
                str(row.get("initial_risk", "")),
                str(row.get("residual_risk", "")),
                str(row.get("control_text", "")),
            ]
            for col_idx, value in enumerate(values):
                self._hazard_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _populate_reports(self, rows: list[dict[str, Any]]) -> None:
        self._report_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            values = [
                str(row.get("time", "")),
                str(row.get("location", "")),
                str(row.get("severity", "")),
                str(row.get("notes", "")),
            ]
            for col_idx, value in enumerate(values):
                self._report_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _update_summary(self, hazards: list[dict[str, Any]], reports: list[dict[str, Any]], form: dict[str, Any]) -> None:
        highest = str(form.get("highest_residual_risk", "L"))
        blocked = bool(form.get("approval_blocked"))
        high_hazards = [row for row in hazards if str(row.get("residual_risk", "")).upper() in {"H", "EH"}]
        flagged_reports = [row for row in reports if row.get("flagged")]
        lines = [
            f"Operational hazards logged: {len(hazards)}",
            f"Highest residual risk: {highest}",
            f"Approval blocked by ORM state: {'Yes' if blocked else 'No'}",
            f"High / Extremely High residual hazards: {len(high_hazards)}",
            f"Flagged safety reports: {len(flagged_reports)}",
        ]
        if high_hazards:
            lines.append("")
            lines.append("Immediate hazard concerns:")
            for row in high_hazards[:5]:
                lines.append(f"- {row.get('sub_activity', '')}: {row.get('hazard_outcome', '')} [{row.get('residual_risk', '')}]")
        if flagged_reports:
            lines.append("")
            lines.append("Flagged safety reports:")
            for row in flagged_reports[:5]:
                lines.append(f"- {row.get('severity', '')} at {row.get('location', '')}: {row.get('notes', '')}")
        self._summary.setPlainText("\n".join(lines))

    def reload(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._hazard_table.setRowCount(0)
            self._report_table.setRowCount(0)
            self._summary.clear()
            self._context.setText("No active incident selected")
            self._set_status("Select an incident to use Hazards.", error=True)
            return
        try:
            form = self._api_get(f"/api/incidents/{incident_id}/safety/orm/form", params={"op": 1}) or {}
            hazards = self._api_get(f"/api/incidents/{incident_id}/safety/orm/hazards", params={"op": 1}) or []
            reports = self._api_get(f"/api/incidents/{incident_id}/safety/reports") or []
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._context.setText(f"Incident {incident_id}")
        self._populate_hazards(hazards)
        self._populate_reports(reports)
        self._update_summary(hazards, reports, form)
        self._set_status(f"{len(hazards)} hazards | {len(reports)} safety reports | residual {form.get('highest_residual_risk', 'L')}")
