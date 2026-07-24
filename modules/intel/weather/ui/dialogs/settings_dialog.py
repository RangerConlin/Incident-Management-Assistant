"""Per-incident Weather settings: polling interval + Go/No-Go thresholds.

Seeded from the creating user's app-wide Weather Thresholds defaults at
incident creation (see modules/incidents/new_incident_dialog.py and
data/db/sarapp_db/api/routers/ic_overview.py::_seed_weather_config);
editing here only affects this incident.
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ...services import weather_repository_client as client
from ...services.thresholds import DEFAULT_AVIATION_THRESHOLDS, DEFAULT_GROUND_THRESHOLDS
from ...services.weather_manager import WeatherManager
from ui.settings.pages.weather_defaults_page import AVIATION_FIELDS, GROUND_FIELDS


class WeatherSettingsDialog(QDialog):
    def __init__(self, manager: WeatherManager, incident_id: str, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._incident_id = incident_id
        self.setWindowTitle("Weather Settings")
        self.setModal(True)

        layout = QVBoxLayout(self)
        note = QLabel(
            "Seeded from your default thresholds — adjust for this incident's air ops/safety plan."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        self._polling_spin = QSpinBox()
        self._polling_spin.setRange(1, 120)
        self._polling_spin.setSuffix(" min")
        self._polling_spin.setValue(manager.polling_minutes())
        form.addRow("Polling interval", self._polling_spin)
        layout.addLayout(form)

        thresholds = manager.thresholds()
        ground = {**DEFAULT_GROUND_THRESHOLDS, **(thresholds.get("ground") or {})}
        aviation = {**DEFAULT_AVIATION_THRESHOLDS, **(thresholds.get("aviation") or {})}

        self._ground_spins: Dict[str, QDoubleSpinBox] = {}
        ground_box = QGroupBox("Ground operations")
        ground_form = QFormLayout(ground_box)
        for key, label in GROUND_FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(0, 999)
            spin.setDecimals(1)
            spin.setValue(ground[key])
            self._ground_spins[key] = spin
            ground_form.addRow(label, spin)
        layout.addWidget(ground_box)

        self._aviation_spins: Dict[str, QDoubleSpinBox] = {}
        aviation_box = QGroupBox("Aviation")
        aviation_form = QFormLayout(aviation_box)
        for key, label in AVIATION_FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(0, 999)
            spin.setDecimals(1)
            spin.setValue(aviation[key])
            self._aviation_spins[key] = spin
            aviation_form.addRow(label, spin)
        layout.addWidget(aviation_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        thresholds: Dict[str, Any] = {
            "ground": {key: spin.value() for key, spin in self._ground_spins.items()},
            "aviation": {key: spin.value() for key, spin in self._aviation_spins.items()},
        }
        try:
            client.update_config(
                self._incident_id,
                polling_minutes=self._polling_spin.value(),
                thresholds=thresholds,
            )
            self._manager.reload_config()
        finally:
            self.accept()
