from __future__ import annotations

import os
import logging
from typing import Optional

from PySide6.QtWidgets import QWidget

from .task_detail_widget import TaskDetailWindow
from utils.perf import PerfTimer


_open_windows: list[QWidget] = []
logger = logging.getLogger(__name__)


def open_task_detail_window(task_id: Optional[int] = None) -> QWidget:
    """Open the QWidget-based Task Detail window (no QML)."""
    tid = int(task_id) if task_id is not None else -1
    timer = PerfTimer(logger, f"Task Detail Window task_id={tid}")
    w = TaskDetailWindow(tid)
    timer.checkpoint("constructed")
    w.setMinimumSize(500, 400)
    w.resize(900, 800)
    w.show()
    timer.finish("shown")
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
