from __future__ import annotations

from types import SimpleNamespace

from styles import styles as style_core
from styles.qss_helpers import global_qss


class _FakeSignal:
    def __init__(self, *, disconnect_error: Exception | None = None) -> None:
        self.callbacks: list = []
        self.disconnect_error = disconnect_error

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def disconnect(self, callback) -> None:
        if self.disconnect_error is not None:
            raise self.disconnect_error
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def emit(self, *args) -> None:
        for callback in list(self.callbacks):
            callback(*args)


class _FakeWidget:
    def __init__(self) -> None:
        self.destroyed = _FakeSignal()


class _Receiver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_theme(self, name: str) -> None:
        self.calls.append(name)


def test_subscribe_theme_disconnects_wrapper_on_destroy(monkeypatch) -> None:
    theme_signal = _FakeSignal()
    monkeypatch.setattr(
        style_core,
        "style_bus",
        SimpleNamespace(THEME_CHANGED=theme_signal),
    )

    widget = _FakeWidget()
    receiver = _Receiver()

    style_core.subscribe_theme(widget, receiver.on_theme)

    assert receiver.calls == [style_core.THEME_NAME]
    assert len(theme_signal.callbacks) == 1
    assert theme_signal.callbacks[0] != receiver.on_theme

    theme_signal.emit("dark")
    assert receiver.calls[-1] == "dark"

    widget.destroyed.emit()
    assert theme_signal.callbacks == []

    theme_signal.emit("light")
    assert receiver.calls[-1] == "dark"


def test_subscribe_theme_destroy_ignores_systemerror_from_qt_disconnect(monkeypatch) -> None:
    theme_signal = _FakeSignal(disconnect_error=SystemError("receiver already deleted"))
    monkeypatch.setattr(
        style_core,
        "style_bus",
        SimpleNamespace(THEME_CHANGED=theme_signal),
    )

    widget = _FakeWidget()
    receiver = _Receiver()

    style_core.subscribe_theme(widget, receiver.on_theme)

    widget.destroyed.emit()


def test_global_qss_focus_rule_uses_background_property() -> None:
    tokens = {
        "bg_window": "#010101",
        "bg_panel": "#020202",
        "bg_raised": "#030303",
        "fg_primary": "#040404",
        "fg_muted": "#050505",
        "divider": "#060606",
        "dock_tab_bg": "#070707",
        "ctrl_border": "#080808",
        "ctrl_focus": "#090909",
        "ctrl_hover": "#101010",
        "btn_bg": "#111111",
        "btn_hover": "#121212",
        "btn_pressed": "#131313",
        "btn_checked": "#141414",
        "btn_focus": "#151515",
        "btn_disabled": "#161616",
    }

    qss = global_qss(tokens)

    assert "baqckground" not in qss
    assert "background: #151515;" in qss
