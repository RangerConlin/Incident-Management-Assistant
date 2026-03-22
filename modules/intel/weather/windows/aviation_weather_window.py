"""Aviation weather viewer window."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QInputDialog,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings


class StationTab(QWidget):
    """Widget representing METAR/TAF for a single station."""

    def __init__(self, station: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.station = station
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.raw_label = QTextEdit(self)
        self.raw_label.setReadOnly(True)
        self.raw_label.setAccessibleName(f"{station} Raw Text")
        layout.addWidget(self.raw_label)
        self.decoded_label = QTextEdit(self)
        self.decoded_label.setReadOnly(True)
        self.decoded_label.setAccessibleName(f"{station} Decoded Text")
        layout.addWidget(self.decoded_label)

    def update_content(self, metar: dict | None, taf: dict | None) -> None:
        self.raw_label.setPlainText(metar.get("raw_text", "—") if metar else "—")
        lines = []
        if taf:
            lines.append(taf.get("raw_text", ""))
        self.decoded_label.setPlainText("\n".join(lines) if lines else "No decoded data.")


class AviationWeatherWindow(QMainWindow):
    """Displays METAR and TAF data for selected stations."""

    def __init__(self, stations: List[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aviationWeatherWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Aviation Weather")
        self.resize(1400, 900)
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self._handle_data)
        self._stations = stations or []
        self._setup_ui()
        self._load_state()
        for station in self._stations:
            self._ensure_station_tab(station)

    def _setup_ui(self) -> None:
        self.toolbar = QToolBar("Aviation Toolbar", self)
        self.toolbar.setMovable(False)
        add_action = QAction("Add", self)
        add_action.triggered.connect(self._prompt_add_station)
        self.toolbar.addAction(add_action)
        self.toolbar.addSeparator()
        self.layout_action_tabs = QAction("Tabs", self)
        self.layout_action_tabs.setCheckable(True)
        self.layout_action_tabs.setChecked(True)
        self.toolbar.addAction(self.layout_action_tabs)
        self.layout_action_two = QAction("2-Up", self)
        self.layout_action_two.setCheckable(True)
        self.toolbar.addAction(self.layout_action_two)
        self.layout_action_four = QAction("4-Up", self)
        self.layout_action_four.setCheckable(True)
        self.toolbar.addAction(self.layout_action_four)
        pin_action = QAction("Pin", self)
        self.toolbar.addAction(pin_action)
        self.addToolBar(self.toolbar)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tab_widget = QTabWidget(central)
        self.tab_widget.setAccessibleName("Aviation Station Tabs")
        layout.addWidget(self.tab_widget)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        QWidget.setTabOrder(self.tab_widget, self.status_bar)

    def _prompt_add_station(self) -> None:
        station, ok = QInputDialog.getText(self, "Add Station", "ICAO")
        if ok and station:
            self._ensure_station_tab(station.upper())

    def _ensure_station_tab(self, station: str) -> None:
        for index in range(self.tab_widget.count()):
            if self.tab_widget.widget(index).property("station_id") == station:
                self.tab_widget.setCurrentIndex(index)
                return
        tab = StationTab(station, self.tab_widget)
        tab.setProperty("station_id", station)
        self.tab_widget.addTab(tab, station)
        self.tab_widget.setCurrentWidget(tab)
        self.api.request_metar([station])
        self.api.request_taf([station])

    def _handle_data(self, payload: dict) -> None:
        metar_entries = payload.get("metar", {})
        taf_entries = payload.get("taf", {})
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            station = tab.property("station_id")
            tab.update_content(metar_entries.get(station), taf_entries.get(station))

    def _load_state(self) -> None:
        geometry = weather_settings().value("geom/AviationWeatherWindow")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: D401
        weather_settings().set_value("geom/AviationWeatherWindow", self.saveGeometry())
        super().closeEvent(event)


def show_window(stations: List[str] | None = None) -> AviationWeatherWindow:
    window = AviationWeatherWindow(stations or [])
    window.show()
    window.raise_()
    return window


__all__ = ["AviationWeatherWindow", "show_window"]
