from __future__ import annotations

from typing import Callable, Dict, Literal

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette, QBrush
from PySide6.QtWidgets import QApplication, QWidget

THEME_NAME: Literal["light", "dark"] = "light"


class StyleBus(QObject):
    """Signal bus for style/theme changes."""

    THEME_CHANGED = Signal(str)


style_bus = StyleBus()


_LIGHT_PALETTE: Dict[str, QColor] = {
    "bg": QColor("#f5f5f5"),
    "fg": QColor("#000000"),
    "muted": QColor("#666666"),
    "accent": QColor("#003a67"),
    "success": QColor("#388e3c"),
    "warning": QColor("#ffa000"),
    "error": QColor("#d32f2f"),
}

_DARK_PALETTE: Dict[str, QColor] = {
    "bg": QColor("#2c2c2c"),
    "fg": QColor("#B4B4B4"),
    "muted": QColor("#888888"),
    "accent": QColor("#90caf9"),
    "success": QColor("#4caf50"),
    "warning": QColor("#ffb300"),
    "error": QColor("#ef5350"),
}

_TASK_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = {
    "created": {"bg": QBrush(QColor("#6e7b8b")), "fg": QBrush(QColor("#333333"))},
    "planned": {"bg": QBrush(QColor("#ce93d8")), "fg": QBrush(QColor("#333333"))},
    "assigned": {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "in progress": {"bg": QBrush(QColor("#17c4e8")), "fg": QBrush(QColor("#333333"))},
    "complete": {"bg": QBrush(QColor("#386a3c")), "fg": QBrush(QColor("#333333"))},
    "cancelled": {"bg": QBrush(QColor("#d32f2f")), "fg": QBrush(QColor("#333333"))},
}

_TASK_STATUS_DARK: Dict[str, Dict[str, QBrush]] = {
    k: {"bg": v["bg"], "fg": QBrush(QColor("#e0e0e0"))} for k, v in _TASK_STATUS_LIGHT.items()
}

_TEAM_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = {
    "aol": {"bg": QBrush(QColor("#085ec7")), "fg": QBrush(QColor("#e0e0e0"))},
    "arrival": {"bg": QBrush(QColor("#17c4eb")), "fg": QBrush(QColor("#333333"))},
    "assigned": {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "available": {"bg": QBrush(QColor("#388e3c")), "fg": QBrush(QColor("#ffffff"))},
    "break": {"bg": QBrush(QColor("#9c27b0")), "fg": QBrush(QColor("#333333"))},
    "briefed": {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "crew rest": {"bg": QBrush(QColor("#9c27b0")), "fg": QBrush(QColor("#333333"))},
    "enroute": {"bg": QBrush(QColor("#ffeb3b")), "fg": QBrush(QColor("#333333"))},
    "out of service": {"bg": QBrush(QColor("#d32f2f")), "fg": QBrush(QColor("#333333"))},
    "report writing": {"bg": QBrush(QColor("#ce93d8")), "fg": QBrush(QColor("#333333"))},
    "returning": {"bg": QBrush(QColor("#0288d1")), "fg": QBrush(QColor("#e1e1e1"))},
    "tol": {"bg": QBrush(QColor("#085ec7")), "fg": QBrush(QColor("#e0e0e0"))},
    "wheels down": {"bg": QBrush(QColor("#0288d1")), "fg": QBrush(QColor("#e1e1e1"))},
    "post incident": {"bg": QBrush(QColor("#ce93d8")), "fg": QBrush(QColor("#333333"))},
    "find": {"bg": QBrush(QColor("#ffa000")), "fg": QBrush(QColor("#333333"))},
    "complete": {"bg": QBrush(QColor("#386a3c")), "fg": QBrush(QColor("#333333"))},
}

_TEAM_STATUS_DARK: Dict[str, Dict[str, QBrush]] = {
    k: {"bg": v["bg"], "fg": QBrush(QColor("#e0e0e0"))} for k, v in _TEAM_STATUS_LIGHT.items()
}

TEAM_TYPE_COLORS: Dict[str, QColor] = {
    "GT": QColor("#228b22"),
    "UDF": QColor("#ffeb3b"),
    "LSAR": QColor("#228b22"),
    "DF": QColor("#ffeb3b"),
    "GT/UAS": QColor("#00b987"),
    "UDF/UAS": QColor("#ffd54f"),
    "UAS": QColor("#00cec9"),
    "AIR": QColor("#00a8ff"),
    "K9": QColor("#8b0000"),
    "UTIL": QColor("#7a7a7a"),
}


def get_palette() -> Dict[str, QColor]:
    """Return the active palette colors."""
    return _LIGHT_PALETTE if THEME_NAME == "light" else _DARK_PALETTE


def apply_app_palette(app: QApplication) -> None:
    """Apply the current palette to the application."""
    pal = QPalette()
    p = get_palette()
    pal.setColor(QPalette.Window, p["bg"])
    pal.setColor(QPalette.Base, p["bg"])
    pal.setColor(QPalette.AlternateBase, p["muted"])
    pal.setColor(QPalette.WindowText, p["fg"])
    pal.setColor(QPalette.Text, p["fg"])
    pal.setColor(QPalette.ButtonText, p["fg"])
    pal.setColor(QPalette.Button, p["bg"])
    pal.setColor(QPalette.Highlight, p["accent"])
    pal.setColor(QPalette.BrightText, p["fg"])
    app.setPalette(pal)


def set_theme(name: str) -> None:
    """Set the current theme and emit change signal."""
    global THEME_NAME
    name = name.lower()
    if name not in {"light", "dark"}:
        return
    if name == THEME_NAME:
        return
    THEME_NAME = name
    style_bus.THEME_CHANGED.emit(name)


def team_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _TEAM_STATUS_LIGHT if THEME_NAME == "light" else _TEAM_STATUS_DARK


def task_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _TASK_STATUS_LIGHT if THEME_NAME == "light" else _TASK_STATUS_DARK


def subscribe_theme(widget: QWidget, callback: Callable[[str], None]) -> None:
    """Subscribe to theme changes and auto-disconnect on widget destruction."""
    style_bus.THEME_CHANGED.connect(callback)
    try:
        widget.destroyed.connect(lambda: style_bus.THEME_CHANGED.disconnect(callback))
    except Exception:
        pass
    callback(THEME_NAME)


__all__ = [
    "THEME_NAME",
    "StyleBus",
    "style_bus",
    "get_palette",
    "apply_app_palette",
    "set_theme",
    "subscribe_theme",
    "team_status_colors",
    "task_status_colors",
    "TEAM_TYPE_COLORS",
]
