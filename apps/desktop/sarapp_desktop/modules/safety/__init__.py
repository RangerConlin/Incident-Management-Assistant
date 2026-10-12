from __future__ import annotations

try:
    from .windows import (
        get_208_panel,
        get_215A_panel,
        get_risk_manager_panel,
        get_safety_panel,
        get_iwi_panel,
    )
except Exception:  # pragma: no cover - fallback for headless/test envs
    get_208_panel = get_215A_panel = get_risk_manager_panel = get_safety_panel = get_iwi_panel = lambda *_, **__: None

__all__ = [
    "get_208_panel",
    "get_215A_panel",
    "get_risk_manager_panel",
    "get_safety_panel",
    "get_iwi_panel",
]
