"""Light‑weight public interface for the logistics module.

The original package initialiser eagerly imported Qt based window factories
which in turn required an OpenGL capable environment.  The automated test
environment used for this kata does not provide the system libraries required
by PySide6 which meant merely importing :mod:`modules.logistics` would raise an
``ImportError`` long before any tests ran.

To make the services usable in a headless context we attempt to import the
window helpers lazily.  When the Qt libraries are unavailable the import will
fail and we provide stub callables that raise a helpful error should they be
used.  This mirrors the behaviour of the real application while keeping the
tests independent from the GUI stack.
"""

try:  # pragma: no cover - executed only when Qt is available
    from .windows import (
        get_logistics_panel,
        get_checkin_panel,
        get_equipment_panel,
        get_213rr_panel,
        get_personnel_panel,
        get_vehicles_panel,
    )
except Exception as exc:  # pragma: no cover - Qt not available
    def _missing(*_: object, **__: object) -> None:
        raise ImportError(
            "Qt GUI components are not available in this build"
        ) from exc

    get_logistics_panel = get_checkin_panel = get_equipment_panel = _missing
    get_213rr_panel = get_personnel_panel = get_vehicles_panel = _missing

__all__ = [
    "get_logistics_panel",
    "get_checkin_panel",
    "get_equipment_panel",
    "get_213rr_panel",
    "get_personnel_panel",
    "get_vehicles_panel",
]
