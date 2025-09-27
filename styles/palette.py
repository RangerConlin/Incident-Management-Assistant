"""Semantic colour palette aliases backed by the profile repository."""

from __future__ import annotations

from styles.profiles import load_profile, profile_tokens


_LIGHT_PROFILE = load_profile("light")
_DARK_PROFILE = load_profile("dark")


LIGHT = profile_tokens("light")
DARK = profile_tokens("dark")

TEAM_STATUS = dict(getattr(_LIGHT_PROFILE, "TEAM_STATUS_REFERENCE", {}))
TASK_STATUS = dict(getattr(_LIGHT_PROFILE, "TASK_STATUS_REFERENCE", {}))

THEMES = {"light": LIGHT, "dark": DARK}

