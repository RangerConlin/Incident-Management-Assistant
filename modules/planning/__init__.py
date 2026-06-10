"""Planning module public factories.

UI factories are loaded lazily so non-UI planning services can be imported in
test and API contexts without requiring PySide6 at package import time.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "get_dashboard_panel",
    "get_approvals_panel",
    "get_forecast_panel",
    "get_meetings_panel",
    "get_op_manager_panel",
    "get_taskmetrics_panel",
    "get_strategic_objectives_panel",
    "get_sitrep_panel",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import windows

        return getattr(windows, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
