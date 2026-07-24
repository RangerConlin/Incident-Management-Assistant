"""
Launcher helper for the Tactics and Resources Planner.

Call open_tactics_resources_planner() from any menu or button to open
the main planner window.  Keeps a single window instance alive so
repeated calls raise the existing window rather than opening a second one.

Menu integration
----------------
Add the following to main.py to wire up the menus:

    # In the menu setup block (alongside m_planning, m_ops, m_logistics):
    self._add_action(m_planning, "Tactics and Resources Planner", None, "planning.tactics_planner")
    self._add_action(m_ops,      "Tactics and Resources Planner", None, "planning.tactics_planner")
    self._add_action(m_logistics,"Tactics and Resources Planner", None, "planning.tactics_planner")

    # In the handlers dict inside open_module():
    "planning.tactics_planner": self.open_tactics_resources_planner,

    # As a method on the main window class:
    def open_tactics_resources_planner(self) -> None:
        from modules.planning.tactics_resources import open_tactics_resources_planner
        open_tactics_resources_planner()
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

# Module-level singleton reference so the window is not garbage-collected
_planner_window: Optional["_PlannerRef"] = None


class _PlannerRef:
    """Holds a strong reference to the planner window."""
    def __init__(self, win: QWidget) -> None:
        self.win = win


def open_tactics_resources_planner(
    parent: Optional[QWidget] = None,
    db_path: str | None = None,
) -> QWidget:
    """
    Open (or raise) the Tactics and Resources Planner window.

    Parameters
    ----------
    parent:
        Accepted for older call sites, but intentionally ignored. The main
        planner board opens parentless so it behaves as an independent window.
    db_path:
        Explicit path to the incident database.
        When None, resolves from incident_context at call time.

    Returns
    -------
    The TacticsResourcesPlannerWindow instance.
    """
    global _planner_window

    # Reuse existing window if still open
    if _planner_window is not None:
        win = _planner_window.win
        if win.isVisible():
            win.raise_()
            win.activateWindow()
            return win

    from modules.planning.tactics_resources.windows.tactics_resources_planner_window import (
        TacticsResourcesPlannerWindow,
    )
    win = TacticsResourcesPlannerWindow(db_path=db_path, parent=None)
    _planner_window = _PlannerRef(win)
    win.show()
    return win
