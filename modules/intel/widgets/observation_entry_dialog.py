"""ObservationEntryDialog — quick dialog for adding an observation to an Intel Item.

Designed for repeated field updates — the form is intentionally compact and
focused on the most critical fields.  The parent dialog opens on top of the
IntelItemDetailWindow without closing it.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QDialogButtonBox, QLabel, QDateTimeEdit, QWidget,
)
from PySide6.QtCore import QDateTime, Qt

from modules.intel.models.intel_items import (
    Observation, CONFIDENCE_VALUES, SEVERITY_VALUES,
)


class ObservationEntryDialog(QDialog):
    """Modal dialog for entering a new observation on an Intel Item."""

    def __init__(self, item_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add Observation — {item_title}")
        self.setMinimumWidth(480)
        self.observation: Observation | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel(f"New Observation: {item_title}")
        header.setStyleSheet("font-size: 14px; font-weight: 600; margin-bottom: 4px;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        # Observer
        self._observer = QLineEdit()
        self._observer.setPlaceholderText("Name or team designator")
        form.addRow("Observer", self._observer)

        # Date/time
        self._datetime = QDateTimeEdit(QDateTime.currentDateTime())
        self._datetime.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._datetime.setCalendarPopup(True)
        form.addRow("Date / Time", self._datetime)

        # Source team
        self._source_team = QLineEdit()
        self._source_team.setPlaceholderText("Optional — field team, unit, etc.")
        form.addRow("Source Team", self._source_team)

        # Status at time of observation
        self._status = QLineEdit()
        self._status.setPlaceholderText("e.g. Closed, Worsening, Under Investigation")
        form.addRow("Status", self._status)

        # Severity
        self._severity = QComboBox()
        self._severity.addItems(SEVERITY_VALUES)
        self._severity.setCurrentText("Low")
        form.addRow("Severity", self._severity)

        # Confidence
        self._confidence = QComboBox()
        self._confidence.addItems(CONFIDENCE_VALUES)
        self._confidence.setCurrentText("Unconfirmed")
        form.addRow("Confidence", self._confidence)

        # Location
        self._location = QLineEdit()
        self._location.setPlaceholderText("Optional location description")
        form.addRow("Location", self._location)

        # Summary (required)
        self._summary = QLineEdit()
        self._summary.setPlaceholderText("Brief summary of this observation (required)")
        form.addRow("Summary *", self._summary)

        # Detailed notes
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Detailed notes, measurements, or additional context")
        self._notes.setMinimumHeight(80)
        form.addRow("Detailed Notes", self._notes)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        summary = self._summary.text().strip()
        if not summary:
            self._summary.setStyleSheet("border: 1px solid #cf222e;")
            return
        dt = self._datetime.dateTime().toPython()
        import uuid
        self.observation = Observation(
            obs_id=str(uuid.uuid4()),
            observed_at=dt.isoformat(timespec="seconds"),
            observer=self._observer.text().strip(),
            source_team=self._source_team.text().strip() or None,
            status=self._status.text().strip(),
            severity=self._severity.currentText(),
            confidence=self._confidence.currentText(),
            summary=summary,
            detailed_notes=self._notes.toPlainText().strip() or None,
            location_text=self._location.text().strip() or None,
        )
        self.accept()
