"""Utility widgets for the logistics module."""

from __future__ import annotations

try:  # pragma: no cover - UI elements are not tested
    from PySide6.QtWidgets import QToolBar, QAction
except Exception:  # pragma: no cover
    QToolBar = QAction = object  # type: ignore


def build_toolbar(spec: list[tuple[str, callable]]) -> QToolBar:  # type: ignore[misc]
    """Create a simple toolbar from ``(label, callback)`` tuples."""

    bar = QToolBar()
    for label, cb in spec:
        act = QAction(label, bar)
        act.triggered.connect(cb)  # type: ignore[attr-defined]
        bar.addAction(act)
    return bar
