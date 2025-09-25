"""Panel factories for the communications module."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget

from ..traffic_log import create_log_window
from .ics205_window import ICS205Window
from .canned_comm_entries_window import CannedCommEntriesWindow

__all__ = ["MessageLogPanel", "ICS205Window", "CannedCommEntriesWindow"]

logger = logging.getLogger(__name__)


def MessageLogPanel(parent=None, *, incident_id: Optional[str] = None):
    """Return the communications traffic log panel.

    Falls back to a placeholder widget if no incident database is available.
    """

    try:
        return create_log_window(parent=parent, incident_id=incident_id)
    except RuntimeError as exc:
        logger.warning("Communications log unavailable: %s", exc)
        if parent is not None:
            try:
                QMessageBox.warning(
                    parent,
                    "Communications Log",
                    "Select or create an incident to use the communications log.",
                )
            except Exception:
                # QMessageBox may be unavailable in headless contexts
                logger.debug("Unable to display QMessageBox for comms log warning.")
        placeholder = QWidget(parent)
        placeholder.setObjectName("communicationsLogUnavailable")
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        label = QLabel(
            "Select or create an incident to use the communications log."
        )
        label.setWordWrap(True)
        layout.addWidget(label, alignment=Qt.AlignCenter)
        placeholder.setEnabled(False)
        return placeholder
