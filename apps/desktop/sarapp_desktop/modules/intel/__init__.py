"""Intel module — All-Hazards Information Collection, Analysis, and Dissemination."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

# Module-level singleton reference so the window is not garbage-collected
# and so repeated calls raise/activate the existing window.
_intel_window = None


def open_intel_window(
    incident_id: Optional[str] = None,
    tab: Optional[str] = None,
    parent: Optional[QWidget] = None,
) -> None:
    """Open (or raise) the Intel module window, optionally switching to a tab.

    Enforces a single-instance window per session.  If the window is already
    open, it is raised and brought to the foreground.  If *tab* is provided,
    the window switches to that tab regardless of whether it was just created
    or already existed.
    """
    global _intel_window

    from modules.intel.intel_window import IntelWindow

    try:
        alive = _intel_window is not None and _intel_window.isVisible()
    except RuntimeError:
        alive = False
        _intel_window = None

    if not alive:
        _intel_window = IntelWindow(incident_id=incident_id, parent=parent)
        _intel_window.show()
    elif _intel_window._incident_id != incident_id:
        # Incident changed while window was open — reload with new incident
        _intel_window.load_incident(incident_id)
        _intel_window.raise_()
        _intel_window.activateWindow()
    else:
        _intel_window.raise_()
        _intel_window.activateWindow()

    if tab:
        _intel_window.switch_to_tab(tab)


__all__ = ["open_intel_window"]
