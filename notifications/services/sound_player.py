from __future__ import annotations

import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect


class SoundPlayer(QObject):
    """Play notification sounds respecting user preferences."""

    _instance: "SoundPlayer | None" = None

    def __init__(self) -> None:
        super().__init__()
        self._effect = QSoundEffect()
        try:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "sounds", "notify_chime.wav"))
            self._effect.setSource(QUrl.fromLocalFile(base))
        except Exception:
            pass

    def play(self) -> None:
        try:
            self._effect.play()
        except Exception:
            pass

    @classmethod
    def instance(cls) -> "SoundPlayer":
        if cls._instance is None:
            cls._instance = SoundPlayer()
        return cls._instance
