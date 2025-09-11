"""ICS‑205 Communications module (Widgets only).

Provides a factory to create the standalone ICS‑205 window.
"""

from .panels.ics205_window import ICS205Window


def create_ics205_window(parent=None):
    return ICS205Window(parent)


__all__ = ["create_ics205_window", "ICS205Window"]

