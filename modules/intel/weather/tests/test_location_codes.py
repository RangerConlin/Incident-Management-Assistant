import os

import pytest

from PySide6.QtWidgets import QApplication

from modules.intel.weather.services.api_link import WeatherApiManager
from modules.intel.weather.services.location_codes import NwsLocationCodeService


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_singletons():
    WeatherApiManager._instance = None
    NwsLocationCodeService._instance = None
    yield
    WeatherApiManager._instance = None
    NwsLocationCodeService._instance = None


def _resolved_entry() -> dict:
    return {
        "office": "ILN",
        "grid_id": "ILN",
        "grid_x": 40,
        "grid_y": 42,
        "forecast_url": "https://api.weather.gov/gridpoints/ILN/40,42/forecast",
        "forecast_hourly_url": "https://api.weather.gov/gridpoints/ILN/40,42/forecast/hourly",
        "time_zone": "America/New_York",
        "stations": ["KLUK", "KCVG"],
    }


def test_resolves_facility_locations_and_exposes_lookups(monkeypatch, qapp, tmp_path):
    from modules.intel.weather.services import cache as cache_mod

    monkeypatch.setattr(cache_mod, "cache_path", lambda name: tmp_path / f"{name}.json")

    service = NwsLocationCodeService.instance()
    monkeypatch.setattr(
        service, "_gather_locations", lambda: [("Staging Alpha", 39.1031, -84.512)]
    )
    monkeypatch.setattr(service, "_run_async", lambda func, callback: callback(func()))
    monkeypatch.setattr(service, "_save_to_server", lambda: None)
    monkeypatch.setattr(service._provider, "resolve", lambda lat, lon: _resolved_entry())

    updates = []
    service.codesUpdated.connect(lambda codes: updates.append(codes))

    service.refresh_now()

    assert updates, "Expected codesUpdated signal to fire"
    entry = service.codes_for(39.1031, -84.512)
    assert entry["office"] == "ILN"
    assert entry["label"] == "Staging Alpha"
    assert service.office_for(39.1031, -84.512) == "ILN"
    assert service.forecast_url_for(39.1031, -84.512).endswith("/forecast")
    assert service.stations_for(39.1031, -84.512) == ["KLUK", "KCVG"]

    # Local cache should hold the resolved entry for offline restarts
    cached = cache_mod.read_cache("nws_location_codes")
    assert cached["39.1031,-84.5120"]["office"] == "ILN"


def test_resolved_locations_are_not_refetched(monkeypatch, qapp, tmp_path):
    from modules.intel.weather.services import cache as cache_mod

    monkeypatch.setattr(cache_mod, "cache_path", lambda name: tmp_path / f"{name}.json")

    service = NwsLocationCodeService.instance()
    monkeypatch.setattr(
        service, "_gather_locations", lambda: [("Staging Alpha", 39.1031, -84.512)]
    )
    monkeypatch.setattr(service, "_run_async", lambda func, callback: callback(func()))
    monkeypatch.setattr(service, "_save_to_server", lambda: None)

    calls = []

    def fake_resolve(lat, lon):
        calls.append((lat, lon))
        return _resolved_entry()

    monkeypatch.setattr(service._provider, "resolve", fake_resolve)

    service.refresh_now()
    service.refresh_now()

    assert len(calls) == 1, "Already-resolved coordinates must not be re-fetched"


def test_failed_resolution_is_retried_on_next_pass(monkeypatch, qapp, tmp_path):
    from modules.intel.weather.services import cache as cache_mod

    monkeypatch.setattr(cache_mod, "cache_path", lambda name: tmp_path / f"{name}.json")

    service = NwsLocationCodeService.instance()
    monkeypatch.setattr(
        service, "_gather_locations", lambda: [("Staging Alpha", 39.1031, -84.512)]
    )
    monkeypatch.setattr(service, "_run_async", lambda func, callback: callback(func()))
    monkeypatch.setattr(service, "_save_to_server", lambda: None)

    results = [None, _resolved_entry()]
    monkeypatch.setattr(service._provider, "resolve", lambda lat, lon: results.pop(0))

    service.refresh_now()
    assert service.codes_for(39.1031, -84.512) is None

    service.refresh_now()
    assert service.codes_for(39.1031, -84.512)["office"] == "ILN"


def test_request_hwo_and_forecast_use_resolved_codes(monkeypatch, qapp):
    api = WeatherApiManager.instance()
    service = NwsLocationCodeService.instance()
    key = service.location_key(39.0, -84.0)
    service._codes[key] = {
        "office": "ILN",
        "forecast_url": "https://api.weather.gov/gridpoints/ILN/40,42/forecast",
    }

    captured = {}

    def fake_fetch_hwo(lat, lon, office=None):
        captured["office"] = office
        return None

    def fake_fetch_forecast(lat, lon, forecast_url=None):
        captured["forecast_url"] = forecast_url
        return []

    monkeypatch.setattr(api._hwo_provider, "fetch_hwo", fake_fetch_hwo)
    monkeypatch.setattr(api._forecast_provider, "fetch_forecast", fake_fetch_forecast)
    monkeypatch.setattr(api, "_run_async", lambda func, callback, context: callback(func()))
    monkeypatch.setattr(api, "_save_settings_to_server", lambda *a, **k: None)

    api.request_hwo(39.0, -84.0)
    api.request_forecast(39.0, -84.0, "ICP")

    assert captured["office"] == "ILN"
    assert captured["forecast_url"].endswith("/forecast")
