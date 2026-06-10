"""Settings helpers for the weather module."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QSettings

LOGGER = logging.getLogger(__name__)


_SETTINGS_SCOPE = "modules/intel/weather"
_SETTINGS_FILE = Path("settings/weather_module.ini")


class WeatherSettings:
    """Wrapper around :class:`QSettings` with convenience helpers."""

    def __init__(self) -> None:
        self._settings = QSettings(str(_SETTINGS_FILE), QSettings.IniFormat)
        self._settings.beginGroup(_SETTINGS_SCOPE)

    def value(self, key: str, default: Any = None) -> Any:
        return self._settings.value(key, default)

    def set_value(self, key: str, value: Any) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    def begin_group(self, name: str) -> None:
        self._settings.beginGroup(name)

    def end_group(self) -> None:
        self._settings.endGroup()


_settings_singleton: Optional[WeatherSettings] = None


def weather_settings() -> WeatherSettings:
    """Return a module-level settings instance."""

    global _settings_singleton
    if _settings_singleton is None:
        _settings_singleton = WeatherSettings()
    return _settings_singleton


def load_api_config(config_path: Path) -> Dict[str, Any]:
    """Load API configuration from disk."""

    if not config_path.exists():
        LOGGER.warning("API config not found at %s", config_path)
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.error("Failed to parse API config: %s", exc)
        return {}


__all__ = ["weather_settings", "load_api_config", "WeatherSettings"]
