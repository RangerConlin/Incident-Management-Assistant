"""Bootstrap helper to display the incident selection window."""

from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtWidgets import QApplication

from ui.windows.incident_selection_window import IncidentSelectionWindow


def show_incident_selector(on_select: Optional[Callable[[str], None]] = None) -> None:
    """Display the :class:`IncidentSelectionWindow` as a standalone dialog."""
    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication(sys.argv)
        owns_app = True

    win = IncidentSelectionWindow()
    if on_select:
        win.incidentLoaded.connect(on_select)

    if owns_app:
        win.show()
        app.exec()
    else:
        win.exec()


if __name__ == "__main__":
    show_incident_selector()
