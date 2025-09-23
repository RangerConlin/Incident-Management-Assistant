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
        self._builtin_themes: Dict[str, Dict[str, str]] = dict(THEMES)
        self._custom_tokens: Dict[str, Dict[str, str]] = {}
        self._theme = initial_theme if initial_theme in self._builtin_themes else "light"
        self.apply_palette()

    # Expose as Qt Property if needed
    def getTheme(self) -> str:
        return self._theme

    @Slot(str)
    def setTheme(self, name: str):
        name = (name or "").lower()
        if name.startswith("custom:"):
            key = name.split("custom:", 1)[1]
            if key in self._custom_tokens and self._theme != f"custom:{key}":
                self._theme = f"custom:{key}"
                self.apply_palette()
                self.themeChanged.emit(self._theme)
            return
        if name not in self._builtin_themes or name == self._theme:
            return
        self._theme = name
        self.apply_palette()
        self.themeChanged.emit(self._theme)

    theme = Property(str, fget=getTheme, fset=setTheme, notify=themeChanged)

    def tokens(self) -> Dict[str, str]:
        if self._theme.startswith("custom:" ):
            key = self._theme.split("custom:", 1)[1]
            return self._custom_tokens.get(key, self._builtin_themes.get("light", {}))
        return self._builtin_themes.get(self._theme, self._builtin_themes.get("light", {}))

    def apply_palette(self):
        """Apply base QWidget palette; QML reads tokens via ThemeBridge."""
        tokens = self.tokens()
        pal = QPalette()
        # Windows
        pal.setColor(QPalette.Window, QColor(tokens.get("bg_window", "#FFFFFF")))
        pal.setColor(QPalette.WindowText, QColor(tokens.get("fg_primary", "#000000")))
        # Base text/controls
        pal.setColor(QPalette.Base, QColor(tokens.get("ctrl_bg", "#FFFFFF")))
        pal.setColor(QPalette.Text, QColor(tokens.get("fg_primary", "#000000")))
        # Buttons
        pal.setColor(QPalette.Button, QColor(tokens.get("ctrl_bg", "#FFFFFF")))
        pal.setColor(QPalette.ButtonText, QColor(tokens.get("fg_primary", "#000000")))
        # Accents (use as Highlight)
        pal.setColor(QPalette.Highlight, QColor(tokens.get("accent", "#2F80ED")))
        pal.setColor(QPalette.HighlightedText, QColor(tokens.get("highlighted_text", "#FFFFFF")))

        if self._app is not None:
            self._app.setPalette(pal)

    # Custom theme helpers -------------------------------------------------
    def register_custom_theme(self, theme_id: str, tokens: Dict[str, str], *, base_theme: str | None = None) -> None:
        theme_id = (theme_id or "").strip().lower()
        if not theme_id:
            return
        base_tokens = dict(self._builtin_themes.get(base_theme or "light", self._builtin_themes.get("light", {})))
        base_tokens.update(tokens)
        self._custom_tokens[theme_id] = base_tokens

    def apply_custom_theme(self, theme_id: str) -> None:
        theme_id = (theme_id or "").strip().lower()
        if theme_id not in self._custom_tokens:
            return
        name = f"custom:{theme_id}"
        if self._theme == name:
            self.apply_palette()
            self.themeChanged.emit(self._theme)
            return
        self._theme = name
        self.apply_palette()
        self.themeChanged.emit(self._theme)

    def remove_custom_theme(self, theme_id: str) -> None:
        theme_id = (theme_id or "").strip().lower()
        self._custom_tokens.pop(theme_id, None)

