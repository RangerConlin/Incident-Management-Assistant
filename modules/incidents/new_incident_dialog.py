"""Dialog for creating a new incident."""
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
        base = self.number or self.name
        slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
        return slug or "incident"


def _load_incident_types() -> list[str]:
    try:
        from utils.api_client import api_client
        types = api_client.get("/api/lookup/incident-types") or []
        if types:
            return types
    except Exception:
        pass
    return ["SAR", "Disaster Response"]


class NewIncidentDialog(QDialog):
    """Collect incident metadata and emit a creation signal."""

    # Emits (meta, incident_id) where incident_id is the MongoDB UUID string
    created = Signal(IncidentMeta, str)
    cancelled = Signal()

    def __init__(self, parent: None | QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Incident")
        self.setModal(True)

        self._name = QLineEdit()
        self._number = QLineEdit()
        self._type = QComboBox()
        self._type.addItems(_load_incident_types())
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

        try:
            from utils.api_client import api_client
            result = api_client.post(
                "/api/incidents",
                json={
                    "number": meta.number,
                    "name": meta.name,
                    "type": meta.type,
                    "description": meta.description,
                    "icp_location": meta.location,
                    "is_training": meta.is_training,
                },
            )
            if result is None:
                QMessageBox.critical(self, "Error", "Failed to create incident: no response from server.")
                return
            incident_id = result.get("incident_id") or result.get("id", "")
        except Exception as e:
            err = str(e)
            if "409" in err or "already exists" in err.lower():
                QMessageBox.warning(
                    self,
                    "Duplicate Incident",
                    f"An incident with number '{meta.number}' already exists.",
                )
            else:
                QMessageBox.critical(self, "Incident Creation Error", err)
            return

        self.created.emit(meta, incident_id)
        self.accept()

    def _handle_reject(self) -> None:
        self.cancelled.emit()
        self.reject()


__all__ = ["IncidentMeta", "NewIncidentDialog"]
