"""Reusable Resource Type Library foundation module.

Qt widgets/windows are imported lazily so repository-only code can run in
headless or dependency-limited environments without loading PySide6.
"""


__all__ = [
    "ResourceTypeSearchBox",
    "CapabilityManagerWindow",
    "ResourceTypeEditorWindow",
    "ResourceTypeLibraryWindow",
    "open_resource_type_library",
]


def __getattr__(name: str):
    if name == "ResourceTypeSearchBox":
        from .widgets import ResourceTypeSearchBox

        return ResourceTypeSearchBox
    if name in {
        "CapabilityManagerWindow",
        "ResourceTypeEditorWindow",
        "ResourceTypeLibraryWindow",
        "open_resource_type_library",
    }:
        from . import windows

        return getattr(windows, name)
    raise AttributeError(name)
