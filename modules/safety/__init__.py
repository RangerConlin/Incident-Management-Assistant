from __future__ import annotations

try:
    from .windows import (
        get_208_panel,
        get_215A_panel,
        get_caporm_panel,
        get_safety_panel,
        get_weather_panel,
    )
except Exception:  # pragma: no cover - fallback for headless/test envs
    get_208_panel = get_215A_panel = get_caporm_panel = get_safety_panel = get_weather_panel = lambda *_, **__: None

__all__ = [
    "get_208_panel",
    "get_215A_panel",
    "get_caporm_panel",
    "get_safety_panel",
    "get_weather_panel",
]
