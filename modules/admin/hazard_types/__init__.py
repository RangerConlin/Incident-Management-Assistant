"""Reusable Hazard Type Library foundation module.

Qt widgets/windows are imported lazily so repository-only code can run in
headless or dependency-limited environments without loading PySide6.
"""

from .data import HazardTypeRepository

__all__ = [
    "HazardTypeSearchBox",
    "HazardTypeEditorWindow",
    "HazardTypeLibraryWindow",
    "open_hazard_type_library",
]


def __getattr__(name: str):
    if name == "HazardTypeSearchBox":
        from .widgets import HazardTypeSearchBox

        return HazardTypeSearchBox
    if name in {
        "HazardTypeEditorWindow",
        "HazardTypeLibraryWindow",
        "open_hazard_type_library",
    }:
        from . import windows

        return getattr(windows, name)
    raise AttributeError(name)
