"""Small reusable severity/Go-Marginal-No-Go badge, theme-aware."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from utils.styles import subscribe_theme, weather_severity_colors


class SeverityBadge(QLabel):
    def __init__(self, text: str = "", key: str = "unknown", parent=None):
        super().__init__(text, parent)
        self._key = key
        self.setAlignment(Qt.AlignCenter)
        subscribe_theme(self, self._repaint)
        self.set_key(key, text)

    def set_key(self, key: str, text: str | None = None) -> None:
        self._key = (key or "unknown").lower()
        if text is not None:
            self.setText(text.upper())
        self._repaint()

    def _repaint(self, _theme_name: str = "") -> None:
        colors = weather_severity_colors()
        palette = colors.get(self._key, colors.get("unknown"))
        bg = palette["bg"].color().name()
        fg = palette["fg"].color().name()
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 4px; "
            "padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )


__all__ = ["SeverityBadge"]
