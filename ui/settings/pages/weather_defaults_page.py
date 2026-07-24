"""Weather Thresholds settings page — the user's personal default Go/No-Go
thresholds, seeded into every new incident this user creates.

`binding.py` has no float-spinbox helper, so this page talks to the settings
bridge directly (same `getSetting`/`setSetting` contract `bind_*` helpers
use) rather than adding a one-off binder for a single page.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from modules.intel.weather.services.thresholds import (
    DEFAULT_AVIATION_THRESHOLDS,
    DEFAULT_GROUND_THRESHOLDS,
)

GROUND_FIELDS = [
    ("wind_gust_marginal_mph", "Wind gust — marginal (mph)"),
    ("wind_gust_nogo_mph", "Wind gust — no-go (mph)"),
    ("visibility_marginal_mi", "Visibility — marginal (mi)"),
    ("visibility_nogo_mi", "Visibility — no-go (mi)"),
    ("ceiling_marginal_ft", "Ceiling — marginal (ft)"),
    ("ceiling_nogo_ft", "Ceiling — no-go (ft)"),
    ("heat_index_marginal_f", "Heat index — marginal (°F)"),
    ("heat_index_nogo_f", "Heat index — no-go (°F)"),
]

AVIATION_FIELDS = [
    ("wind_gust_marginal_kt", "Wind gust — marginal (kt)"),
    ("wind_gust_nogo_kt", "Wind gust — no-go (kt)"),
    ("visibility_marginal_sm", "Visibility — marginal (sm)"),
    ("visibility_nogo_sm", "Visibility — no-go (sm)"),
    ("ceiling_marginal_ft_agl", "Ceiling — marginal (ft AGL)"),
    ("ceiling_nogo_ft_agl", "Ceiling — no-go (ft AGL)"),
    ("crosswind_marginal_kt", "Crosswind — marginal (kt)"),
    ("crosswind_nogo_kt", "Crosswind — no-go (kt)"),
]


def _bind_double_spinbox(spin: QDoubleSpinBox, bridge: Any, key: str, default: float) -> None:
    getter = getattr(bridge, "getSetting", None)
    value = None
    if getter is not None:
        try:
            value = getter(key)
        except Exception:
            value = None
    spin.setValue(float(value) if value is not None else default)
    setter = getattr(bridge, "setSetting", None)
    if setter is not None:
        spin.valueChanged.connect(lambda val, setter=setter: setter(key, float(val)))


class WeatherDefaultsPage(QWidget):
    """Personal default Go/No-Go weather thresholds, seeded into new incidents."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        note = QLabel(
            "These are your personal default Go/No-Go weather thresholds. When you "
            "create a new incident, its weather thresholds start from these values; "
            "editing them here does not change any incident that already exists."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        ground_box = QGroupBox("Ground operations")
        ground_form = QFormLayout(ground_box)
        for key, label in GROUND_FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(0, 999)
            spin.setDecimals(1)
            _bind_double_spinbox(spin, bridge, f"weatherDefaults.ground.{key}", DEFAULT_GROUND_THRESHOLDS[key])
            ground_form.addRow(label, spin)
        layout.addWidget(ground_box)

        aviation_box = QGroupBox("Aviation")
        aviation_form = QFormLayout(aviation_box)
        for key, label in AVIATION_FIELDS:
            spin = QDoubleSpinBox()
            spin.setRange(0, 999)
            spin.setDecimals(1)
            _bind_double_spinbox(spin, bridge, f"weatherDefaults.aviation.{key}", DEFAULT_AVIATION_THRESHOLDS[key])
            aviation_form.addRow(label, spin)
        layout.addWidget(aviation_box)

        layout.addStretch(1)


def read_weather_defaults(bridge: Any) -> dict:
    """Return {'ground': {...}, 'aviation': {...}} from the saved settings, filling
    in hardcoded defaults for anything the user never touched."""
    getter = getattr(bridge, "getSetting", None)

    def _get(key: str, default: float) -> float:
        if getter is None:
            return default
        try:
            value = getter(key)
        except Exception:
            return default
        return float(value) if value is not None else default

    ground = {key: _get(f"weatherDefaults.ground.{key}", default) for key, default in DEFAULT_GROUND_THRESHOLDS.items()}
    aviation = {
        key: _get(f"weatherDefaults.aviation.{key}", default) for key, default in DEFAULT_AVIATION_THRESHOLDS.items()
    }
    return {"ground": ground, "aviation": aviation}


__all__ = ["WeatherDefaultsPage", "read_weather_defaults", "GROUND_FIELDS", "AVIATION_FIELDS"]
