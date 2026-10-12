"""Public Information module entry points."""
from __future__ import annotations

from typing import Any, Optional

from modules.public_information.services import PublicInformationRepository

_pio_window = None
_release_manager_window = None


def open_pio_window(
    incident_id: Optional[str] = None,
    current_user: Optional[dict[str, Any]] = None,
    tab: Optional[str] = None,
    parent=None,
) -> None:
    """Open (or raise) the standalone PIO dashboard, or a specific section window.

    If *tab* is given, opens only that section's window directly — the dashboard
    is not opened or raised.
    """
    global _pio_window
    from modules.public_information.pio_window import PublicInformationWindow

    if tab:
        # Open the section window directly, no dashboard involved.
        # Ensure a window instance exists to host section windows.
        try:
            alive = _pio_window is not None
        except RuntimeError:
            alive = False
            _pio_window = None
        if not alive:
            _pio_window = PublicInformationWindow(incident_id, current_user, parent)
            # Don't show the dashboard — just use it as the owner for section windows.
        _pio_window.switch_to_section(tab)
        return

    try:
        alive = _pio_window is not None and _pio_window.isVisible()
    except RuntimeError:
        alive = False
        _pio_window = None

    if not alive:
        _pio_window = PublicInformationWindow(incident_id, current_user, parent)
        _pio_window.show()
    elif getattr(_pio_window, "_incident_id", None) != incident_id:
        _pio_window.load_incident(incident_id or "")
        _pio_window.raise_()
        _pio_window.activateWindow()
    else:
        _pio_window.raise_()
        _pio_window.activateWindow()


def open_release_manager(
    incident_id: Optional[str] = None,
    current_user: Optional[dict[str, Any]] = None,
    status_filter: Optional[str] = None,
    parent=None,
) -> None:
    global _release_manager_window
    from modules.public_information.panels.release_manager import ReleaseManagerWindow

    try:
        alive = _release_manager_window is not None and _release_manager_window.isVisible()
    except RuntimeError:
        alive = False
        _release_manager_window = None

    if not alive or getattr(_release_manager_window, "repo", None) is None or getattr(_release_manager_window.repo, "incident_id", None) != str(incident_id or "unassigned"):
        _release_manager_window = ReleaseManagerWindow(
            PublicInformationRepository(incident_id),
            current_user,
            parent,
        )
        _release_manager_window.show()

    if _release_manager_window is not None:
        if status_filter:
            _release_manager_window.set_status_filter(status_filter)
        _release_manager_window.refresh()
        _release_manager_window.raise_()
        _release_manager_window.activateWindow()


def open_release_editor(
    incident_id: Optional[str] = None,
    current_user: Optional[dict[str, Any]] = None,
    message: Optional[dict[str, Any]] = None,
    defaults: Optional[dict[str, Any]] = None,
    parent=None,
) -> None:
    from modules.public_information.dialogs.release_editor_dialog import ReleaseEditorDialog

    repo = PublicInformationRepository(incident_id)
    payload = dict(message or defaults or {})
    dialog = ReleaseEditorDialog(repo, current_user, payload or None, parent)
    dialog.exec()


# ── legacy panel helpers (still used by main.py sub-menu items) ───────────────

def get_public_information_panel(
    incident_id: str | None = None,
    current_user: dict[str, Any] | None = None,
    parent=None,
):
    from modules.public_information.panels import PublicInformationDashboardPanel

    return PublicInformationDashboardPanel(incident_id, current_user, parent)


def get_public_info_panel(
    incident_id: str | None = None,
    current_user: dict[str, Any] | None = None,
    parent=None,
):
    return get_public_information_panel(incident_id, current_user, parent)


def get_media_releases_panel(incident_id: str | None = None, parent=None):
    from modules.public_information.panels.release_manager import ReleaseManagerPanel

    return ReleaseManagerPanel(PublicInformationRepository(incident_id), {}, parent)


def get_inquiries_panel(incident_id: str | None = None, parent=None):
    from modules.public_information.panels.simple_panels import MediaLogPanel

    return MediaLogPanel(PublicInformationRepository(incident_id), {}, parent)


__all__ = [
    "PublicInformationRepository",
    "open_pio_window",
    "get_public_information_panel",
    "get_public_info_panel",
    "get_media_releases_panel",
    "get_inquiries_panel",
    "open_release_manager",
    "open_release_editor",
]
