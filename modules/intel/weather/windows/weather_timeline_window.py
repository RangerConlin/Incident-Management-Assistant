"""Weather timeline / strip chart window."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSpacerItem,
    QStatusBar,
    QTableWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings


class WeatherTimelineWindow(QMainWindow):
    """Displays time-series weather data in a strip chart."""

    def __init__(self, stations: List[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weatherTimelineWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Weather Timeline")
        self.resize(1300, 720)
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self._handle_data)
        self._stations = stations or []
        self._setup_ui()
        self._load_state()

    def _setup_ui(self) -> None:
        toolbar = QToolBar("Timeline Toolbar", self)
        toolbar.setMovable(False)
        add_action = toolbar.addAction("Add Station")
        add_action.triggered.connect(self._add_station)
        remove_action = toolbar.addAction("Remove")
        remove_action.triggered.connect(self._remove_station)
        interval_action = toolbar.addAction("Interval")
        interval_action.triggered.connect(self._change_interval)
        export_action = toolbar.addAction("Export PNG")
        export_action.triggered.connect(self._export_png)
        refresh_action = toolbar.addAction("Refresh")
        refresh_action.triggered.connect(self.api.refresh_all)
        self.addToolBar(toolbar)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Range: Now", central))
        controls.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.temp_toggle = QCheckBox("Temp", central)
        self.temp_toggle.setChecked(True)
        controls.addWidget(self.temp_toggle)
        self.wind_toggle = QCheckBox("Wind", central)
        self.wind_toggle.setChecked(True)
        controls.addWidget(self.wind_toggle)
        self.precip_toggle = QCheckBox("Precip", central)
        self.precip_toggle.setChecked(True)
        controls.addWidget(self.precip_toggle)
        self.vis_toggle = QCheckBox("Vis", central)
        self.vis_toggle.setChecked(True)
        controls.addWidget(self.vis_toggle)
        self.sun_toggle = QCheckBox("Sunrise/Sunset", central)
        self.sun_toggle.setChecked(True)
        controls.addWidget(self.sun_toggle)
        layout.addLayout(controls)

        self.chart_placeholder = QLabel("Timeline chart placeholder", central)
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setMinimumHeight(380)
        layout.addWidget(self.chart_placeholder)

        self.table = QTableWidget(0, 4, central)
        self.table.setHorizontalHeaderLabels(["Time", "Temp", "Wind", "Precip%"])
        layout.addWidget(self.table)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        QWidget.setTabOrder(self.temp_toggle, self.wind_toggle)
        QWidget.setTabOrder(self.wind_toggle, self.precip_toggle)
        QWidget.setTabOrder(self.precip_toggle, self.vis_toggle)
        QWidget.setTabOrder(self.vis_toggle, self.sun_toggle)
        QWidget.setTabOrder(self.sun_toggle, self.table)

    def _handle_data(self, payload: dict) -> None:
        self.table.setRowCount(0)
        self.status_bar.showMessage("Timeline data pending live feed.")

    def _load_state(self) -> None:
        geometry = weather_settings().value("geom/WeatherTimelineWindow")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: D401
        weather_settings().set_value("geom/WeatherTimelineWindow", self.saveGeometry())
        super().closeEvent(event)

    # Placeholder slots
    def _add_station(self) -> None:
        self.status_bar.showMessage("Add station not yet implemented.")

    def _remove_station(self) -> None:
        self.status_bar.showMessage("Remove station not yet implemented.")

    def _change_interval(self) -> None:
        self.status_bar.showMessage("Interval change not yet implemented.")

    def _export_png(self) -> None:
        self.status_bar.showMessage("Export pending implementation.")


def show_window(stations: List[str] | None = None) -> WeatherTimelineWindow:
    window = WeatherTimelineWindow(stations or [])
    window.show()
    window.raise_()
    return window


__all__ = ["WeatherTimelineWindow", "show_window"]
