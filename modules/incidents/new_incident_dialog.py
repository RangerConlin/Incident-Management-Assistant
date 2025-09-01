"""Dialog for creating a new incident.

Both the main menu action and the Incident Selection window reuse this
dialog. It gathers basic incident metadata and creates a placeholder
SQLite database for the incident.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from utils.incident_db import create_incident_database
from models.database import get_incident_by_number


@dataclass(slots=True)
class IncidentMeta:
    """Simple container for incident metadata."""

    number: str
    name: str
    type: str
    description: str
    location: str
    is_training: bool

    def slug(self) -> str:
        """Return a filesystem-friendly slug.

        Uses the incident number if available; otherwise falls back to the
        name. Non-alphanumeric characters are replaced with hyphens and the
        result is lowercased.
        """
        base = self.number or self.name
        slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
        return slug or "incident"


class NewIncidentDialog(QDialog):
    """Collect incident metadata and emit a creation signal."""

    created = Signal(IncidentMeta, str)
    cancelled = Signal()

    def __init__(self, parent: None | QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Incident")
        self.setModal(True)

        self._name = QLineEdit()
        self._number = QLineEdit()
        self._type = QComboBox()
        self._type.addItems(["SAR", "Disaster Response"])
        self._desc = QLineEdit()
        self._location = QLineEdit()
        self._training = QCheckBox("Training Incident?")

        form = QFormLayout()
        form.addRow("Name", self._name)
        form.addRow("Number", self._number)
        form.addRow("Type", self._type)
        form.addRow("Description", self._desc)
        form.addRow("ICP Location", self._location)
        form.addRow(self._training)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self._handle_reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _handle_accept(self) -> None:
        meta = IncidentMeta(
            number=self._number.text().strip(),
            name=self._name.text().strip(),
            type=self._type.currentText().strip(),
            description=self._desc.text().strip(),
            location=self._location.text().strip(),
            is_training=self._training.isChecked(),
        )
        if not meta.name or not meta.number:
            QMessageBox.warning(self, "Missing Data", "Name and Number are required.")
            return

        # Prevent duplicates: check master for existing incident number
        try:
            existing = get_incident_by_number(meta.number)
            if existing:
                QMessageBox.warning(
                    self,
                    "Duplicate Incident",
                    f"An incident with number '{meta.number}' already exists.",
                )
                return
        except Exception:
            # If master.db is unavailable, still proceed to file-level check
            pass

        # Create incident DB named after the incident number; prevent overwrite
        try:
            db_path = create_incident_database(meta.number)
        except FileExistsError as e:
            QMessageBox.warning(self, "Already Exists", str(e))
            return

        self.created.emit(meta, str(db_path))
        self.accept()

    def _handle_reject(self) -> None:
        self.cancelled.emit()
        self.reject()


__all__ = ["IncidentMeta", "NewIncidentDialog"]

