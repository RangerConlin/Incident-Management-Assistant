"""Dialog for creating a new incident."""
from __future__ import annotations

from dataclasses import dataclass
import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.styles import form_dialog_stylesheet, subscribe_theme


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


def _load_creator_weather_thresholds() -> dict:
    """Read this user's saved Weather Thresholds defaults (ui.settings.pages.weather_defaults_page),
    falling back to hardcoded defaults for anything never touched. Returns None on any failure
    (server falls back to its own hardcoded defaults if this field is omitted)."""
    try:
        from utils.settingsmanager import SettingsManager
        from modules.intel.weather.services.thresholds import (
            DEFAULT_AVIATION_THRESHOLDS,
            DEFAULT_GROUND_THRESHOLDS,
        )

        manager = SettingsManager()
        ground = {
            key: float(manager.get(f"weatherDefaults.ground.{key}", default))
            for key, default in DEFAULT_GROUND_THRESHOLDS.items()
        }
        aviation = {
            key: float(manager.get(f"weatherDefaults.aviation.{key}", default))
            for key, default in DEFAULT_AVIATION_THRESHOLDS.items()
        }
        return {"ground": ground, "aviation": aviation}
    except Exception:
        return None


class NewIncidentDialog(QDialog):
    """Collect incident metadata and emit a creation signal."""

    # Emits (meta, incident_id) where incident_id is the MongoDB UUID string
    created = Signal(IncidentMeta, str)
    cancelled = Signal()

    def __init__(self, parent: None | QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("NewIncidentDialog")
        self.setWindowTitle("New Incident")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Oak Ridge Search")
        self._number = QLineEdit()
        self._number.setPlaceholderText("e.g. 26-118")
        self._type = QComboBox()
        self._type.addItems(_load_incident_types())
        self._desc = QLineEdit()
        self._desc.setPlaceholderText("Brief summary of the incident")
        self._location = QLineEdit()
        self._location.setPlaceholderText("ICP address or coordinates")
        self._training = QCheckBox("Training incident")

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_create = QPushButton("Create Incident")
        self.btn_create.setObjectName("primaryButton")
        self.btn_create.setDefault(True)

        title = QLabel("New Incident")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Set up a new incident record to start operations.")
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)

        name_row = QHBoxLayout()
        name_row.addWidget(self._labeled_field("Name", self._name), 2)
        name_row.addWidget(self._labeled_field("Number", self._number), 1)
        layout.addLayout(name_row)

        layout.addWidget(self._labeled_field("Type", self._type))
        layout.addWidget(self._labeled_field("Description", self._desc))
        layout.addWidget(self._labeled_field("ICP Location", self._location))
        layout.addWidget(self._training)

        layout.addSpacing(6)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.btn_cancel)
        button_row.addWidget(self.btn_create)
        layout.addLayout(button_row)

        self.btn_create.clicked.connect(self._handle_accept)
        self.btn_cancel.clicked.connect(self._handle_reject)

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

    def _labeled_field(self, label_text: str, field: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(field)
        return wrap

    def _apply_styles(self) -> None:
        self.setStyleSheet(form_dialog_stylesheet("NewIncidentDialog"))

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
            payload = {
                "number": meta.number,
                "name": meta.name,
                "type": meta.type,
                "description": meta.description,
                "icp_location": meta.location,
                "is_training": meta.is_training,
            }
            weather_thresholds = _load_creator_weather_thresholds()
            if weather_thresholds is not None:
                payload["weather_thresholds"] = weather_thresholds
            result = api_client.post("/api/incidents", json=payload)
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
