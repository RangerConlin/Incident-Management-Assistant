"""
Public Information module (UI only) for SARApp.

Exports helper functions that lazily import PySide6-based widgets. Importing
this package has no Qt side effects. If PySide6 is unavailable, calling any
GUI function raises ImportError with a clear message.

Functions:
- get_public_info_panel(incident_id, current_user, parent=None) -> QWidget
  Dashboard widget with toolbar and Queue/History tabs.
- get_media_releases_panel(incident_id, current_user=None, parent=None) -> QWidget
  Same as dashboard for now.
- get_inquiries_panel(incident_id, current_user=None, parent=None) -> QWidget
  Placeholder widget with centered label.
- open_editor_window(incident_id, current_user, message_id=None) -> QWidget
  Opens a top-level editor window for creating/editing a message.
"""

from typing import Any, Dict, Optional


def _ensure_qt_available() -> None:
    try:
        import PySide6  # noqa: F401
    except Exception as exc:  # pragma: no cover - import guard
        raise ImportError(
            "PySide6 is required for Public Information UI components"
        ) from exc


def get_public_info_panel(
    incident_id: str, current_user: Dict[str, Any], parent: Optional[object] = None
):
    _ensure_qt_available()
    from .windows import get_public_info_panel as _get

    return _get(incident_id, current_user, parent=parent)


def get_media_releases_panel(
    incident_id: str, current_user: Optional[Dict[str, Any]] = None, parent: Optional[object] = None
):
    _ensure_qt_available()
    from .windows import get_media_releases_panel as _get

    return _get(incident_id, current_user, parent=parent)


def get_inquiries_panel(
    incident_id: str, current_user: Optional[Dict[str, Any]] = None, parent: Optional[object] = None
):
    _ensure_qt_available()
    from .windows import get_inquiries_panel as _get

    return _get(incident_id, current_user, parent=parent)


def open_editor_window(
    incident_id: str,
    current_user: Dict[str, Any],
    message_id: Optional[int] = None,
):
    _ensure_qt_available()
    from .windows import open_editor_window as _open

    return _open(incident_id, current_user, message_id)

__all__ = [
    "get_public_info_panel",
    "get_media_releases_panel",
    "get_inquiries_panel",
    "open_editor_window",
]
