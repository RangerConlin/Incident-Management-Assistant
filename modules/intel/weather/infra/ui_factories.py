"""Factories for showing weather module UI components."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from .window_registry import WindowRegistry
from ..services.api_link import WeatherApiManager
from ..windows.override_location_dialog import OverrideLocationDialog


def open_alert_details(payload: Optional[dict] = None) -> QWidget:
    from ..windows.alert_details_window import AlertDetailsWindow

    return WindowRegistry.instance().open_or_raise(
        AlertDetailsWindow,
        key="AlertDetailsWindow",
        allow_multiple=False,
        payload=payload or {},
    )


def open_hwo_viewer() -> QWidget:
    from ..windows.hwo_viewer_window import HwoViewerWindow

    return WindowRegistry.instance().open_or_raise(
        HwoViewerWindow,
        key="HwoViewerWindow",
        allow_multiple=False,
    )


def open_weather_timeline(stations: Optional[list[str]] = None) -> QWidget:
    from ..windows.weather_timeline_window import WeatherTimelineWindow

    return WindowRegistry.instance().open_or_raise(
        WeatherTimelineWindow,
        key="WeatherTimelineWindow",
        allow_multiple=False,
        stations=stations or [],
    )


def open_aviation_window(stations: Optional[list[str]] = None) -> QWidget:
    from ..windows.aviation_weather_window import AviationWeatherWindow

    return WindowRegistry.instance().open_or_raise(
        AviationWeatherWindow,
        allow_multiple=True,
        stations=stations or [],
    )


def open_advisories_window() -> QWidget:
    from ..windows.advisories_lightning_window import AdvisoriesLightningWindow

    return WindowRegistry.instance().open_or_raise(
        AdvisoriesLightningWindow,
        key="AdvisoriesLightningWindow",
        allow_multiple=False,
    )


def open_settings_dialog(parent: Optional[QWidget] = None) -> QWidget:
    from ..windows.settings_dialog import SettingsDialog

    return WindowRegistry.instance().open_or_raise(
        SettingsDialog,
        key="SettingsDialog",
        allow_multiple=False,
    )


def open_export_dialog(parent: Optional[QWidget] = None) -> QWidget:
    from ..windows.export_briefing_dialog import ExportBriefingDialog

    return WindowRegistry.instance().open_or_raise(
        ExportBriefingDialog,
        key="ExportBriefingDialog",
        allow_multiple=False,
    )


def open_override_location(parent: Optional[QWidget] = None) -> QWidget:
    """Open the override dialog and, on Apply, request data for selection.

    Currently handles the 'manual' coordinate path; 'ICP' and 'city/ZIP'
    selections are placeholders until upstream services provide coordinates
    and geocoding, respectively.
    """
    dialog: OverrideLocationDialog = WindowRegistry.instance().open_or_raise(
        OverrideLocationDialog,
        allow_multiple=True,
    )  # type: ignore[assignment]

    def _on_accept() -> None:
        mode = dialog.selected_mode()
        api = WeatherApiManager.instance()
        if mode == "manual":
            lat, lon = dialog.get_manual_coords()
            api.request_advisories(latitude=lat, longitude=lon)
            api.request_lightning(latitude=lat, longitude=lon, radius_nm=25.0)
        elif mode == "icp":
            try:
                from utils import incident_meta as _incident_meta

                loc = _incident_meta.get_icp_location()
                if loc:
                    api.request_advisories(latitude=loc.latitude, longitude=loc.longitude)
                    api.request_lightning(latitude=loc.latitude, longitude=loc.longitude, radius_nm=25.0)
            except Exception:
                pass
        # 'city' remains a no-op until a geocoder-backed search is provided

    try:
        dialog.accepted.disconnect()
    except Exception:
        pass
    dialog.accepted.connect(_on_accept)
    return dialog


def open_current_forecast_window(parent: Optional[QWidget] = None) -> QWidget:
    from ..windows.current_forecast_window import CurrentForecastWindow

    return WindowRegistry.instance().open_or_raise(
        CurrentForecastWindow,
        key="CurrentForecastWindow",
        allow_multiple=False,
    )


def open_sun_times_panel(parent: Optional[QWidget] = None) -> QWidget:
    from ..windows.sun_times_panel import SunTimesPanel

    return WindowRegistry.instance().open_or_raise(
        SunTimesPanel,
        allow_multiple=True,
    )


def show_alert_toast(payload: dict) -> QWidget:
    from ..windows.alert_toast import AlertToast

    return WindowRegistry.instance().open_or_raise(
        AlertToast,
        allow_multiple=True,
        payload=payload,
    )


__all__ = [
    "open_alert_details",
    "open_hwo_viewer",
    "open_weather_timeline",
    "open_aviation_window",
    "open_advisories_window",
    "open_settings_dialog",
    "open_export_dialog",
    "open_override_location",
    "open_sun_times_panel",
    "show_alert_toast",
    "open_current_forecast_window",
]
