import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication

from modules.intel.weather.services.api_link import WeatherApiManager
from modules.intel.weather.models.readings import MetarReading, TafReading
from modules.intel.weather.models.advisory import Advisory


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_weather_api_manager():
    WeatherApiManager._instance = None
    yield
    WeatherApiManager._instance = None


def _make_workspace_temp_dir(name: str) -> Path:
    path = Path(".pytest_weather_tmp") / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_request_methods_run_without_network(monkeypatch, qapp):
    api = WeatherApiManager.instance()

    # Force cache dir to a temp location by monkeypatching cache helpers
    from modules.intel.weather.services import cache as cache_mod

    tmp_cache = _make_workspace_temp_dir("request_methods") / "weather_cache"
    tmp_cache.mkdir(parents=True, exist_ok=True)

    def fake_cache_path(name: str) -> Path:
        safe = name.replace("/", "_")
        return tmp_cache / f"{safe}.json"

    monkeypatch.setattr(cache_mod, "cache_path", fake_cache_path)

    # Make _run_async synchronous to avoid threads in tests
    def run_sync(func, callback, context):  # noqa: ANN001
        result = func()
        callback(result)

    monkeypatch.setattr(api, "_run_async", run_sync)

    # Stub providers
    monkeypatch.setattr(
        api._metar_provider,  # type: ignore[attr-defined]
        "fetch_metar",
        lambda codes: [MetarReading(station="KJFK", raw_text="METAR KJFK 010000Z 18005KT 10SM CLR 12/08 A2992")],
    )
    monkeypatch.setattr(
        api._taf_provider,  # type: ignore[attr-defined]
        "fetch_taf",
        lambda codes: [TafReading(station="KJFK", raw_text="TAF KJFK 010000Z ...")],
    )
    monkeypatch.setattr(
        api._advisory_provider,  # type: ignore[attr-defined]
        "fetch_advisories",
        lambda lat, lon: [Advisory(event="Test Advisory", severity=None, start=None, end=None, headline=None, description=None)],
    )

    # Capture signals
    updates = []
    api.dataUpdated.connect(lambda payload: updates.append(payload))

    # Exercise
    api.request_metar(["KJFK"])
    api.request_taf(["KJFK"])
    api.request_advisories(40.0, -73.0)

    assert updates, "Expected dataUpdated signal to fire"
    latest = updates[-1]
    assert latest["metar"].get("KJFK"), "METAR cache missing KJFK"
    assert latest["taf"].get("KJFK"), "TAF cache missing KJFK"
    assert isinstance(latest["advisories"], list)


def test_override_location_apply_triggers_requests(monkeypatch, qapp):
    # Arrange
    called = {"advisories": None, "lightning": None, "hwo": None}
    api = WeatherApiManager.instance()

    monkeypatch.setattr(api, "request_advisories", lambda latitude, longitude: called.__setitem__("advisories", (latitude, longitude)))
    monkeypatch.setattr(api, "request_lightning", lambda latitude, longitude, radius_nm: called.__setitem__("lightning", (latitude, longitude, radius_nm)))
    monkeypatch.setattr(api, "request_hwo", lambda latitude, longitude: called.__setitem__("hwo", (latitude, longitude)))

    from modules.intel.weather.infra import ui_factories
    dialog = ui_factories.open_override_location()

    # Select manual and set coordinates
    dialog.manual_option.setChecked(True)
    dialog.lat_spin.setValue(39)
    dialog.lon_spin.setValue(-84)

    # Act: simulate Apply
    dialog.accept()

    # Assert
    assert called["advisories"] == (39.0, -84.0)
    assert called["lightning"] == (39.0, -84.0, 25.0)
    assert called["hwo"] == (39.0, -84.0)


def test_cached_advisories_restore_datetimes_and_forecast(monkeypatch, qapp):
    from modules.intel.weather.services import cache as cache_mod

    tmp_cache = _make_workspace_temp_dir("cached_payloads") / "weather_cache"
    tmp_cache.mkdir(parents=True, exist_ok=True)

    def fake_cache_path(name: str) -> Path:
        return tmp_cache / f"{name}.json"

    monkeypatch.setattr(cache_mod, "cache_path", fake_cache_path)

    cache_mod.write_cache(
        "advisories",
        {
            "0": {
                "event": "Wind Advisory",
                "severity": "Moderate",
                "start": "2026-06-26T10:00:00+00:00",
                "end": "2026-06-26T16:00:00+00:00",
                "headline": "Strong wind",
                "description": "Use caution",
            }
        },
    )
    cache_mod.write_cache(
        "forecast",
        {
            "39.0000,-84.0000": {
                "label": "ICP",
                "latitude": 39.0,
                "longitude": -84.0,
                "periods": [{"name": "Today", "temperature": 80, "detailed_text": "Sunny"}],
            }
        },
    )

    api = WeatherApiManager.instance()

    assert api._advisory_cache[0].start == datetime.fromisoformat("2026-06-26T10:00:00+00:00")
    assert api._advisory_cache[0].end == datetime.fromisoformat("2026-06-26T16:00:00+00:00")
    assert api._forecast_cache["39.0000,-84.0000"]["label"] == "ICP"


def test_current_forecast_window_requests_async_forecast(monkeypatch, qapp):
    api = WeatherApiManager.instance()
    requested = []

    monkeypatch.setattr(api, "request_forecast", lambda lat, lon, label="": requested.append((lat, lon, label)))
    monkeypatch.setattr(
        "modules.intel.weather.windows.current_forecast_window.get_icp_location",
        lambda: None,
    )

    from modules.intel.weather.windows.current_forecast_window import CurrentForecastWindow

    window = CurrentForecastWindow()
    window._locations = [{"label": "Test", "lat": 39.1, "lon": -84.5}]
    window._render_cards()
    window._refresh_all()

    assert requested == [(39.1, -84.5, "Test")]


def test_aviation_refresh_requests_service_for_station_list(monkeypatch, qapp):
    api = WeatherApiManager.instance()
    metar_calls = []
    taf_calls = []

    monkeypatch.setattr(api, "refresh_all", lambda: None)
    monkeypatch.setattr(api, "request_metar", lambda stations: metar_calls.append(list(stations)))
    monkeypatch.setattr(api, "request_taf", lambda stations: taf_calls.append(list(stations)))
    monkeypatch.setattr(api, "add_station_code", lambda code: [code])
    monkeypatch.setattr(api, "remove_station_code", lambda code: [])

    from modules.intel.weather.windows.aviation_weather_window import AviationWeatherWindow

    window = AviationWeatherWindow(["KJFK"])
    metar_calls.clear()
    taf_calls.clear()

    window._refresh_all_now()

    assert metar_calls == [["KJFK"]]
    assert taf_calls == [["KJFK"]]


def test_weather_summary_page_updates_forecast_and_station_actions(monkeypatch, qapp):
    api = WeatherApiManager.instance()
    added = []
    removed = []
    defaulted = []
    station_codes = ["KJFK", "KLGA"]

    monkeypatch.setattr(api, "station_codes", lambda: list(station_codes))
    monkeypatch.setattr(api, "weather_location", lambda: (39.0, -84.0))
    monkeypatch.setattr(api, "add_station_code", lambda code: added.append(code))
    monkeypatch.setattr(api, "remove_station_code", lambda code: removed.append(code))
    monkeypatch.setattr(api, "set_default_station", lambda code: defaulted.append(code))
    monkeypatch.setattr(api, "request_metar", lambda stations: None)
    monkeypatch.setattr(api, "request_taf", lambda stations: None)
    monkeypatch.setattr(
        "modules.intel.weather.pages.weather_summary_page.QInputDialog.getText",
        lambda *args, **kwargs: ("KCVG", True),
    )
    monkeypatch.setattr(
        "modules.intel.weather.pages.weather_summary_page.QInputDialog.getItem",
        lambda *args, **kwargs: ("KJFK", True),
    )

    from modules.intel.weather.pages.weather_summary_page import WeatherSummaryPage

    page = WeatherSummaryPage()
    page._add_station()
    page._remove_station()
    page._set_default_station()
    page.refresh_display(
        {
            "metar": {
                "KJFK": {
                    "station": "KJFK",
                    "raw_text": "METAR KJFK",
                    "decoded": {
                        "temp": "22C",
                        "dewp": "15C",
                        "wdir": "180",
                        "wspd": "12kt",
                        "visib": "10SM",
                        "altim": "A2992",
                        "clouds": [{"cover": "BKN", "base": "4000"}],
                    },
                }
            },
            "advisories": [],
            "forecast": {
                "39.0000,-84.0000": {
                    "label": "ICP",
                    "periods": [
                        {"name": "Today", "temperature": 81, "detailed_text": "Sunny"},
                        {"name": "Tonight", "temperature": 65, "detailed_text": "Clear"},
                    ],
                }
            },
            "hwo": {
                "office": "NWS Wilmington",
                "time": "2026-06-26T08:00:00Z",
                "text": "Hazardous weather expected today.\nAdditional detail follows.",
            },
        }
    )

    assert added == ["KCVG"]
    assert removed == ["KJFK"]
    assert defaulted == ["KJFK"]
    assert page.forecast_labels[0].text().startswith("Today: 81")
    assert "Temp: 22C" in page.current_conditions_label.text()
    assert "Hazardous weather expected today." in page.hwo_excerpt.text()
    assert not page.auto_log_checkbox.isEnabled()


def test_export_briefing_dialog_uses_live_weather_payload(qapp):
    from modules.intel.weather.windows.export_briefing_dialog import ExportBriefingDialog

    dialog = ExportBriefingDialog()
    dialog._handle_data(
        {
            "metar": {
                "KCVG": {
                    "station": "KCVG",
                    "raw_text": "KCVG 261651Z 21012KT 10SM SCT040 29/21 A2992",
                }
            },
            "forecast": {
                "39.1031,-84.5120": {
                    "label": "ICP",
                    "periods": [
                        {"name": "Today", "temperature": 84, "detailed_text": "Hot and humid"},
                        {"name": "Tonight", "temperature": 68, "detailed_text": "Chance of storms"},
                    ],
                }
            },
            "advisories": [{"event": "Heat Advisory"}],
            "hwo": {"text": "Hazardous weather expected today.\nAdditional detail."},
        }
    )

    preview = dialog.preview.toPlainText()
    assert "Current weather: KCVG" in preview
    assert "Next 12h: ICP: Today 84F Hot and humid" in preview
    assert "Alerts: Heat Advisory" in preview
    assert "HWO: Hazardous weather expected today." in preview


def test_request_hwo_publishes_payload(monkeypatch, qapp):
    api = WeatherApiManager.instance()
    updates = []

    monkeypatch.setattr(
        api,
        "_run_async",
        lambda func, callback, context: callback(
            {
                "office": "ILN",
                "time": "2026-06-26T08:00:00Z",
                "text": "Hazardous Weather Outlook text",
                "url": "https://api.weather.gov/products/123",
            }
        ),
    )
    api.dataUpdated.connect(lambda payload: updates.append(payload))

    api.request_hwo(39.0, -84.0)

    assert updates
    assert updates[-1]["hwo"]["office"] == "ILN"


def test_location_preset_accessors_round_trip(qapp):
    api = WeatherApiManager.instance()
    api.save_location_presets(
        [
            {
                "id": "facility:fac-1",
                "label": "Staging Alpha",
                "latitude": 39.1,
                "longitude": -84.5,
            }
        ],
        active_preset="facility:fac-1",
    )

    assert api.active_location_preset() == "facility:fac-1"
    assert api.location_presets()[0]["label"] == "Staging Alpha"
    assert updates[-1]["hwo"]["text"] == "Hazardous Weather Outlook text"
