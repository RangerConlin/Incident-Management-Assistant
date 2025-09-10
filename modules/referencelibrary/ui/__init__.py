"""Qt widget based UI for the reference library module.

This package replaces previous QML frontend usage with standard
PySide6 widgets.
"""

from .library_window import LibraryWindow
from .dialogs import AddEditDialog

__all__ = ["LibraryWindow", "AddEditDialog"]
