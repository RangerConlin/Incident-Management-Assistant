from __future__ import annotations

from typing import Optional

from .panels.team_detail_window import TeamDetailWindow


_open_windows: list[TeamDetailWindow] = []


def open_team_detail_window(team_id: Optional[int] = None) -> TeamDetailWindow:
    """Open the Team Detail window using the widget-based implementation."""

    window = TeamDetailWindow(team_id=team_id)
    window.show()
    _open_windows.append(window)

    def _cleanup() -> None:
        try:
            _open_windows.remove(window)
        except ValueError:
            pass

    window.destroyed.connect(lambda *_: _cleanup())
    return window
