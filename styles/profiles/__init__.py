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


__all__ = ["DEFAULT_PROFILE", "available_profiles", "get_profile_name", "load_profile"]
