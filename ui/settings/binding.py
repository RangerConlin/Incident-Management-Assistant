"""Utility helpers for connecting widgets to the settings bridge."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QCheckBox, QComboBox, QSlider, QSpinBox

Setter = Callable[[str, Any], None]


def _safe_get(bridge: QObject, key: str) -> Any:
    """Return a stored value from the bridge, swallowing attribute errors."""
    getter = getattr(bridge, "getSetting", None)
    if getter is None:
        return None
    try:
        return getter(key)
    except Exception:  # pragma: no cover - defensive, bridge should not raise
        return None


def _safe_setter(bridge: QObject) -> Setter:
    setter = getattr(bridge, "setSetting", None)
    if setter is None:
        raise AttributeError("settings bridge must expose setSetting")
    return setter


def bind_checkbox(box: QCheckBox, bridge: QObject, key: str, default: bool = False) -> None:
    """Bind a checkbox to a boolean setting."""
    value = _safe_get(bridge, key)
    checked = default if value is None else bool(value)
    box.setChecked(checked)
    setter = _safe_setter(bridge)
    box.toggled.connect(lambda state, setter=setter: setter(key, bool(state)))


def bind_combobox(combo: QComboBox, bridge: QObject, key: str, default_index: int = 0) -> None:
    """Bind a combo box index to a numeric setting."""
    value = _safe_get(bridge, key)
    index = default_index if value is None else int(value)
    combo.setCurrentIndex(index)
    setter = _safe_setter(bridge)
    combo.currentIndexChanged.connect(lambda idx, setter=setter: setter(key, int(idx)))


def bind_spinbox(spin: QSpinBox, bridge: QObject, key: str, default: int = 0) -> None:
    """Bind a spin box value to an integer setting."""
    value = _safe_get(bridge, key)
    number = default if value is None else int(value)
    spin.setValue(number)
    setter = _safe_setter(bridge)
    spin.valueChanged.connect(lambda val, setter=setter: setter(key, int(val)))


def bind_slider(slider: QSlider, bridge: QObject, key: str, default: int = 0) -> None:
    """Bind a slider value to an integer setting."""
    value = _safe_get(bridge, key)
    number = default if value is None else int(value)
    slider.setValue(number)
    setter = _safe_setter(bridge)
    slider.valueChanged.connect(lambda val, setter=setter: setter(key, int(val)))
