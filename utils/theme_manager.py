from __future__ import annotations
from typing import Dict
from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

from styles.palette import THEMES


class ThemeManager(QObject):
    themeChanged = Signal(str)  # emits current theme name ("light"/"dark")

    def __init__(self, app: QApplication, initial_theme: str = "light"):
        super().__init__()
        self._app = app
        self._theme = initial_theme if initial_theme in THEMES else "light"
        self.apply_palette()

    # Expose as Qt Property if needed
    def getTheme(self) -> str:
        return self._theme

    @Slot(str)
    def setTheme(self, name: str):
        name = (name or "").lower()
        if name not in THEMES or name == self._theme:
            return
        self._theme = name
        self.apply_palette()
        self.themeChanged.emit(self._theme)

    theme = Property(str, fget=getTheme, fset=setTheme, notify=themeChanged)

    def tokens(self) -> Dict[str, str]:
        return THEMES[self._theme]

    def apply_palette(self):
        """Apply base QWidget palette; QML reads tokens via ThemeBridge."""
        tokens = self.tokens()
        pal = QPalette()
        # Windows
        pal.setColor(QPalette.Window, QColor(tokens["bg_window"]))
        pal.setColor(QPalette.WindowText, QColor(tokens["fg_primary"]))
        # Base text/controls
        pal.setColor(QPalette.Base, QColor(tokens["ctrl_bg"]))
        pal.setColor(QPalette.Text, QColor(tokens["fg_primary"]))
        # Buttons
        pal.setColor(QPalette.Button, QColor(tokens["ctrl_bg"]))
        pal.setColor(QPalette.ButtonText, QColor(tokens["fg_primary"]))
        # Accents (use as Highlight)
        pal.setColor(QPalette.Highlight, QColor(tokens["accent"]))
        pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))

        self._app.setPalette(pal)

