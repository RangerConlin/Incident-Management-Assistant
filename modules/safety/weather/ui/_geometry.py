from __future__ import annotations

from PySide6.QtCore import QSettings


class GeometryHelper:
    @staticmethod
    def restore(widget, key: str) -> None:
        try:
            s = QSettings("SARApp", "WeatherUI")
            g = s.value(f"{key}/geometry")
            if g:
                widget.restoreGeometry(g)
        except Exception:
            pass

    @staticmethod
    def save(widget, key: str) -> None:
        try:
            s = QSettings("SARApp", "WeatherUI")
            s.setValue(f"{key}/geometry", widget.saveGeometry())
        except Exception:
            pass

