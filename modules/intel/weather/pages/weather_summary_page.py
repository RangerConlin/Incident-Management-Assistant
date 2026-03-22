"""Dockable weather summary page widget."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..infra import ui_factories


class WeatherSummaryPage(QWidget):
    """Weather dashboard summary mirroring the design spec."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weatherSummaryPage")
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self.refresh_display)
        self.api.fetchFailed.connect(self.show_error_banner)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header_frame = QFrame(self)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title = QLabel("Weather Safety", header_frame)
        title.setObjectName("weatherSummaryTitle")
        title.setAccessibleName("Weather Safety Header")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.icp_label = QLabel("ICP: —", header_frame)
        self.icp_label.setAccessibleName("ICP Coordinates")
        header_layout.addWidget(self.icp_label)

        self.use_icp_button = QPushButton("Use ICP", header_frame)
        self.use_icp_button.setAccessibleName("Use ICP Location")
        self.use_icp_button.clicked.connect(self._use_icp_location)
        header_layout.addWidget(self.use_icp_button)

        self.override_button = QPushButton("Override", header_frame)
        self.override_button.setAccessibleName("Override Location")
        self.override_button.clicked.connect(self._open_override_location)
        header_layout.addWidget(self.override_button)

        self.refresh_button = QPushButton("Refresh", header_frame)
        self.refresh_button.setAccessibleName("Refresh Weather Data")
        self.refresh_button.clicked.connect(self.api.refresh_all)
        header_layout.addWidget(self.refresh_button)

        layout.addWidget(header_frame)

        toolbar_frame = QFrame(self)
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        self.add_station_button = QPushButton("Add Station", toolbar_frame)
        toolbar_layout.addWidget(self.add_station_button)
        self.remove_station_button = QPushButton("Remove", toolbar_frame)
        toolbar_layout.addWidget(self.remove_station_button)
        self.set_default_button = QPushButton("Set Default", toolbar_frame)
        toolbar_layout.addWidget(self.set_default_button)
        toolbar_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.open_timeline_button = QPushButton("Open Timeline", toolbar_frame)
        self.open_timeline_button.clicked.connect(self._open_timeline)
        toolbar_layout.addWidget(self.open_timeline_button)
        self.open_metar_button = QPushButton("Open METAR/TAF", toolbar_frame)
        self.open_metar_button.clicked.connect(self._open_aviation_window)
        toolbar_layout.addWidget(self.open_metar_button)
        self.advisories_button = QPushButton("Advisories", toolbar_frame)
        self.advisories_button.clicked.connect(ui_factories.open_advisories_window)
        toolbar_layout.addWidget(self.advisories_button)
        self.settings_button = QPushButton("Settings", toolbar_frame)
        self.settings_button.clicked.connect(lambda: ui_factories.open_settings_dialog(self))
        toolbar_layout.addWidget(self.settings_button)
        layout.addWidget(toolbar_frame)

        splitter = QSplitter(Qt.Horizontal, self)
        self.stations_list = QListWidget(splitter)
        self.stations_list.setAccessibleName("Saved Stations List")
        self.stations_list.addItem("—")
        self.stations_list.itemDoubleClicked.connect(lambda _: self._open_aviation_window())

        right_container = QWidget(splitter)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        body_frame = QFrame(right_container)
        body_layout = QGridLayout(body_frame)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setHorizontalSpacing(12)
        body_layout.setVerticalSpacing(12)

        current_group = QGroupBox("Current Conditions", body_frame)
        current_layout = QVBoxLayout(current_group)
        self.current_conditions_label = QLabel(
            "Temp: —  Feels: —  Wind: —\nVis: —  Clouds: —\nHumidity: —  Pressure: —",
            current_group,
        )
        self.current_conditions_label.setAccessibleName("Current Conditions Summary")
        current_layout.addWidget(self.current_conditions_label)
        body_layout.addWidget(current_group, 0, 0)

        forecast_group = QGroupBox("3-Day Forecast", body_frame)
        forecast_layout = QVBoxLayout(forecast_group)
        self.forecast_labels: List[QLabel] = []
        for _ in range(3):
            lbl = QLabel("—", forecast_group)
            lbl.setAccessibleName("Forecast Entry")
            forecast_layout.addWidget(lbl)
            self.forecast_labels.append(lbl)
        body_layout.addWidget(forecast_group, 0, 1)

        aviation_group = QGroupBox("Aviation Summary", body_frame)
        aviation_layout = QVBoxLayout(aviation_group)
        self.aviation_station_label = QLabel("Station: —", aviation_group)
        aviation_layout.addWidget(self.aviation_station_label)
        self.aviation_raw_label = QLabel("METAR: —", aviation_group)
        self.aviation_raw_label.setAccessibleName("Aviation Raw Data")
        self.aviation_raw_label.setWordWrap(True)
        aviation_layout.addWidget(self.aviation_raw_label)
        open_aviation_button = QPushButton("Open Aviation Weather", aviation_group)
        open_aviation_button.clicked.connect(self._open_aviation_window)
        aviation_layout.addWidget(open_aviation_button)
        body_layout.addWidget(aviation_group, 0, 2)

        alerts_group = QGroupBox("Active Alerts", body_frame)
        alerts_layout = QVBoxLayout(alerts_group)
        self.alerts_list = QListWidget(alerts_group)
        self.alerts_list.setAccessibleName("Active Alerts List")
        alerts_layout.addWidget(self.alerts_list)
        self.auto_log_checkbox = QCheckBox("Auto-log severe alerts to Safety Notes", alerts_group)
        alerts_layout.addWidget(self.auto_log_checkbox)
        body_layout.addWidget(alerts_group, 1, 0, 1, 3)

        hwo_group = QGroupBox("Hazardous Weather Outlook", body_frame)
        hwo_layout = QVBoxLayout(hwo_group)
        self.hwo_excerpt = QLabel("No outlook available.", hwo_group)
        self.hwo_excerpt.setWordWrap(True)
        hwo_layout.addWidget(self.hwo_excerpt)
        self.open_hwo_button = QPushButton("Open HWO Viewer", hwo_group)
        self.open_hwo_button.clicked.connect(self._open_hwo_viewer)
        hwo_layout.addWidget(self.open_hwo_button)
        body_layout.addWidget(hwo_group, 2, 0, 1, 3)

        right_layout.addWidget(body_frame)

        footer_frame = QFrame(right_container)
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        self.open_aviation_footer = QPushButton("Open Aviation Weather", footer_frame)
        self.open_aviation_footer.clicked.connect(self._open_aviation_window)
        footer_layout.addWidget(self.open_aviation_footer)
        self.open_timeline_footer = QPushButton("Timeline View", footer_frame)
        self.open_timeline_footer.clicked.connect(self._open_timeline)
        footer_layout.addWidget(self.open_timeline_footer)
        self.open_settings_footer = QPushButton("Settings", footer_frame)
        self.open_settings_footer.clicked.connect(lambda: ui_factories.open_settings_dialog(self))
        footer_layout.addWidget(self.open_settings_footer)
        self.open_export_footer = QPushButton("Export Snippet", footer_frame)
        self.open_export_footer.clicked.connect(lambda: ui_factories.open_export_dialog(self))
        footer_layout.addWidget(self.open_export_footer)
        footer_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        right_layout.addWidget(footer_frame)

        splitter.addWidget(right_container)
        layout.addWidget(splitter)

        QWidget.setTabOrder(self.use_icp_button, self.override_button)
        QWidget.setTabOrder(self.override_button, self.refresh_button)
        QWidget.setTabOrder(self.refresh_button, self.add_station_button)
        QWidget.setTabOrder(self.add_station_button, self.remove_station_button)
        QWidget.setTabOrder(self.remove_station_button, self.set_default_button)
        QWidget.setTabOrder(self.set_default_button, self.open_timeline_button)
        QWidget.setTabOrder(self.open_timeline_button, self.open_metar_button)
        QWidget.setTabOrder(self.open_metar_button, self.advisories_button)
        QWidget.setTabOrder(self.advisories_button, self.settings_button)
        QWidget.setTabOrder(self.settings_button, self.stations_list)
        QWidget.setTabOrder(self.stations_list, self.alerts_list)
        QWidget.setTabOrder(self.alerts_list, self.open_hwo_button)
        QWidget.setTabOrder(self.open_hwo_button, self.open_aviation_footer)
        QWidget.setTabOrder(self.open_aviation_footer, self.open_timeline_footer)
        QWidget.setTabOrder(self.open_timeline_footer, self.open_settings_footer)
        QWidget.setTabOrder(self.open_settings_footer, self.open_export_footer)

    def refresh_display(self, payload: dict) -> None:
        metar_entries = payload.get("metar", {})
        if metar_entries:
            first_station = next(iter(metar_entries.values()))
            self.current_conditions_label.setText(
                "Temp: —  Feels: —  Wind: —\nVis: —  Clouds: —\nHumidity: —  Pressure: —"
            )
            self.aviation_station_label.setText(f"Station: {first_station.get('station', '—')}")
            self.aviation_raw_label.setText(first_station.get("raw_text", "—"))
        advisories = payload.get("advisories", [])
        self.alerts_list.clear()
        for adv in advisories:
            item = QListWidgetItem(f"{adv.get('event', 'Advisory')} — {adv.get('headline', '—')}")
            self.alerts_list.addItem(item)
        if not advisories:
            self.alerts_list.addItem(QListWidgetItem("No active alerts."))

    def show_error_banner(self, context: str, error: Exception) -> None:
        self.hwo_excerpt.setText(f"Error loading {context}: {error}")

    def _use_icp_location(self) -> None:
        self.icp_label.setText("ICP: Using active incident")

    def _open_override_location(self) -> None:
        ui_factories.open_override_location(self)

    def _open_aviation_window(self) -> None:
        ui_factories.open_aviation_window()

    def _open_timeline(self) -> None:
        ui_factories.open_weather_timeline()

    def _open_hwo_viewer(self) -> None:
        ui_factories.open_hwo_viewer()


__all__ = ["WeatherSummaryPage"]
