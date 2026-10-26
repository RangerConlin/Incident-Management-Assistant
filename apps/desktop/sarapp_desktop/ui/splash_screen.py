"""Themed splash screen shown while the app loads, before the main window appears."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

_LOGO_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "branding" / "arc_horizon_mark.png"
)

_WIDTH = 480
_HEIGHT = 300


def _build_pixmap(tokens: Mapping[str, str]) -> QPixmap:
    pixmap = QPixmap(_WIDTH, _HEIGHT)
    pixmap.fill(QColor(tokens["bg_panel"]))

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)

        if _LOGO_PATH.exists():
            logo = QPixmap(str(_LOGO_PATH)).scaledToHeight(120, Qt.SmoothTransformation)
            painter.drawPixmap((pixmap.width() - logo.width()) // 2, 32, logo)

        painter.setPen(QColor(tokens["fg_primary"]))
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            pixmap.rect().adjusted(0, 168, 0, -64),
            Qt.AlignHCenter | Qt.AlignTop,
            "Incident Management Assistant",
        )
    finally:
        painter.end()

    return pixmap


class SplashScreen(QSplashScreen):
    """Frameless splash shown from app launch until the main window is ready.

    Call `set_status()` as startup moves through its phases (connecting,
    signing in, loading incident data, building the workspace) so the window
    gives feedback instead of sitting there blank.
    """

    def __init__(self, tokens: Mapping[str, str]):
        super().__init__(_build_pixmap(tokens))
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self._status_color = QColor(tokens["fg_muted"])
        self.set_status("Starting...")

    def set_status(self, text: str) -> None:
        self.showMessage(text, Qt.AlignHCenter | Qt.AlignBottom, self._status_color)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
