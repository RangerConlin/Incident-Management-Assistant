"""Manual harness for weather UI components."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from ..infra import ui_factories
from ..infra.window_registry import WindowRegistry
from ..pages.weather_summary_page import WeatherSummaryPage


class WeatherHarness(QMainWindow):
    """Simple window exposing menu entries for weather components."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Weather UI Harness")
        self.resize(1280, 800)
        self._setup_menu()
        self.summary_page = WeatherSummaryPage(self)
        self.setCentralWidget(self.summary_page)

    def _setup_menu(self) -> None:
        weather_menu = self.menuBar().addMenu("Weather UI")
        weather_menu.addAction(
            "Open Alert Details", lambda: ui_factories.open_alert_details({})
        )
        weather_menu.addAction("Open HWO Viewer", ui_factories.open_hwo_viewer)
        weather_menu.addAction("Open Timeline", ui_factories.open_weather_timeline)
        weather_menu.addAction("Open Aviation", ui_factories.open_aviation_window)
        weather_menu.addAction("Open Advisories", ui_factories.open_advisories_window)
        weather_menu.addAction(
            "Open Settings", lambda: ui_factories.open_settings_dialog(self)
        )
        weather_menu.addAction("Open Export", lambda: ui_factories.open_export_dialog(self))
        weather_menu.addAction("Open Override", lambda: ui_factories.open_override_location(self))
        weather_menu.addAction("Open Sun Times", ui_factories.open_sun_times_panel)


def launch() -> None:
    app = QApplication(sys.argv)
    window = WeatherHarness()
    window.show()
    sys.exit(app.exec())


def _self_test() -> None:
    """Quick self-test verifying window flags."""

    app = QApplication.instance() or QApplication([])
    timeline = ui_factories.open_weather_timeline()
    assert timeline.isWindow()
    timeline.close()
    registry = WindowRegistry.instance()
    try:
        _ = registry.open_or_raise(type(timeline), parent=QMainWindow())
    except RuntimeError as exc:  # noqa: PERF203
        assert "Window separation" in str(exc)


if __name__ == "__main__":  # pragma: no cover
    launch()
