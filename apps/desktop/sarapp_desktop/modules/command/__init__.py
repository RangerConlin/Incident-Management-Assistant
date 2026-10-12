from __future__ import annotations

"""Command module public API."""

__all__ = [
    "get_incident_dashboard_panel",
    "get_incident_overview_panel",
    "get_iap_builder_panel",
    "get_objectives_panel",
    "get_staff_org_panel",
    "get_sitrep_panel",
]


def __getattr__(name: str):
    if name in __all__:
        from . import windows

        return getattr(windows, name)
    raise AttributeError(name)
