"""QtWidgets panel loader for the ICS-214 Activity Log."""
from __future__ import annotations

from typing import Any

from ..widgets import Ics214ActivityLogPanel


def load_panel(engine: Any | None = None) -> Ics214ActivityLogPanel:
    """Return a new QtWidgets-based ICS-214 panel instance.

    The legacy implementation loaded a QML document into the provided
    ``QQmlApplicationEngine``. The redesigned module is widget-native, so the
    ``engine`` parameter is kept for backward compatibility but ignored.
    """

    _ = engine  # unused
    return Ics214ActivityLogPanel()
