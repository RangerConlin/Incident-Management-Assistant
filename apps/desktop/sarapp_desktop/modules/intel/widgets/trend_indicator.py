"""TrendIndicator — displays a trend arrow + label for Intel Items."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


_TREND_ICONS: dict[str, str] = {
    "Improving": "▲",
    "Stable":    "●",
    "Worsening": "▼",
    "Unknown":   "?",
}

_TREND_COLORS: dict[str, str] = {
    "Improving": "#2da44e",
    "Stable":    "#1f6feb",
    "Worsening": "#cf222e",
    "Unknown":   "#6e7781",
}


class TrendIndicator(QWidget):
    """Icon + label showing trend direction for an Intel Item.

    Usage::

        indicator = TrendIndicator("Worsening")
    """

    def __init__(self, trend: str = "Unknown", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._icon = QLabel()
        self._label = QLabel()

        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        layout.addStretch()

        self.set_trend(trend)

    def set_trend(self, trend: str) -> None:
        icon = _TREND_ICONS.get(trend, "?")
        color = _TREND_COLORS.get(trend, "#6e7781")
        style = f"color: {color}; font-weight: 600; font-size: 13px;"
        self._icon.setText(icon)
        self._icon.setStyleSheet(style)
        self._label.setText(trend)
        self._label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
