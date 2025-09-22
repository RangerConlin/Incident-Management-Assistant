"""Public interface helpers for the Logistics Check-In package."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

__all__ = ["CheckInPanel"]


def __getattr__(name: str) -> Any:
    if name == "CheckInPanel":  # pragma: no cover - requires Qt stack
        try:
            from .panels.CheckInPanel import CheckInPanel as _CheckInPanel
        except Exception as exc:  # noqa: BLE001 - propagate root Qt failure
            raise ImportError(
                "Qt Check-In panel is not available in this build"
            ) from exc
        globals()[name] = _CheckInPanel
        return _CheckInPanel
    raise AttributeError(name)


if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from .panels.CheckInPanel import CheckInPanel as CheckInPanel

