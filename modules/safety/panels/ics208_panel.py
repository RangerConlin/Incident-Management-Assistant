"""ICS-208 Safety Message panel — one document per operational period."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.safety import services
from utils.api_client import api_client
from utils.state import AppState


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    font = QFont()
    font.setBold(True)
    font.setPointSize(9)
    lbl.setFont(font)
    lbl.setStyleSheet("color: #1a237e; padding-top: 6px;")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #e0e0e0;")
    return line


class ICS208Panel(QWidget):
    """Safety Message (ICS-208) panel — per op period, single save."""

    def __init__(self, incident_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setStyleSheet("background: #e8eaf6; padding: 6px;")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(12, 6, 12, 6)
        title = QLabel("Safety Message (ICS-208)")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1a237e;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Op Period:"))
        self._op_spin = QSpinBox()
        self._op_spin.setRange(1, 99)
        self._op_spin.setValue(int(AppState.get_active_op_period() or 1))
        self._op_spin.setFixedWidth(60)
        self._op_spin.valueChanged.connect(self._load)
        header_layout.addWidget(self._op_spin)
        outer.addWidget(header_bar)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Op period dates
        layout.addWidget(_section_label("Operational Period"))
        date_grid = QGridLayout()
        date_grid.setHorizontalSpacing(12)
        self._op_from = QLineEdit()
        self._op_from.setPlaceholderText("Date/Time From (YYYY-MM-DD HH:MM)")
        self._op_to = QLineEdit()
        self._op_to.setPlaceholderText("Date/Time To (YYYY-MM-DD HH:MM)")
        date_grid.addWidget(QLabel("From:"), 0, 0)
        date_grid.addWidget(self._op_from, 0, 1)
        date_grid.addWidget(QLabel("To:"), 0, 2)
        date_grid.addWidget(self._op_to, 0, 3)
        layout.addLayout(date_grid)

        layout.addWidget(_divider())

        # Safety message — the core of the form
        layout.addWidget(_section_label("Safety Message"))
        self._safety_message = QTextEdit()
        self._safety_message.setPlaceholderText(
            "Enter the safety message / briefing for this operational period.\n\n"
            "Include: known hazards, required PPE, hot zones, evacuation routes, "
            "emergency signals, weather concerns, and any other safety-critical information "
            "personnel must know before beginning operations."
        )
        self._safety_message.setMinimumHeight(220)
        layout.addWidget(self._safety_message)

        # 215A import hook
        import_row = QHBoxLayout()
        self._import_hazards_btn = QPushButton("Import Hazards from ICS-215A")
        self._import_hazards_btn.setToolTip(
            "Appends unresolved High / Extreme hazards from ICS-215A to the safety message"
        )
        self._import_hazards_btn.setStyleSheet(
            "background: #e8eaf6; color: #1a237e; font-weight: 600;"
            "padding: 4px 12px; border: 1px solid #9fa8da; border-radius: 3px;"
        )
        self._import_hazards_btn.clicked.connect(self._import_from_215a)
        import_row.addWidget(self._import_hazards_btn)
        import_row.addStretch()
        layout.addLayout(import_row)

        layout.addWidget(_divider())

        # Site safety plan
        layout.addWidget(_section_label("Site Safety Plan"))
        site_row = QHBoxLayout()
        self._site_plan_required = QCheckBox("Site safety plan required for this incident")
        site_row.addWidget(self._site_plan_required)
        site_row.addStretch()
        layout.addLayout(site_row)
        layout.addWidget(QLabel("Approved site safety plan(s) located at:"))
        self._site_plan_location = QLineEdit()
        self._site_plan_location.setPlaceholderText("Location / file path / document reference")
        layout.addWidget(self._site_plan_location)

        layout.addWidget(_divider())

        # Prepared by
        layout.addWidget(_section_label("Prepared By"))
        sig_grid = QGridLayout()
        sig_grid.setHorizontalSpacing(12)
        self._prepared_by_name = QLineEdit()
        self._prepared_by_name.setPlaceholderText("Name")
        self._prepared_by_position = QLineEdit()
        self._prepared_by_position.setPlaceholderText("Position / ICS Title")
        self._prepared_by_datetime = QLineEdit()
        self._prepared_by_datetime.setPlaceholderText("Date / Time")
        sig_grid.addWidget(QLabel("Name:"), 0, 0)
        sig_grid.addWidget(self._prepared_by_name, 0, 1)
        sig_grid.addWidget(QLabel("Position:"), 0, 2)
        sig_grid.addWidget(self._prepared_by_position, 0, 3)
        sig_grid.addWidget(QLabel("Date / Time:"), 0, 4)
        sig_grid.addWidget(self._prepared_by_datetime, 0, 5)
        layout.addLayout(sig_grid)

        layout.addSpacing(12)

        # Save
        save_row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(
            "background-color: #1a237e; color: white; font-weight: 600; padding: 6px 20px; border-radius: 4px;"
        )
        self._save_btn.clicked.connect(self._save)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #2e7d32; font-size: 11px;")
        save_row.addWidget(self._save_btn)
        save_row.addWidget(self._status_lbl)
        save_row.addStretch()
        layout.addLayout(save_row)
        layout.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _load(self) -> None:
        if not self._incident_id:
            return
        self._status_lbl.setText("")
        op = self._op_spin.value()
        try:
            data = services.get_ics208(self._incident_id, op)
        except Exception:
            data = {}
        self._op_from.setText(data.get("op_period_from") or "")
        self._op_to.setText(data.get("op_period_to") or "")
        self._safety_message.setPlainText(data.get("safety_message") or "")
        self._site_plan_required.setChecked(bool(data.get("site_safety_plan_required", False)))
        self._site_plan_location.setText(data.get("site_safety_plan_location") or "")
        self._prepared_by_name.setText(data.get("prepared_by_name") or "")
        self._prepared_by_position.setText(data.get("prepared_by_position") or "")
        self._prepared_by_datetime.setText(data.get("prepared_by_datetime") or "")

    def _import_from_215a(self) -> None:
        """Append unresolved High/Extreme hazards from ICS-215A into the safety message."""
        if not self._incident_id:
            return
        try:
            was = api_client.get(
                f"/api/incidents/{self._incident_id}/planning/work-assignments"
            ) or []
        except Exception:
            QMessageBox.warning(self, "Import Failed", "Could not reach the server.")
            return

        target_risks = {"High", "Extreme"}
        lines: list[str] = []
        for wa in was:
            if wa.get("is_archived"):
                continue
            for h in (wa.get("hazards") or []):
                if h.get("is_resolved"):
                    continue
                if h.get("risk_level") not in target_risks:
                    continue
                wa_label = wa.get("assignment_number") or wa.get("assignment_name") or ""
                risk = h.get("risk_level", "")
                text = h.get("hazard_type_text", "Unnamed hazard")
                control = h.get("control_measure") or h.get("mitigation_text") or ""
                ppe = h.get("ppe_text") or ""
                line = f"[{risk}] {text}"
                if wa_label:
                    line += f" ({wa_label})"
                if control:
                    line += f" — Control: {control}"
                if ppe:
                    line += f"  PPE: {ppe}"
                lines.append(line)

        if not lines:
            QMessageBox.information(
                self, "No Hazards Found",
                "No unresolved High or Extreme hazards found in ICS-215A."
            )
            return

        header = "\n\n--- Imported from ICS-215A ---\n"
        existing = self._safety_message.toPlainText().rstrip()
        self._safety_message.setPlainText(
            existing + header + "\n".join(lines)
        )
        self._status_lbl.setText(f"Imported {len(lines)} hazard(s) — remember to save.")
        self._status_lbl.setStyleSheet("color: #e65100; font-size: 11px;")

    def _save(self) -> None:
        if not self._incident_id:
            QMessageBox.warning(self, "No Incident", "Select an incident before saving.")
            return
        payload = {
            "op_period": self._op_spin.value(),
            "op_period_from": self._op_from.text().strip(),
            "op_period_to": self._op_to.text().strip(),
            "safety_message": self._safety_message.toPlainText().strip(),
            "site_safety_plan_required": self._site_plan_required.isChecked(),
            "site_safety_plan_location": self._site_plan_location.text().strip(),
            "prepared_by_name": self._prepared_by_name.text().strip(),
            "prepared_by_position": self._prepared_by_position.text().strip(),
            "prepared_by_datetime": self._prepared_by_datetime.text().strip(),
        }
        try:
            services.save_ics208(self._incident_id, payload)
            self._status_lbl.setText("Saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
