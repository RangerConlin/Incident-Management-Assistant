"""Color profile registry for the style system."""
from __future__ import annotations

import importlib
import os
import sys
from functools import lru_cache
from types import ModuleType
from typing import Dict

DEFAULT_PROFILE = "light"


def _is_system_dark_mode() -> bool:
    """Return True if the OS is configured to use a dark color scheme."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception:
        return False

_PROFILE_REGISTRY: Dict[str, str] = {
    "light": "styles.profiles.light",
    "dark": "styles.profiles.dark",
}


def get_profile_name() -> str:
    """Return the active color profile name.

    Checks ``IMA_COLOR_PROFILE`` env var first, then falls back to OS dark
    mode detection. Returns "light" or "dark".
    """
    env = os.getenv("IMA_COLOR_PROFILE", "").lower()
    if env in ("light", "dark"):
        return env
    return "dark" if _is_system_dark_mode() else "light"


@lru_cache(maxsize=None)
def load_profile(name: str | None = None) -> ModuleType:
    """Import and return the module that defines the requested profile."""

    profile_name = (name or get_profile_name()).lower()
    module_path = _PROFILE_REGISTRY.get(profile_name, profile_name)
    return importlib.import_module(module_path)


def available_profiles() -> tuple[str, ...]:
    """Return the names of built-in color profiles."""

    return tuple(sorted(_PROFILE_REGISTRY))


def _collect_tokens(profile_module: ModuleType) -> Dict[str, str]:
    """Return a merged palette for the provided profile module."""

    tokens: Dict[str, str] = {}
    for attribute in ("PALETTE", "SURFACE"):
        section = getattr(profile_module, attribute, {})
        tokens.update(dict(section))
    return tokens


def profile_tokens(name: str | None = None) -> Dict[str, str]:
    """Return merged palette tokens for the requested profile."""

    profile_module = load_profile(name)
    return _collect_tokens(profile_module)


def builtin_theme_tokens() -> Dict[str, Dict[str, str]]:
    """Return merged palette tokens for each registered profile."""

    tokens: Dict[str, Dict[str, str]] = {}
    for profile_name in available_profiles():
        profile_module = load_profile(profile_name)
        tokens[profile_name] = _collect_tokens(profile_module)
    return tokens


__all__ = [
    "DEFAULT_PROFILE",
    "available_profiles",
    "profile_tokens",
    "builtin_theme_tokens",
    "get_profile_name",
    "load_profile",
]
