"""Check-In module for SARApp / ICS Command Assistant.

This package implements a minimal offline-first check-in workflow
supporting personnel and assets. The code is deliberately small but
heavily commented so it can serve as a starting point for future
expansion.
"""

# Re-export the QWidget wrapper for the QML Check-In window so callers can do:
#   from modules.logistics.checkin import CheckInPanel
from .panels.CheckInPanel import CheckInPanel

__all__ = ["CheckInPanel"]
