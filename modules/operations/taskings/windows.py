from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import QWidget

from .task_detail_widget import TaskDetailWindow


_open_windows: list[QWidget] = []
def open_task_detail_window(task_id: Optional[int] = None) -> QWidget:
    """Open the QWidget-based Task Detail window (no QML)."""
    tid = int(task_id) if task_id is not None else -1
    w = TaskDetailWindow(tid)
    w.resize(700, 800)
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
