"""Reference Library module package."""

from .api import router
from .panels.ReferenceLibraryPanel import ReferenceLibraryPanel


def get_library_panel() -> ReferenceLibraryPanel:
    """Return the main reference library panel instance."""
    return ReferenceLibraryPanel()

__all__ = ["router", "get_library_panel"]
