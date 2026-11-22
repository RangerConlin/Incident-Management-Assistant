"""Tiny fire-and-forget background-call helper, Checklist widgets only.

`utils/api_client.py` is fully synchronous, and no existing desktop module
runs its network calls off the UI thread (every panel in this app calls it
directly and accepts the blocking round trip — see `utils/api_client.py`'s
own docstring). The Checklist execution widget saves a response on nearly
every keystroke (debounced) and the product spec explicitly requires the
UI not to block during those saves, so this module adds a minimal,
self-contained `QThread` wrapper for Checklist response writes and
full-checklist reloads only. It changes nothing about `api_client` or any
other module's calling convention.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal


class BackgroundCall(QThread):
    """Runs ``fn(*args, **kwargs)`` off the UI thread.

    Caller must keep a reference to the instance until one of
    ``succeeded``/``failed`` fires (storing it on the widget that started
    it is enough) — PySide6 only keeps a `QThread` alive while something
    still references it.
    """

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D102 - QThread override
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - reported via `failed`, never swallowed
            self.failed.emit(exc)
        else:
            self.succeeded.emit(result)


__all__ = ["BackgroundCall"]
