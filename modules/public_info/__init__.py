"""Public information module exports.

Similar to :mod:`modules.logistics`, this package used to eagerly import Qt
widgets on module import which breaks in environments without an available X
server or OpenGL stack.  The tests only need access to the underlying data
models and repositories, so we guard the optional GUI imports and provide
explicit stubs when the GUI layer cannot be loaded.
"""

try:  # pragma: no cover - only executed when Qt is installed
    from .windows import (
        get_media_releases_panel,
        get_inquiries_panel,
        get_public_info_panel,
    )
except Exception:  # pragma: no cover - no Qt available
    def _missing(*_: object, **__: object) -> None:
        raise ImportError("Qt GUI components are not available in this build")

    get_media_releases_panel = _missing
    get_inquiries_panel = _missing
    get_public_info_panel = _missing

__all__ = [
    "get_media_releases_panel",
    "get_inquiries_panel",
    "get_public_info_panel",
]
