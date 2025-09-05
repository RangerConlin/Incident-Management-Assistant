from __future__ import annotations

import os
from typing import Optional

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl

from .panels.team_detail_window import TeamDetailBridge


_open_engines: list[QQmlApplicationEngine] = []


def open_team_detail_window(team_id: Optional[int] = None):
    """Open the Team Detail window.

    Loads modules/operations/teams/qml/TeamDetailWindow.qml, injects a
    TeamDetailBridge as `teamBridge`, and passes the optional teamId.
    """
    qml_path = os.path.abspath(os.path.join(
        "modules", "operations", "teams", "qml", "TeamDetailWindow.qml"
    ))
    engine = QQmlApplicationEngine()
    # Inject bridge first so QML can call it on startup
    bridge = TeamDetailBridge()
    engine.rootContext().setContextProperty("teamBridge", bridge)
    engine.load(QUrl.fromLocalFile(qml_path))
    # If a team id was provided, load it immediately so the bridge
    # has data even if QML hasn't yet reacted to the property change.
    if team_id is not None:
        try:
            bridge.loadTeam(int(team_id))
        except Exception:
            pass
    roots = engine.rootObjects()
    if roots:
        root = roots[0]
        try:
            if team_id is not None:
                root.setProperty("teamId", int(team_id))
        except Exception:
            pass
        try:
            root.setProperty("visible", True)
        except Exception:
            pass
    _open_engines.append(engine)
    return engine
