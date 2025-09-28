"""Communications Traffic Log module."""

from __future__ import annotations

from typing import Optional

from .services import CommsLogService

__all__ = [
    "create_log_window",
    "create_log_board_window",
    "create_quick_entry_window",
    "CommsLogService",
    "get_log_window_class",
]


def create_log_window(parent=None, *, incident_id: Optional[str] = None):
    """Factory for the communications traffic log window."""
    from .ui.log_window import CommunicationsLogWindow

    service = CommsLogService(incident_id=incident_id)
    window = CommunicationsLogWindow(service, parent=parent)
    return window


def get_log_window_class():
    from .ui.log_window import CommunicationsLogWindow

    return CommunicationsLogWindow


def create_log_board_window(parent=None, *, incident_id: Optional[str] = None):
    # Return a dock-friendly QWidget panel
    from .ui.log_board_window import CommunicationsLogBoardPanel

    service = CommsLogService(incident_id=incident_id)
    return CommunicationsLogBoardPanel(service, parent=parent)


def create_quick_entry_window(parent=None, *, incident_id: Optional[str] = None):
    # Return a dock-friendly QWidget panel
    from .ui.quick_entry_window import QuickEntryPanel

    service = CommsLogService(incident_id=incident_id)
    return QuickEntryPanel(service, parent=parent)
