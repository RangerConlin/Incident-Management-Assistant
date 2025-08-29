"""Dialog for creating a new mission/incident.

Both the main menu action and the Incident Selection window reuse this
dialog. It gathers basic mission metadata and creates a placeholder
SQLite database for the mission.
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

from utils.mission_db import create_mission_db


@dataclass(slots=True)
class MissionMeta:
    """Simple container for mission metadata."""

    number: str
    name: str
    type: str
    description: str
    location: str
    is_training: bool

    def slug(self) -> str:
        """Return a filesystem-friendly slug.

        Uses the mission number if available; otherwise falls back to the
        name. Non-alphanumeric characters are replaced with hyphens and the
        result is lowercased.
        """
        base = self.number or self.name
        slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
        return slug or "mission"


class NewIncidentDialog(QDialog):
    """Collect mission metadata and emit a creation signal."""

    created = Signal(MissionMeta, str)
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
        meta = MissionMeta(
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

        slug = meta.slug()
        db_path = create_mission_db(slug)
        # TODO: register mission metadata in master.db

        self.created.emit(meta, str(db_path))
        self.accept()

    def _handle_reject(self) -> None:
        self.cancelled.emit()
        self.reject()


__all__ = ["MissionMeta", "NewIncidentDialog"]
