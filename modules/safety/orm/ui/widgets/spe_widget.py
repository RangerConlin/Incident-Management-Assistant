"""Reusable Severity x Probability x Exposure (SPE) input widget."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QSpinBox, QWidget

from ...scoring import EXPOSURE_RANGE, PROBABILITY_RANGE, SEVERITY_RANGE, spe_band, spe_score

_BAND_COLORS = {
    "Very High": ("#c62828", "white"),
    "High": ("#ef6c00", "white"),
    "Substantial": ("#f9a825", "black"),
    "Possible": ("#fdd835", "black"),
    "Slight": ("#2e7d32", "white"),
}


class SpeWidget(QWidget):
    """Severity / Probability / Exposure inputs with a live score + degree chip."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None, *, default_enabled: bool = True) -> None:
        super().__init__(parent)

        self.enabled_checkbox = QCheckBox("Assessed")
        self.enabled_checkbox.setChecked(default_enabled)
        self.enabled_checkbox.toggled.connect(self._on_toggle)

        self.severity = QSpinBox()
        self.severity.setRange(*SEVERITY_RANGE)
        self.probability = QSpinBox()
        self.probability.setRange(*PROBABILITY_RANGE)
        self.exposure = QSpinBox()
        self.exposure.setRange(*EXPOSURE_RANGE)

        self.score_chip = QLabel()
        self.score_chip.setAlignment(Qt.AlignCenter)
        self.score_chip.setFixedHeight(28)

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(self.enabled_checkbox)
        layout.addRow("Severity (1-5)", self.severity)
        layout.addRow("Probability (1-5)", self.probability)
        layout.addRow("Exposure (1-4)", self.exposure)
        layout.addRow("Score", self.score_chip)

        for spin in (self.severity, self.probability, self.exposure):
            spin.valueChanged.connect(self._recompute)

        self._on_toggle(default_enabled)

    def _on_toggle(self, checked: bool) -> None:
        for spin in (self.severity, self.probability, self.exposure):
            spin.setEnabled(checked)
        self._recompute()

    def _recompute(self) -> None:
        if not self.enabled_checkbox.isChecked():
            self.score_chip.setText("Not assessed")
            self.score_chip.setStyleSheet("")
            self.changed.emit()
            return
        score = spe_score(self.severity.value(), self.probability.value(), self.exposure.value())
        degree, action = spe_band(score)
        color, text_color = _BAND_COLORS.get(degree, ("#616161", "white"))
        self.score_chip.setText(f"{score} — {degree} ({action})")
        self.score_chip.setStyleSheet(
            "border-radius: 14px; padding: 4px 12px; font-weight: 600; "
            f"background-color: {color}; color: {text_color};"
        )
        self.changed.emit()

    def value(self) -> Optional[dict[str, int]]:
        if not self.enabled_checkbox.isChecked():
            return None
        return {
            "severity": self.severity.value(),
            "probability": self.probability.value(),
            "exposure": self.exposure.value(),
        }

    def set_value(self, assessment: Optional[dict]) -> None:
        if not assessment:
            self.enabled_checkbox.setChecked(False)
            return
        self.enabled_checkbox.setChecked(True)
        self.severity.setValue(int(assessment.get("severity", 1)))
        self.probability.setValue(int(assessment.get("probability", 1)))
        self.exposure.setValue(int(assessment.get("exposure", 1)))
        self._recompute()
