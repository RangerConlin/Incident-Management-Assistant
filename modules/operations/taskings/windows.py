from __future__ import annotations

import os
from typing import Optional

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlContext

from .bridge import TaskingsBridge


_open_engines: list[QQmlApplicationEngine] = []


def open_task_detail_window(task_id: Optional[int] = None):
    """Open the floating, modeless QML Task Detail Window.

    Uses QQmlApplicationEngine so the QML ApplicationWindow manages its own toplevel.
    Keeps a strong ref to the engine to prevent premature GC.
    """
    qml_path = os.path.abspath(os.path.join(
        "modules", "operations", "taskings", "qml", "TaskDetailWindow.qml"
    ))
    engine = QQmlApplicationEngine()
    bridge: TaskingsBridge | None = None
    try:
        ctx: QQmlContext = engine.rootContext()
        bridge = TaskingsBridge()
        ctx.setContextProperty("taskingsBridge", bridge)
    except Exception:
        bridge = None
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
        # Best-effort: directly hydrate data to avoid timing issues when bridge loads later
        try:
            if bridge and task_id is not None:
                # Preload lookups and task detail
                lookups = bridge.getLookups()
                detail = bridge.getTaskDetail(int(task_id))
                teams = bridge.listTeams(int(task_id))
                if lookups:
                    root.setProperty("lookups", lookups)
                if detail:
                    root.setProperty("taskDetail", detail)
                if teams and isinstance(teams, dict) and "teams" in teams:
                    root.setProperty("taskTeams", teams.get("teams", []))
        except Exception:
            # Non-fatal hydration issues; QML will still try via dataApi
            pass
    _open_engines.append(engine)
    return engine
