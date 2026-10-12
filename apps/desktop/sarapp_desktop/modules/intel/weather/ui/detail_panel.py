"""WeatherDetailPanel — the single window replacing all 11 legacy popups.

Presentational only: all data comes from WeatherManager signals/getters and
the history HTTP client; never touches Mongo directly.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..models.location import WeatherLocation
from ..services.weather_manager import WeatherManager, get_weather_manager
from .dialogs.settings_dialog import WeatherSettingsDialog
from .tabs.alerts_hwo_tab import AlertsHwoTab
from .tabs.aviation_tab import AviationTab
from .tabs.forecast_tab import ForecastTab
from .tabs.history_tab import HistoryTab
from .tabs.stations_tab import StationsTab

_TAB_INDEX = {
    "forecast": 0,
    "aviation": 1,
    "alerts": 2,
    "history": 3,
    "stations": 4,
}


class WeatherDetailPanel(QWidget):
    def __init__(self, incident_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Weather")
        self._incident_id = incident_id
        self._manager: WeatherManager = get_weather_manager(incident_id)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Location"))
        self._location_combo = QComboBox()
        self._location_combo.currentIndexChanged.connect(self._on_location_changed)
        toolbar.addWidget(self._location_combo, 1)
        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setToolTip("Fetch current weather data now instead of waiting for the next poll")
        self._refresh_btn.clicked.connect(self._manager.refresh_all)
        toolbar.addWidget(self._refresh_btn)
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(settings_btn)
        export_btn = QPushButton("⬇ Export Briefing…")
        export_btn.clicked.connect(self._export_briefing)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        self._tabs = QTabWidget()
        self._forecast_tab = ForecastTab(self._manager)
        self._aviation_tab = AviationTab(self._manager)
        self._alerts_tab = AlertsHwoTab(self._manager, incident_id)
        self._history_tab = HistoryTab(self._manager, incident_id)
        self._stations_tab = StationsTab(self._manager)
        self._tabs.addTab(self._forecast_tab, "Current && Forecast")
        self._tabs.addTab(self._aviation_tab, "Aviation")
        self._tabs.addTab(self._alerts_tab, "Alerts + HWO")
        self._tabs.addTab(self._history_tab, "History")
        self._tabs.addTab(self._stations_tab, "Stations")
        layout.addWidget(self._tabs, 1)

        self._manager.locationsChanged.connect(self._rebuild_locations)
        self._manager.pollStarted.connect(self._on_poll_started)
        self._manager.pollFinished.connect(self._on_poll_finished)
        self._rebuild_locations(self._manager.locations())

    def open_tab(self, initial_tab: Optional[str]) -> None:
        if initial_tab and initial_tab in _TAB_INDEX:
            self._tabs.setCurrentIndex(_TAB_INDEX[initial_tab])

    def _rebuild_locations(self, locations) -> None:
        self._location_combo.blockSignals(True)
        self._location_combo.clear()
        for location in locations:
            label = location.label + (" (default)" if location.is_default else "")
            self._location_combo.addItem(label, location.location_id)
        self._location_combo.blockSignals(False)
        default = self._manager.default_location()
        if default is not None:
            index = self._location_combo.findData(default.location_id)
            if index >= 0:
                self._location_combo.setCurrentIndex(index)
        self._on_location_changed(self._location_combo.currentIndex())

    def _current_location(self) -> Optional[WeatherLocation]:
        location_id = self._location_combo.currentData()
        if location_id is None:
            return None
        return next((loc for loc in self._manager.locations() if loc.location_id == location_id), None)

    def _on_location_changed(self, _index: int) -> None:
        location = self._current_location()
        self._forecast_tab.set_location(location)
        self._alerts_tab.set_location(location)
        self._history_tab.set_location(location)

    def _on_poll_started(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("⟳ Refreshing…")

    def _on_poll_finished(self) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("⟳ Refresh")

    def _open_settings(self) -> None:
        dialog = WeatherSettingsDialog(self._manager, self._incident_id, self)
        dialog.exec()

    def _export_briefing(self) -> None:
        from ..export.briefing_pdf import build_weather_briefing_pdf
        from ..export.briefing_png import save_widget_as_png

        choice = QMessageBox.question(
            self,
            "Export Briefing",
            "Export as PDF? (No = export as PNG)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        if choice == QMessageBox.Cancel:
            return
        if choice == QMessageBox.Yes:
            path, _ = QFileDialog.getSaveFileName(self, "Save Briefing PDF", "weather_briefing.pdf", "PDF Files (*.pdf)")
            if not path:
                return
            data = build_weather_briefing_pdf(incident_name=None, manager=self._manager)
            with open(path, "wb") as fh:
                fh.write(data)
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save Briefing PNG", "weather_briefing.png", "PNG Files (*.png)")
            if not path:
                return
            save_widget_as_png(self, path)


__all__ = ["WeatherDetailPanel"]
