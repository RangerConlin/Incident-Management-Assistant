"""Quick clue capture dialog — posts canonical Intel Item clue records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from utils.api_client import api_client
from utils.state import AppState


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AddClueDialog(QDialog):
    """Lightweight dialog for logging a field clue from the comms area."""

    def __init__(self, parent=None, *, incident_id: Optional[str] = None,
                 prefill_team: Optional[str] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Field Clue")
        self.setModal(True)
        self.setMinimumWidth(480)

        self._incident_id = incident_id or str(AppState.get_active_incident() or "")
        self._teams: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Log Field Clue")
        header.setStyleSheet("font-size:14px; font-weight:700; color:#1a237e;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Brief identifying title")
        form.addRow("Title *", self._title)

        self._location = QLineEdit()
        self._location.setPlaceholderText("Grid ref, landmark, or description")
        form.addRow("Location", self._location)

        self._description = QTextEdit()
        self._description.setPlaceholderText("Describe the clue in detail…")
        self._description.setFixedHeight(100)
        form.addRow("Description", self._description)

        self._team_combo = QComboBox()
        self._team_combo.addItem("— Select Team —", None)
        form.addRow("Recorded By (Team)", self._team_combo)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background:#f5f5f5; color:#616161; border:1px solid #e0e0e0;"
            " border-radius:3px; padding:5px 16px; font-weight:600; }"
        )
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        self._save_btn = QPushButton("Save Clue")
        self._save_btn.setDefault(True)
        self._save_btn.setStyleSheet(
            "QPushButton { background:#1a237e; color:white; border-radius:3px;"
            " padding:5px 16px; font-weight:700; }"
            "QPushButton:hover { background:#283593; }"
        )
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

        self._load_teams()
        if prefill_team:
            idx = self._team_combo.findText(prefill_team)
            if idx >= 0:
                self._team_combo.setCurrentIndex(idx)

    def _load_teams(self) -> None:
        if not self._incident_id:
            return
        try:
            teams = api_client.get(f"/api/incidents/{self._incident_id}/operations/teams") or []
        except Exception:
            teams = []
        self._teams = teams
        for t in teams:
            label = t.get("name") or t.get("callsign") or f"Team {t.get('int_id','?')}"
            self._team_combo.addItem(label, t.get("int_id"))

    def _save(self) -> None:
        title = self._title.text().strip()
        if not title:
            QMessageBox.warning(self, "Required Field", "Title is required.")
            self._title.setFocus()
            return
        if not self._incident_id:
            QMessageBox.warning(self, "No Incident", "No active incident selected.")
            return

        team_id = self._team_combo.currentData()
        team_label = self._team_combo.currentText() if team_id else ""

        payload = {
            "item_type": "Clue",
            "title": title,
            "status": "Active",
            "priority": "Medium",
            "confidence": "Unconfirmed",
            "trend": "Unknown",
            "location_text": self._location.text().strip(),
            "linked_team_ids": [int(team_id)] if team_id else [],
            "notes": self._description.toPlainText().strip(),
            "created_by": str(AppState.get_current_user() or ""),
        }

        try:
            item = api_client.post(f"/api/incidents/{self._incident_id}/intel/items", json=payload)
            if item and self._description.toPlainText().strip():
                api_client.post(
                    f"/api/incidents/{self._incident_id}/intel/items/{item['id']}/observations",
                    json={
                        "observed_at": _utcnow(),
                        "observer": str(AppState.get_current_user() or ""),
                        "source_team": team_label if team_label and team_label != "— Select Team —" else None,
                        "source_team_id": int(team_id) if team_id else None,
                        "status": "Active",
                        "severity": "Unknown",
                        "confidence": "Unconfirmed",
                        "summary": title,
                        "detailed_notes": self._description.toPlainText().strip(),
                        "location_text": self._location.text().strip(),
                        "actor": str(AppState.get_current_user() or "system"),
                    },
                )
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        self.accept()


__all__ = ["AddClueDialog"]
