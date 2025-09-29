from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QLineEdit,
    QGroupBox,
)

from ._geometry import GeometryHelper


class WeatherSettingsDialog(QDialog):
    saved = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Weather Settings")
        GeometryHelper.restore(self, "WeatherSettingsDialog")
        v = QVBoxLayout(self)
        grpGen = QGroupBox("General"); fg = QFormLayout(grpGen)
        self.comboPoll = QComboBox(); self.comboPoll.addItems(["1 min", "5 min", "10 min", "30 min", "1 hr"]) ; fg.addRow("Polling interval:", self.comboPoll)
        self.chkSound = QCheckBox("Enable alert sound"); fg.addRow("", self.chkSound)
        self.sliderVol = QSpinBox(); self.sliderVol.setRange(0, 100); self.sliderVol.setValue(70); fg.addRow("Volume:", self.sliderVol)
        self.comboSeverity = QComboBox(); self.comboSeverity.addItems(["All", "Moderate+", "Severe/Extreme"]) ; fg.addRow("Severity filter:", self.comboSeverity)
        self.spnDup = QSpinBox(); self.spnDup.setRange(0, 180); self.spnDup.setValue(30); fg.addRow("Duplicate suppression (min):", self.spnDup)

        grpData = QGroupBox("Data"); fd = QFormLayout(grpData)
        self.chkHourly = QCheckBox("Store hourly snapshots") ; fd.addRow("", self.chkHourly)
        self.lblStorage = QLabel("~3 MB/week/incident") ; fd.addRow("Storage estimate:", self.lblStorage)
        self.comboTZ = QComboBox(); self.comboTZ.addItems(["Local", "UTC"]) ; fd.addRow("Timezone display:", self.comboTZ)

        grpPerm = QGroupBox("Permissions"); fp = QFormLayout(grpPerm)
        self.txtRoles = QLineEdit(); self.txtRoles.setPlaceholderText("Safety Officer, IC") ; fp.addRow("Override requires:", self.txtRoles)

        v.addWidget(grpGen); v.addWidget(grpData); v.addWidget(grpPerm)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        v.addWidget(buttons)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._on_save)

    def closeEvent(self, e):
        GeometryHelper.save(self, "WeatherSettingsDialog")
        super().closeEvent(e)

    def _on_save(self) -> None:
        cfg = {
            "poll": self.comboPoll.currentText(),
            "sound": self.chkSound.isChecked(),
            "volume": self.sliderVol.value(),
            "severity": self.comboSeverity.currentText(),
            "dup": self.spnDup.value(),
            "hourly": self.chkHourly.isChecked(),
            "tz": self.comboTZ.currentText(),
            "roles": self.txtRoles.text(),
        }
        self.saved.emit(cfg)
        self.accept()

