"""Utility for managing top-level weather windows."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Type

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QWidget

LOGGER = logging.getLogger(__name__)

_SINGLETON_NAMES = {
    "AlertDetailsWindow",
    "HwoViewerWindow",
    "WeatherTimelineWindow",
    "SettingsDialog",
    "ExportBriefingDialog",
    "AdvisoriesLightningWindow",
}


class WindowRegistry(QObject):
    """Keeps track of open weather windows and enforces policies."""

    _instance: "WindowRegistry" | None = None

    def __init__(self) -> None:
        super().__init__()
        self._singletons: Dict[str, QWidget] = {}
        # Hold strong refs to all opened windows (including non-singletons)
        # to prevent Python GC from destroying top-level windows immediately.
        self._open_windows: list[QWidget] = []

    @classmethod
    def instance(cls) -> "WindowRegistry":
        if cls._instance is None:
            cls._instance = WindowRegistry()
        return cls._instance

    def open_or_raise(
        self,
        window_cls: Type[QWidget],
        *,
        key: Optional[str] = None,
        allow_multiple: bool = False,
        **kwargs,
    ) -> QWidget:
        """Open the window if not already open or raise the existing instance."""

        identifier = key or window_cls.__name__
        is_singleton = not allow_multiple and window_cls.__name__ in _SINGLETON_NAMES
        if is_singleton:
            window = self._singletons.get(identifier)
            if window:
                LOGGER.debug("Raising existing window %s", identifier)
                window.show()
                window.raise_()
                window.activateWindow()
                return window
        window = window_cls(**kwargs)
        if window.parent() is not None:
            raise RuntimeError("Window separation violated: top-level window may not be embedded")
        window.setAttribute(Qt.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda: self._on_destroyed(identifier, window))
        if is_singleton:
            self._singletons[identifier] = window
        # Keep a strong reference so the window is not GC'd when the caller
        # does not hold onto it (common for menu actions).
        self._open_windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()
        LOGGER.debug("Opened window %s", identifier)
        return window

    def _on_destroyed(self, identifier: str, window: QWidget | None = None) -> None:
        if identifier in self._singletons:
            LOGGER.debug("Window %s destroyed; removing from registry", identifier)
            self._singletons.pop(identifier, None)
        if window is not None and window in self._open_windows:
            self._open_windows.remove(window)


__all__ = ["WindowRegistry"]
