"""PNG briefing export — grabs the rendered widget as a pixmap and saves it."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def save_widget_as_png(widget: QWidget, path: str) -> bool:
    pixmap = widget.grab()
    return pixmap.save(path, "PNG")


__all__ = ["save_widget_as_png"]
