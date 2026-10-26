from __future__ import annotations

from types import SimpleNamespace

from main import MainWindow


class _Dock:
    def __init__(self) -> None:
        self.toggled: list[bool] = []
        self.shown = False
        self.current = False

    def toggleView(self, visible: bool) -> None:  # noqa: N802
        self.toggled.append(visible)

    def show(self) -> None:
        self.shown = True

    def setAsCurrentTab(self) -> None:  # noqa: N802
        self.current = True

    def floatingDockContainer(self):  # noqa: N802
        return None

    def isVisible(self) -> bool:  # noqa: N802
        return self.shown


class _DockManager:
    def __init__(self, dock) -> None:
        self.dock = dock
        self.focused = None

    def findDockWidget(self, _title: str):  # noqa: N802
        return self.dock

    def setDockWidgetFocused(self, dock) -> None:  # noqa: N802
        self.focused = dock


def test_reveal_notification_center_opens_hidden_ads_dock() -> None:
    dock = _Dock()
    window = SimpleNamespace(dock_manager=_DockManager(dock))

    assert MainWindow._reveal_dock_widget(window, "Notification Center") is True
    assert dock.toggled == [True]
    assert dock.shown is True
    assert dock.current is True
    assert window.dock_manager.focused is dock


def test_reveal_notification_center_handles_missing_dock() -> None:
    window = SimpleNamespace(dock_manager=_DockManager(None))
    assert MainWindow._reveal_dock_widget(window, "Notification Center") is False
