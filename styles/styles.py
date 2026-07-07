from __future__ import annotations

import weakref
from typing import Callable, Dict, Literal, cast

try:  # pragma: no cover - allow running without Qt libraries
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtGui import QColor, QPalette, QBrush
    from PySide6.QtWidgets import QApplication, QWidget
    import shiboken6
except ImportError:  # pragma: no cover
    shiboken6 = None  # type: ignore[assignment]

    class Signal:  # lightweight signal emulation for tests
        def __init__(self, *_, **__):
            self._subs: list[Callable] = []

        def connect(self, callback: Callable) -> None:
            self._subs.append(callback)

        def emit(self, *args, **kwargs) -> None:
            for cb in list(self._subs):
                try:
                    cb(*args, **kwargs)
                except Exception:
                    pass

        def disconnect(self, callback: Callable) -> None:
            if callback in self._subs:
                self._subs.remove(callback)

    class QObject:  # pragma: no cover - stub
        pass

    class QColor:  # simple RGB container
        def __init__(self, *args):
            if not args:
                self._r = self._g = self._b = 0
            elif isinstance(args[0], str):
                value = args[0].lstrip("#")
                if len(value) >= 6:
                    self._r = int(value[0:2], 16)
                    self._g = int(value[2:4], 16)
                    self._b = int(value[4:6], 16)
                else:
                    self._r = self._g = self._b = 0
            else:
                r, g, b = (list(args) + [0, 0, 0])[:3]
                self._r, self._g, self._b = int(r), int(g), int(b)

        def red(self) -> int:
            return self._r

        def green(self) -> int:
            return self._g

        def blue(self) -> int:
            return self._b

    class QBrush:  # pragma: no cover - stub
        def __init__(self, color: "QColor"):
            self._color = color

        def color(self) -> "QColor":
            return self._color

    class QPalette:  # pragma: no cover - stub storing values
        def __init__(self):
            self._colors: Dict[int, QColor] = {}

        def setColor(self, role: int, color: "QColor") -> None:
            self._colors[role] = color

    class _StubSignal:
        def connect(self, *_args, **_kwargs) -> None:
            pass

    class QWidget:  # pragma: no cover - stub
        destroyed = _StubSignal()

    class QApplication:  # pragma: no cover - stub
        def __init__(self, *_args, **_kwargs):
            pass

        def setPalette(self, *_args, **_kwargs) -> None:
            pass

from styles.profiles import get_profile_name, load_profile

_initial_profile = get_profile_name()
if _initial_profile not in {"light", "dark"}:
    _initial_profile = "light"

THEME_NAME: Literal["light", "dark"] = cast(Literal["light", "dark"], _initial_profile)


class StyleBus(QObject):
    """Signal bus for style/theme changes."""

    THEME_CHANGED = Signal(str)


style_bus = StyleBus()


def _ensure_qcolor(value: str | tuple[int, int, int] | QColor) -> QColor:
    if isinstance(value, QColor):
        return value
    if isinstance(value, (tuple, list)):
        r, g, b = (list(value) + [0, 0, 0])[:3]
        return QColor(int(r), int(g), int(b))
    return QColor(str(value))


def _build_palette(profile_module) -> Dict[str, QColor]:
    data = getattr(profile_module, "PALETTE", {})
    return {key: _ensure_qcolor(value) for key, value in data.items()}


def _build_status(profile_module, attribute: str) -> Dict[str, Dict[str, QBrush]]:
    data = getattr(profile_module, attribute, {})
    mapping: Dict[str, Dict[str, QBrush]] = {}
    for key, colors in data.items():
        bg = _ensure_qcolor(colors.get("bg", "#000000"))
        fg = _ensure_qcolor(colors.get("fg", "#ffffff"))
        mapping[key] = {"bg": QBrush(bg), "fg": QBrush(fg)}
    return mapping


def _build_flat_colors(profile_module, attribute: str) -> Dict[str, QColor]:
    data = getattr(profile_module, attribute, {})
    return {key: _ensure_qcolor(value) for key, value in data.items()}


def _build_team_types(profile_module) -> Dict[str, QColor]:
    return _build_flat_colors(profile_module, "TEAM_TYPE_COLORS")


_LIGHT_PROFILE = load_profile("light")
_DARK_PROFILE = load_profile("dark")

_LIGHT_PALETTE: Dict[str, QColor] = _build_palette(_LIGHT_PROFILE)
_DARK_PALETTE: Dict[str, QColor] = _build_palette(_DARK_PROFILE)

_TASK_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "TASK_STATUS")
_TASK_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "TASK_STATUS")

_TEAM_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "TEAM_STATUS")
_TEAM_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "TEAM_STATUS")

_RESOURCE_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "RESOURCE_STATUS")
_RESOURCE_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "RESOURCE_STATUS")

_INTEL_SUBJECT_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "INTEL_SUBJECT_STATUS")
_INTEL_SUBJECT_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "INTEL_SUBJECT_STATUS")

_INTEL_ASSESSMENT_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "INTEL_ASSESSMENT_STATUS")
_INTEL_ASSESSMENT_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "INTEL_ASSESSMENT_STATUS")

_INTEL_ITEM_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "INTEL_ITEM_STATUS")
_INTEL_ITEM_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "INTEL_ITEM_STATUS")

_INTEL_LEAD_STATUS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "INTEL_LEAD_STATUS")
_INTEL_LEAD_STATUS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "INTEL_LEAD_STATUS")

_INTEL_ENTITY_COLORS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "INTEL_ENTITY_COLORS")
_INTEL_ENTITY_COLORS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "INTEL_ENTITY_COLORS")

_INTEL_PRIORITY_COLORS_LIGHT: Dict[str, Dict[str, QBrush]] = _build_status(_LIGHT_PROFILE, "INTEL_PRIORITY_COLORS")
_INTEL_PRIORITY_COLORS_DARK: Dict[str, Dict[str, QBrush]] = _build_status(_DARK_PROFILE, "INTEL_PRIORITY_COLORS")

_INTEL_TREND_COLORS_LIGHT: Dict[str, QColor] = _build_flat_colors(_LIGHT_PROFILE, "INTEL_TREND_COLORS")
_INTEL_TREND_COLORS_DARK: Dict[str, QColor] = _build_flat_colors(_DARK_PROFILE, "INTEL_TREND_COLORS")

_light_team_types = _build_team_types(_LIGHT_PROFILE)
_dark_team_types = _build_team_types(_DARK_PROFILE)
if not _dark_team_types:
    _dark_team_types = _light_team_types

_TEAM_TYPE_COLOR_TABLE: Dict[str, Dict[str, QColor]] = {
    "light": _light_team_types,
    "dark": _dark_team_types,
}

TEAM_TYPE_COLORS: Dict[str, QColor] = _TEAM_TYPE_COLOR_TABLE.get(THEME_NAME, _light_team_types)


def get_palette() -> Dict[str, QColor]:
    """Return the active palette colors."""
    return _LIGHT_PALETTE if THEME_NAME == "light" else _DARK_PALETTE


def apply_app_palette(app: QApplication) -> None:
    """Apply the current palette to the application."""
    pal = QPalette()
    p = get_palette()
    pal.setColor(QPalette.Window, p["bg"])
    pal.setColor(QPalette.Base, p["bg"])
    pal.setColor(QPalette.AlternateBase, p["muted"])
    pal.setColor(QPalette.WindowText, p["fg"])
    pal.setColor(QPalette.Text, p["fg"])
    pal.setColor(QPalette.ButtonText, p["fg"])
    pal.setColor(QPalette.Button, p["bg"])
    pal.setColor(QPalette.Highlight, p["accent"])
    pal.setColor(QPalette.BrightText, p["fg"])
    app.setPalette(pal)


def set_theme(name: str) -> None:
    """Set the current theme and emit change signal."""
    global THEME_NAME, TEAM_TYPE_COLORS
    name = name.lower()
    if name not in {"light", "dark"}:
        return
    if name == THEME_NAME:
        return
    THEME_NAME = name
    TEAM_TYPE_COLORS = _TEAM_TYPE_COLOR_TABLE.get(name, _light_team_types)
    style_bus.THEME_CHANGED.emit(name)


def team_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _TEAM_STATUS_LIGHT if THEME_NAME == "light" else _TEAM_STATUS_DARK


def task_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _TASK_STATUS_LIGHT if THEME_NAME == "light" else _TASK_STATUS_DARK


def resource_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _RESOURCE_STATUS_LIGHT if THEME_NAME == "light" else _RESOURCE_STATUS_DARK


def intel_subject_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _INTEL_SUBJECT_STATUS_LIGHT if THEME_NAME == "light" else _INTEL_SUBJECT_STATUS_DARK


def intel_assessment_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _INTEL_ASSESSMENT_STATUS_LIGHT if THEME_NAME == "light" else _INTEL_ASSESSMENT_STATUS_DARK


def intel_item_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _INTEL_ITEM_STATUS_LIGHT if THEME_NAME == "light" else _INTEL_ITEM_STATUS_DARK


def intel_lead_status_colors() -> Dict[str, Dict[str, QBrush]]:
    return _INTEL_LEAD_STATUS_LIGHT if THEME_NAME == "light" else _INTEL_LEAD_STATUS_DARK


def intel_entity_colors() -> Dict[str, Dict[str, QBrush]]:
    return _INTEL_ENTITY_COLORS_LIGHT if THEME_NAME == "light" else _INTEL_ENTITY_COLORS_DARK


def intel_priority_colors() -> Dict[str, Dict[str, QBrush]]:
    return _INTEL_PRIORITY_COLORS_LIGHT if THEME_NAME == "light" else _INTEL_PRIORITY_COLORS_DARK


def intel_trend_colors() -> Dict[str, QColor]:
    return _INTEL_TREND_COLORS_LIGHT if THEME_NAME == "light" else _INTEL_TREND_COLORS_DARK


def _qobject_is_valid(obj: object | None) -> bool:
    if obj is None:
        return False
    if shiboken6 is not None:
        try:
            return bool(shiboken6.isValid(obj))
        except Exception:
            return True
    return True


def subscribe_theme(widget: QWidget, callback: Callable[[str], None]) -> None:
    """Subscribe to theme changes and auto-disconnect on widget destruction."""
    try:
        widget_ref = weakref.ref(widget)
    except TypeError:
        widget_ref = lambda: widget  # type: ignore[assignment]

    try:
        callback_ref = weakref.WeakMethod(callback)  # type: ignore[arg-type]
        strong_callback: Callable[[str], None] | None = None
    except TypeError:
        callback_ref = None
        strong_callback = callback

    def _current_callback() -> Callable[[str], None] | None:
        if callback_ref is not None:
            return callback_ref()
        return strong_callback

    def _disconnect(*_: object) -> None:
        """Safely disconnect the wrapper when the widget is destroyed."""
        try:
            style_bus.THEME_CHANGED.disconnect(_on_theme_changed)
        except Exception:
            # Qt shutdown and deleted receivers can surface as RuntimeError,
            # SystemError, or TypeError depending on the PySide state.
            pass

    def _on_theme_changed(name: str) -> None:
        target = widget_ref()
        if not _qobject_is_valid(target):
            _disconnect()
            return
        active_callback = _current_callback()
        if active_callback is None:
            _disconnect()
            return
        try:
            active_callback(name)
        except (RuntimeError, SystemError):
            if not _qobject_is_valid(target):
                _disconnect()
                return
            raise

    style_bus.THEME_CHANGED.connect(_on_theme_changed)
    try:
        widget.destroyed.connect(_disconnect)
    except Exception:
        # In case the widget does not support the destroyed signal
        pass
    _on_theme_changed(THEME_NAME)


__all__ = [
    "THEME_NAME",
    "StyleBus",
    "style_bus",
    "get_palette",
    "apply_app_palette",
    "set_theme",
    "subscribe_theme",
    "team_status_colors",
    "task_status_colors",
    "resource_status_colors",
    "TEAM_TYPE_COLORS",
    "intel_subject_status_colors",
    "intel_assessment_status_colors",
    "intel_item_status_colors",
    "intel_lead_status_colors",
    "intel_entity_colors",
    "intel_priority_colors",
    "intel_trend_colors",
]
