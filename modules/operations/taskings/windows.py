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
    """Open the QML Task Detail window (legacy/alt path)."""
    try:
        import os
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlContext
        from .bridge import TaskingsBridge

        qml_path = os.path.abspath(os.path.join(
            "modules", "operations", "taskings", "qml", "TaskDetailWindow.qml"
        ))
        engine = QQmlApplicationEngine()
        ctx: QQmlContext = engine.rootContext()
        bridge = TaskingsBridge()
        ctx.setContextProperty("taskingsBridge", bridge)
        engine.load(QUrl.fromLocalFile(qml_path))
        roots = engine.rootObjects()
        if roots:
            root = roots[0]
            try:
                if task_id is not None:
                    root.setProperty("taskId", int(task_id))
            except Exception:
                pass
            try:
                root.setProperty("visible", True)
            except Exception:
                pass
        _open_engines.append(engine)
        return engine
    except Exception as e:
        print(f"Failed to open QML Task Detail Window: {e}")
        return None
