from __future__ import annotations

"""Shared color constants used across QtWidgets panels."""

from typing import Dict

from styles.profiles import load_profile

try:  # pragma: no cover - allow usage without Qt bindings available
    from PySide6.QtGui import QColor
except ImportError:  # pragma: no cover
    class QColor:  # minimal stub used for testing environments without Qt
        def __init__(self, value: str | tuple[int, int, int]):
            if isinstance(value, str):
                self._value = value
            else:
                r, g, b = (list(value) + [0, 0, 0])[:3]
                self._value = f"#{r:02x}{g:02x}{b:02x}"

        def name(self) -> str:
            return self._value


def _ensure_qcolor(value: str | tuple[int, int, int] | QColor) -> QColor:
    if isinstance(value, QColor):
        return value
    return QColor(value)


_profile = load_profile()
_named_colors = getattr(_profile, "NAMED_COLORS", {})

COLORS: Dict[str, QColor] = {
    key: _ensure_qcolor(value)
    for key, value in _named_colors.items()
}


def _color(name: str, fallback: str) -> QColor:
    return COLORS.get(name, _ensure_qcolor(fallback))


PRIMARY_BLUE = _color("PRIMARY_BLUE", "#1f6feb")
ACCENT_ORANGE = _color("ACCENT_ORANGE", "#d29922")
MUTED_TEXT = _color("MUTED_TEXT", "#6e7781")
SUCCESS_GREEN = _color("SUCCESS_GREEN", "#2da44e")
WARNING_RED = _color("WARNING_RED", "#cf222e")
INFO_BLUE = _color("INFO_BLUE", "#338eda")
DANGER_RED = _color("DANGER_RED", "#d64545")

__all__ = [
    "COLORS",
    "PRIMARY_BLUE",
    "ACCENT_ORANGE",
    "MUTED_TEXT",
    "SUCCESS_GREEN",
    "WARNING_RED",
    "INFO_BLUE",
    "DANGER_RED",
]
