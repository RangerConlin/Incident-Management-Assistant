from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect

SOUNDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "sounds"))

CATEGORIES = ('operations', 'communications', 'safety', 'logistics', 'planning', 'administrative', 'system')
SEVERITIES = ('informational', 'routine', 'priority', 'emergency')

# Default sound file (basename) per category+severity. None = silent.
_DEFAULTS: dict[tuple[str, str], Optional[str]] = {
    ("operations",     "informational"): None,
    ("operations",     "routine"):       None,
    ("operations",     "priority"):      "notify_chime.wav",
    ("operations",     "emergency"):     "notify_chime.wav",
    ("communications", "informational"): None,
    ("communications", "routine"):       None,
    ("communications", "priority"):      "notify_chime.wav",
    ("communications", "emergency"):     "notify_chime.wav",
    ("safety",         "informational"): None,
    ("safety",         "routine"):       None,
    ("safety",         "priority"):      "notify_chime.wav",
    ("safety",         "emergency"):     "notify_chime.wav",
    ("logistics",      "informational"): None,
    ("logistics",      "routine"):       None,
    ("logistics",      "priority"):      "notify_chime.wav",
    ("logistics",      "emergency"):     "notify_chime.wav",
    ("planning",       "informational"): None,
    ("planning",       "routine"):       None,
    ("planning",       "priority"):      "notify_chime.wav",
    ("planning",       "emergency"):     "notify_chime.wav",
    ("administrative", "informational"): None,
    ("administrative", "routine"):       None,
    ("administrative", "priority"):      None,
    ("administrative", "emergency"):     "notify_chime.wav",
    ("system",         "informational"): None,
    ("system",         "routine"):       None,
    ("system",         "priority"):      None,
    ("system",         "emergency"):     "notify_chime.wav",
}


def list_available_sounds() -> list[str]:
    """Return sorted list of .wav filenames found in the sounds directory."""
    try:
        return sorted(f for f in os.listdir(SOUNDS_DIR) if f.lower().endswith(".wav"))
    except OSError:
        return []


def settings_key(category: str, severity: str) -> str:
    return f"sound.{category}.{severity}"


class SoundPlayer(QObject):
    """Play per-category/severity notification sounds."""

    _instance: "SoundPlayer | None" = None

    def __init__(self) -> None:
        super().__init__()
        self._files: dict[tuple[str, str], Optional[str]] = dict(_DEFAULTS)
        self._effects: dict[tuple[str, str], QSoundEffect] = {}
        self._volume: float = 1.0
        self._preview_effect: Optional[QSoundEffect] = None

    def set_sound(self, category: str, severity: str, filename: Optional[str]) -> None:
        key = (category, severity)
        self._files[key] = filename
        self._effects.pop(key, None)

    def set_volume(self, volume_pct: int) -> None:
        self._volume = max(0.0, min(1.0, volume_pct / 100.0))
        for effect in self._effects.values():
            try:
                effect.setVolume(self._volume)
            except Exception:
                pass

    def play(self, category: str, severity: str) -> None:
        key = (category, severity)
        filename = self._files.get(key)
        if not filename:
            return
        effect = self._effects.get(key)
        if effect is None:
            path = os.path.join(SOUNDS_DIR, filename)
            if not os.path.isfile(path):
                return
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(self._volume)
            self._effects[key] = effect
        try:
            effect.play()
        except Exception:
            pass

    def preview(self, filename: str) -> None:
        path = os.path.join(SOUNDS_DIR, filename)
        if not os.path.isfile(path):
            return
        try:
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(self._volume)
            effect.play()
            self._preview_effect = effect
        except Exception:
            pass

    @classmethod
    def instance(cls) -> "SoundPlayer":
        if cls._instance is None:
            cls._instance = SoundPlayer()
        return cls._instance
