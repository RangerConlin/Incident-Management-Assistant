"""Dockable weather summary page widget."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.facilities.service import FacilitiesService
from ..services.api_link import WeatherApiManager
from ..infra import ui_factories


class WeatherSummaryPage(QWidget):
    """Weather dashboard summary mirroring the design spec."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weatherSummaryPage")
        self.api = WeatherApiManager.instance()
        self._facility_service = FacilitiesService()
        self.api.dataUpdated.connect(self.refresh_display)
        self.api.fetchFailed.connect(self.show_error_banner)
        self._setup_ui()
        self._load_station_list()
        self._load_last_location()
        self._sync_location_presets()

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

        self.preset_combo = QComboBox(header_frame)
        header_layout.addWidget(self.preset_combo)

        self.use_preset_button = QPushButton("Use Preset", header_frame)
        self.use_preset_button.clicked.connect(self._use_selected_preset)
        header_layout.addWidget(self.use_preset_button)

        self.sync_presets_button = QPushButton("Sync Presets", header_frame)
        self.sync_presets_button.clicked.connect(self._sync_location_presets)
        header_layout.addWidget(self.sync_presets_button)

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
        self.add_station_button.clicked.connect(self._add_station)
        toolbar_layout.addWidget(self.add_station_button)
        self.remove_station_button = QPushButton("Remove", toolbar_frame)
        self.remove_station_button.clicked.connect(self._remove_station)
        toolbar_layout.addWidget(self.remove_station_button)
        self.set_default_button = QPushButton("Set Default", toolbar_frame)
        self.set_default_button.clicked.connect(self._set_default_station)
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
        self.auto_log_checkbox.setChecked(False)
        self.auto_log_checkbox.setEnabled(False)
        self.auto_log_checkbox.setToolTip("Safety Notes integration is not configured for the weather module yet.")
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
        QWidget.setTabOrder(self.override_button, self.preset_combo)
        QWidget.setTabOrder(self.preset_combo, self.use_preset_button)
        QWidget.setTabOrder(self.use_preset_button, self.sync_presets_button)
        QWidget.setTabOrder(self.sync_presets_button, self.refresh_button)
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
            self.current_conditions_label.setText(self._format_current_conditions(first_station))
            self.aviation_station_label.setText(f"Station: {first_station.get('station', '—')}")
            self.aviation_raw_label.setText(first_station.get("raw_text", "—"))
        else:
            self.current_conditions_label.setText(
                "Temp: —  Feels: —  Wind: —\nVis: —  Clouds: —\nHumidity: —  Pressure: —"
            )
            self.aviation_station_label.setText("Station: —")
            self.aviation_raw_label.setText("METAR: —")
        forecasts = payload.get("forecast", {}) or {}
        forecast_entry = next(iter(forecasts.values()), None)
        forecast_periods = forecast_entry.get("periods", []) if isinstance(forecast_entry, dict) else []
        for idx, label in enumerate(self.forecast_labels):
            if idx < len(forecast_periods):
                item = forecast_periods[idx]
                text = item.get("detailed_text") or item.get("name") or "—"
                temp = item.get("temperature")
                if temp is not None:
                    text = f"{item.get('name', 'Forecast')}: {temp}°F, {text}"
                label.setText(text)
            else:
                label.setText("—")
        advisories = payload.get("advisories", [])
        self.alerts_list.clear()
        for adv in advisories:
            item = QListWidgetItem(f"{adv.get('event', 'Advisory')} — {adv.get('headline', '—')}")
            self.alerts_list.addItem(item)
        if not advisories:
            self.alerts_list.addItem(QListWidgetItem("No active alerts."))
        hwo_payload = payload.get("hwo")
        if isinstance(hwo_payload, dict) and hwo_payload.get("text"):
            self.hwo_excerpt.setText(self._summarize_hwo(hwo_payload))
        elif forecast_entry:
            label = forecast_entry.get("label") or "Active location"
            self.hwo_excerpt.setText(
                f"No Hazardous Weather Outlook text is cached. Forecast loaded for {label}."
            )
        else:
            self.hwo_excerpt.setText("No outlook available.")

    def show_error_banner(self, context: str, error: Exception) -> None:
        self.hwo_excerpt.setText(f"Error loading {context}: {error}")

    def _use_icp_location(self) -> None:
        try:
            from utils.incident_meta import get_icp_location

            icp = get_icp_location()
        except Exception:
            icp = None
        if not icp:
            self.icp_label.setText("ICP: Not set")
            return
        self.icp_label.setText(f"ICP: {icp.address}")
        self.api.request_advisories(icp.latitude, icp.longitude)
        self.api.request_lightning(icp.latitude, icp.longitude, 25.0)
        self.api.request_forecast(icp.latitude, icp.longitude, icp.address)
        self.api.request_hwo(icp.latitude, icp.longitude)
        self._sync_location_presets()

    def _open_override_location(self) -> None:
        ui_factories.open_override_location(self)

    def _open_aviation_window(self) -> None:
        ui_factories.open_aviation_window()

    def _open_timeline(self) -> None:
        ui_factories.open_weather_timeline()

    def _open_hwo_viewer(self) -> None:
        ui_factories.open_hwo_viewer()

    @staticmethod
    def _format_current_conditions(entry: dict) -> str:
        decoded = entry.get("decoded") or {}
        station = entry.get("station", "—")
        temperature = WeatherSummaryPage._first_value(decoded, "temp", "tempC", "temperature")
        dewpoint = WeatherSummaryPage._first_value(decoded, "dewp", "dewpoint", "dewpointC")
        wind = WeatherSummaryPage._first_value(decoded, "wdir", "windDir", "windDirection")
        wind_speed = WeatherSummaryPage._first_value(decoded, "wspd", "windSpeed")
        visibility = WeatherSummaryPage._first_value(decoded, "visib", "visibility")
        pressure = WeatherSummaryPage._first_value(decoded, "altim", "pressure", "seaLevelPressure")
        clouds = WeatherSummaryPage._format_cloud_layers(decoded.get("clouds"))
        temp_text = f"{temperature}" if temperature is not None else "—"
        dew_text = f"{dewpoint}" if dewpoint is not None else "—"
        wind_bits = []
        if wind is not None:
            wind_bits.append(str(wind))
        if wind_speed is not None:
            wind_bits.append(str(wind_speed))
        wind_text = " ".join(wind_bits) if wind_bits else "—"
        vis_text = f"{visibility}" if visibility is not None else "—"
        pressure_text = f"{pressure}" if pressure is not None else "—"
        return (
            f"Station: {station}  Temp: {temp_text}  Dewpoint: {dew_text}\n"
            f"Wind: {wind_text}  Vis: {vis_text}\n"
            f"Clouds: {clouds}  Pressure: {pressure_text}"
        )

    @staticmethod
    def _first_value(payload: dict, *keys: str):
        for key in keys:
            if key in payload and payload[key] not in (None, ""):
                return payload[key]
        return None

    @staticmethod
    def _format_cloud_layers(clouds) -> str:
        if not isinstance(clouds, list) or not clouds:
            return "—"
        layers = []
        for layer in clouds:
            if not isinstance(layer, dict):
                continue
            cover = layer.get("cover") or layer.get("amount") or "Cloud"
            base = layer.get("base") or layer.get("baseFtAgl")
            if base not in (None, ""):
                layers.append(f"{cover}@{base}")
            else:
                layers.append(str(cover))
        return ", ".join(layers) if layers else "—"

    @staticmethod
    def _summarize_hwo(payload: dict) -> str:
        office = payload.get("office") or "Unknown office"
        issued = payload.get("time") or "Unknown time"
        text = str(payload.get("text") or "").strip().replace("\r\n", "\n")
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "Outlook available.")
        return f"{office} | {issued}\n{first_line}"

    def _load_station_list(self) -> None:
        self.stations_list.clear()
        stations = self.api.station_codes()
        if not stations:
            self.stations_list.addItem("—")
            return
        for station in stations:
            self.stations_list.addItem(station)

    def _load_last_location(self) -> None:
        lat, lon = self.api.weather_location()
        if lat is None or lon is None:
            return
        self.icp_label.setText(f"ICP: {lat:.4f}, {lon:.4f}")

    def _load_preset_list(self) -> None:
        current = self.api.active_location_preset()
        self.preset_combo.clear()
        selected_index = -1
        for idx, preset in enumerate(self.api.location_presets()):
            label = str(preset.get("label") or "Preset")
            self.preset_combo.addItem(label, dict(preset))
            if str(preset.get("id") or "") == current:
                selected_index = idx
        if selected_index >= 0:
            self.preset_combo.setCurrentIndex(selected_index)

    def _sync_location_presets(self) -> None:
        presets: list[dict] = []
        seen: set[str] = set()

        def add_preset(preset: dict) -> None:
            preset_id = str(preset.get("id") or "")
            if not preset_id or preset_id in seen:
                return
            seen.add(preset_id)
            presets.append(preset)

        try:
            from utils.incident_meta import get_icp_location

            icp = get_icp_location()
        except Exception:
            icp = None
        if icp:
            add_preset(
                {
                    "id": "icp",
                    "label": f"ICP - {icp.address}",
                    "source": "incident_overview",
                    "facility_id": "",
                    "latitude": icp.latitude,
                    "longitude": icp.longitude,
                }
            )

        try:
            facilities = self._facility_service.list_facilities(status="active")
        except Exception:
            facilities = []
        for facility in facilities:
            if facility.latitude is None or facility.longitude is None:
                continue
            add_preset(
                {
                    "id": f"facility:{facility.id}",
                    "label": f"{facility.name} [{facility.facility_type}]",
                    "source": "facility",
                    "facility_id": facility.id,
                    "latitude": facility.latitude,
                    "longitude": facility.longitude,
                }
            )

        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id

            incident_id = get_active_incident_id()
            rows = (
                api_client.get(f"/api/incidents/{incident_id}/medical/ics206/aid-stations", params={"op": None})
                if incident_id
                else []
            ) or []
        except Exception:
            rows = []
        for row in rows:
            lat = row.get("latitude")
            lon = row.get("longitude")
            if lat in (None, "") or lon in (None, ""):
                continue
            add_preset(
                {
                    "id": f"aid-station:{row.get('id')}",
                    "label": f"Aid Station - {row.get('name') or row.get('location_text') or row.get('id')}",
                    "source": "ics206_aid_station",
                    "facility_id": row.get("facility_id") or "",
                    "latitude": lat,
                    "longitude": lon,
                }
            )

        active = self.api.active_location_preset()
        if active and active not in seen:
            active = ""
        self.api.save_location_presets(presets, active_preset=active)
        self._load_preset_list()

    def _use_selected_preset(self) -> None:
        preset = self.preset_combo.currentData()
        if not isinstance(preset, dict):
            return
        try:
            lat = float(preset.get("latitude"))
            lon = float(preset.get("longitude"))
        except (TypeError, ValueError):
            return
        label = str(preset.get("label") or "Weather preset")
        self.icp_label.setText(f"Preset: {label}")
        self.api.save_location_presets(self.api.location_presets(), active_preset=str(preset.get("id") or ""))
        self.api.request_advisories(lat, lon)
        self.api.request_lightning(lat, lon, 25.0)
        self.api.request_forecast(lat, lon, label)
        self.api.request_hwo(lat, lon)

    def _add_station(self) -> None:
        station, ok = QInputDialog.getText(self, "Add Station", "ICAO")
        if not (ok and station):
            return
        self.api.add_station_code(station)
        station_code = station.strip().upper()
        self.api.request_metar([station_code])
        self.api.request_taf([station_code])
        self._load_station_list()

    def _remove_station(self) -> None:
        stations = self.api.station_codes()
        if not stations:
            return
        station, ok = QInputDialog.getItem(self, "Remove Station", "ICAO", stations, 0, False)
        if not (ok and station):
            return
        self.api.remove_station_code(station)
        self._load_station_list()

    def _set_default_station(self) -> None:
        stations = self.api.station_codes()
        if not stations:
            return
        station, ok = QInputDialog.getItem(self, "Set Default Station", "ICAO", stations, 0, False)
        if not (ok and station):
            return
        self.api.set_default_station(station)
        self._load_station_list()


__all__ = ["WeatherSummaryPage"]
