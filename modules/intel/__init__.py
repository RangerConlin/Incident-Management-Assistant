"""Intel module providing incident intelligence management."""

from __future__ import annotations

from .panels.intel_dashboard import IntelDashboard


def register_intel_module(app) -> IntelDashboard:
    """Register the intel module with ``app`` and return the main dashboard.

    Parameters
    ----------
    app:
        QApplication instance. The function currently does not use ``app``
        directly but accepting it keeps the signature consistent with other
        modules in the project.
    """

    return IntelDashboard()


__all__ = ["register_intel_module", "IntelDashboard"]
