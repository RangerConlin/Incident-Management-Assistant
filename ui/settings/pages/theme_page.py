"""Theme and appearance settings page."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from ..binding import bind_combobox


def _get_setting(bridge: QObject, key: str, default: Optional[str] = None) -> Optional[str]:
    """Safely fetch a setting value from the bridge."""

    getter = getattr(bridge, "getSetting", None)
    if getter is None:
        return default
    try:
        value = getter(key)
    except Exception:  # pragma: no cover - defensive safeguard
        return default
    return str(value) if value is not None else default


def _set_setting(bridge: QObject, key: str, value) -> None:
    setter = getattr(bridge, "setSetting", None)
    if setter is None:
        return
    try:
        setter(key, value)
    except Exception:  # pragma: no cover - defensive safeguard
        return


class ThemePage(QWidget):
    """Visual customization options."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        theme = QComboBox()
        theme.addItem("System Default", "system")
        theme.addItem("Dark", "dark")
        theme.addItem("Light", "light")
        theme.addItem("Custom", "custom")
        self._theme_combo = theme
        self._bridge = bridge
        self._syncing = False
        layout.addRow("Theme:", theme)

        self._initialize_theme_combo()
        theme.currentIndexChanged.connect(self._on_theme_changed)

        if hasattr(bridge, "settingChanged"):
            try:
                bridge.settingChanged.connect(self._on_setting_changed)
            except Exception:  # pragma: no cover - Qt connection failure should be non-fatal
                pass

        font_size = QComboBox()
        font_size.addItems(["Small", "Medium", "Large"])
        bind_combobox(font_size, bridge, "fontSizeIndex", 1)
        layout.addRow("Font Size:", font_size)

        color_profile = QComboBox()
        color_profile.addItems(["Standard SAR", "High Contrast", "Colorblind Safe"])
        bind_combobox(color_profile, bridge, "colorProfileIndex", 0)
        layout.addRow("Color Profile:", color_profile)

        ui_template = QComboBox()
        ui_template.addItems(["Default", "Compact", "Wide", "Operator View"])
        bind_combobox(ui_template, bridge, "uiTemplateIndex", 0)
        layout.addRow("UI Template:", ui_template)

    # ------------------------------------------------------------------
    # Theme wiring helpers
    def _initialize_theme_combo(self) -> None:
        theme_name = _get_setting(self._bridge, "themeName", "light") or "light"
        index = self._index_for_theme(theme_name)
        if index < 0:
            stored_index = _get_setting(self._bridge, "themeIndex")
            try:
                index = int(stored_index) if stored_index is not None else 0
            except (TypeError, ValueError):
                index = 0
        self._set_combo_index(index)

    def _index_for_theme(self, theme_name: str) -> int:
        theme_name = (theme_name or "").lower()
        if theme_name.startswith("custom:"):
            return self._find_combo_data("custom")
        if theme_name in {"light", "dark"}:
            return self._find_combo_data(theme_name)
        return -1

    def _find_combo_data(self, data: str) -> int:
        for idx in range(self._theme_combo.count()):
            if self._theme_combo.itemData(idx) == data:
                return idx
        return -1

    def _set_combo_index(self, index: int) -> None:
        if index < 0 or index >= self._theme_combo.count():
            index = 0
        self._syncing = True
        try:
            self._theme_combo.setCurrentIndex(index)
        finally:
            self._syncing = False

    def _on_theme_changed(self, index: int) -> None:
        if self._syncing:
            return

        data = self._theme_combo.itemData(index)
        # Persist index for future sessions
        _set_setting(self._bridge, "themeIndex", int(index))

        if data == "dark":
            _set_setting(self._bridge, "themeName", "dark")
        elif data == "light":
            _set_setting(self._bridge, "themeName", "light")
        elif data == "custom":
            current = _get_setting(self._bridge, "themeName")
            if not (isinstance(current, str) and current.startswith("custom:")):
                # Fall back to light if no custom theme is registered
                _set_setting(self._bridge, "themeName", "light")
        else:  # "system" or unknown
            # Default to light until an OS-aware theme is implemented
            _set_setting(self._bridge, "themeName", "light")

    def _on_setting_changed(self, key, value) -> None:
        if key == "themeName":
            self._set_combo_index(self._index_for_theme(str(value)))
        elif key == "themeIndex" and not self._syncing:
            try:
                idx = int(value)
            except (TypeError, ValueError):
                return
            self._set_combo_index(idx)
