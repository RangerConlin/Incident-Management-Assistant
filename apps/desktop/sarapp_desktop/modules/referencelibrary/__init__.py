"""Reference Library module."""

from .api.public_api import (
    add_reference,
    search_references,
    get_reference_by_id,
    link_reference_to_collection,
    list_collections,
)
from .ui.library_window import LibraryWindow
from .helpdocs import get_user_guide_panel, get_about_panel


def get_library_panel(incident_id: object | None = None):
    """Return a widget for browsing the Reference Library."""
    return LibraryWindow()


def get_form_library_panel(incident_id: object | None = None):
    """Return a widget for browsing form templates."""
    return LibraryWindow()


__all__ = [
    "add_reference",
    "search_references",
    "get_reference_by_id",
    "link_reference_to_collection",
    "list_collections",
    "get_library_panel",
    "get_form_library_panel",
    "get_user_guide_panel",
    "get_about_panel",
]
