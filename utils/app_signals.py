from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """Global Qt signals for app-wide events.

    Panels can subscribe to these to stay in sync with application state.
    """

    incidentChanged = Signal(str)  # emits the incident number (string)
    userChanged = Signal(object, object)  # user_id, role
    opPeriodChanged = Signal(object)  # op period id
    # Emitted when a communications message is logged; provide sender and recipient labels
    messageLogged = Signal(str, str)
    # Emitted when a team status is changed elsewhere in the app; provide team_id
    teamStatusChanged = Signal(int)
    # Emitted when team asset assignments change (personnel, vehicles, equipment, aircraft)
    teamAssetsChanged = Signal(int)
    # Emitted when a team's leader changes
    teamLeaderChanged = Signal(int)


# Global singleton instance
app_signals = AppSignals()


__all__ = ["app_signals", "AppSignals"]
