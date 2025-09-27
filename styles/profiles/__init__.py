"""Color profile registry for the style system."""
from __future__ import annotations

import importlib
import os
from functools import lru_cache
from types import ModuleType
from typing import Dict

DEFAULT_PROFILE = "light"

_PROFILE_REGISTRY: Dict[str, str] = {
    "light": "styles.profiles.light",
    "dark": "styles.profiles.dark",
}


def get_profile_name() -> str:
    """Return the active color profile name.

    The profile can be overridden by setting the ``IMA_COLOR_PROFILE``
    environment variable. When not provided, the light profile is used.
    """

    return os.getenv("IMA_COLOR_PROFILE", DEFAULT_PROFILE).lower()


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
