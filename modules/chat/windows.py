"""Factory for the incident chat window, mirroring `modules/ics214/windows.py`."""

from __future__ import annotations


def get_chat_window(incident_id=None):
    from .widgets.chat_window import ChatWindow

    return ChatWindow(incident_id=incident_id)
