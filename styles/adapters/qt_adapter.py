"""Qt Widgets convenience wrapper."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from styles import styles as core


def apply_qt_theme(app: QApplication, mode: str = 'light') -> None:
    """Apply palette and keep updated on theme changes."""
    core.set_theme(mode)
    core.apply_app_palette(app)
    core.style_bus.THEME_CHANGED.connect(lambda m: core.apply_app_palette(app))


__all__ = ['apply_qt_theme']
