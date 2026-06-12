from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def _load_placeholder_panel(widget: QWidget, panel_name: str) -> QWidget:
    """Compatibility helper for old panel classes after panel-asset removal."""

    layout = widget.layout()
    if layout is None:
        layout = QVBoxLayout(widget)

    title = QLabel(Path(panel_name).stem)
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(QLabel(f"Legacy panel '{panel_name}' has been removed."))
    return widget
