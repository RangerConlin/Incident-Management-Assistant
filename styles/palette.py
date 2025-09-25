"""Semantic colour palette aliases backed by the profile repository."""

from __future__ import annotations

from styles.profiles import load_profile


_LIGHT_PROFILE = load_profile("light")
_DARK_PROFILE = load_profile("dark")


LIGHT = dict(getattr(_LIGHT_PROFILE, "SURFACE", {}))
DARK = dict(getattr(_DARK_PROFILE, "SURFACE", {}))

TEAM_STATUS = dict(getattr(_LIGHT_PROFILE, "TEAM_STATUS_REFERENCE", {}))
TASK_STATUS = dict(getattr(_LIGHT_PROFILE, "TASK_STATUS_REFERENCE", {}))

THEMES = {"light": LIGHT, "dark": DARK}

