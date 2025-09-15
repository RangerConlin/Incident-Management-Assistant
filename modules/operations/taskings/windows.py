from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import QWidget

from .task_detail_widget import TaskDetailWindow


_open_windows: list[QWidget] = []
_open_engines = []  # keep QML engines alive when using QML variant


def open_task_detail_window(task_id: Optional[int] = None) -> QWidget:
    """Open the QWidget-based Task Detail window (no QML)."""
    tid = int(task_id) if task_id is not None else -1
    w = TaskDetailWindow(tid)
    w.show()
    _open_windows.append(w)
    # Remove from list on close
    try:
        w.destroyed.connect(lambda _obj=None: _open_windows.remove(w))
    except Exception:
        pass
    return w


def open_task_detail_window_widget(task_id: Optional[int] = None) -> QWidget:
    """Explicit alias for QWidget variant."""
    return open_task_detail_window(task_id)


def open_task_detail_window_qml(task_id: Optional[int] = None):
    """Deprecated: QML Task Detail window has been removed."""
    print("QML Task Detail window is not available in this build.")
    return None
