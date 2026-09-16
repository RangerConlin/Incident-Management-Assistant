import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.intel.weather.models.location import WeatherLocation
from modules.intel.weather.services.summary import build_weather_form_payload
from modules.intel.weather.services import weather_manager as wm_module


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _pump(condition, timeout_s: float = 5.0) -> bool:
    app = _app()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


def _location_dict(loc: WeatherLocation) -> dict:
    return {
        "location_id": loc.location_id,
        "label": loc.label,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "icao_codes": loc.icao_codes,
        "is_default": loc.is_default,
        "source": loc.source,
        "source_ref_id": loc.source_ref_id,
    }


def _make_manager(monkeypatch, locations):
    monkeypatch.setattr(
        wm_module.client,
        "get_config",
        lambda incident_id: {
            "polling_minutes": 10,
            "thresholds": {},
            "locations": [_location_dict(loc) for loc in locations],
        },
    )
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})
    manager = wm_module.WeatherManager("TEST-WM-1")
    return manager


def test_provider_exception_emits_fetch_error_not_a_silent_swallow(monkeypatch):
    _app()
    location = WeatherLocation(location_id="loc-1", label="Test", icao_codes=["KTST"])
    manager = _make_manager(monkeypatch, [location])

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(manager._metar_provider, "fetch_metar", _raise)
    monkeypatch.setattr(manager._taf_provider, "fetch_taf", lambda codes: [])

    errors = []
    manager.fetchError.connect(lambda loc_id, provider, msg: errors.append((loc_id, provider, msg)))

    finished = []
    manager.pollFinished.connect(lambda: finished.append(True))

    manager.refresh_all()
    assert _pump(lambda: bool(finished)), "poll never finished — a callback must have been swallowed"

    assert any(provider == "metar" and "simulated provider failure" in msg for _loc, provider, msg in errors), (
        "provider exception must surface via fetchError, never a bare except: pass"
    )


def test_successful_metar_poll_updates_snapshot_and_records_history(monkeypatch):
    _app()
    location = WeatherLocation(location_id="loc-2", label="Test2", icao_codes=["KTST"])
    manager = _make_manager(monkeypatch, [location])

    from modules.intel.weather.models.readings import MetarReading

    reading = MetarReading(station="KTST", raw_text="KTST RAW", decoded={"temp": 20, "dewp": 15, "wspd": 10})
    monkeypatch.setattr(manager._metar_provider, "fetch_metar", lambda codes: [reading])
    monkeypatch.setattr(manager._taf_provider, "fetch_taf", lambda codes: [])

    recorded = []
    monkeypatch.setattr(wm_module.history_recorder, "record", lambda incident_id, loc_id, normalized: recorded.append(normalized))

    finished = []
    manager.pollFinished.connect(lambda: finished.append(True))
    manager.refresh_all()
    assert _pump(lambda: bool(finished))

    snap = manager.snapshot("loc-2")
    assert snap is not None
    assert snap.metar is not None
    assert snap.metar.station == "KTST"
    assert recorded, "a successful METAR fetch must record a history sample"
    assert any(sample.get("temperature_f") is not None for sample in recorded)


def test_point_location_fetches_nws_observation_for_current_conditions(monkeypatch):
    _app()
    location = WeatherLocation(location_id="loc-point", label="ICP", latitude=39.0, longitude=-77.0)
    manager = _make_manager(monkeypatch, [location])

    from modules.intel.weather.models.readings import MetarReading

    observation = MetarReading(
        station="KDCA",
        decoded={
            "temp": 22.0,
            "wspd": 6.0,
            "visib": 10.0,
            "altim": 1015.0,
            "relative_humidity_pct": 55.0,
        },
    )
    monkeypatch.setattr(manager._observation_provider, "fetch_current_observation", lambda lat, lon: observation)
    monkeypatch.setattr(manager._forecast_provider, "fetch_forecast", lambda lat, lon: [])
    monkeypatch.setattr(manager._advisory_provider, "fetch_advisories", lambda lat, lon: [])
    monkeypatch.setattr(manager._hwo_provider, "fetch_hwo", lambda lat, lon: {})

    recorded = []
    monkeypatch.setattr(
        wm_module.history_recorder,
        "record",
        lambda incident_id, loc_id, normalized: recorded.append(normalized),
    )

    finished = []
    manager.pollFinished.connect(lambda: finished.append(True))
    manager.refresh_all()
    assert _pump(lambda: bool(finished))

    reading = manager.normalized_current("loc-point")
    assert round(reading["temperature_f"]) == 72
    assert reading["relative_humidity_pct"] == 55.0
    assert any(round(sample.get("temperature_f", 0)) == 72 for sample in recorded)


def test_nws_observation_payload_converts_to_current_reading():
    from modules.intel.weather.data_providers.noaa_observations import _parse_observation

    observation = _parse_observation(
        "KDCA",
        {
            "properties": {
                "timestamp": "2026-09-14T12:00:00+00:00",
                "temperature": {"value": 20.0},
                "dewpoint": {"value": 10.0},
                "windSpeed": {"value": 5.0},
                "windGust": {"value": 8.0},
                "windDirection": {"value": 270.0},
                "visibility": {"value": 16093.44},
                "barometricPressure": {"value": 101500.0},
                "relativeHumidity": {"value": 52.0},
                "cloudLayers": [{"amount": "BKN", "base": {"value": 914.4}}],
            }
        },
    )

    reading = wm_module._normalize_metar_reading(observation)

    assert observation is not None
    assert round(reading["temperature_f"]) == 68
    assert round(reading["wind_speed_kt"]) == 10
    assert round(reading["visibility_sm"]) == 10
    assert reading["barometric_pressure_hpa"] == 1015.0
    assert round(reading["ceiling_ft"]) == 3000
    assert reading["relative_humidity_pct"] == 52.0


def test_configure_polling_enforces_one_minute_floor(monkeypatch):
    _app()
    manager = _make_manager(monkeypatch, [])
    manager.configure_polling(0)
    assert manager.polling_minutes() == 1


def test_weather_form_payload_does_not_emit_address_without_readings(monkeypatch):
    location = WeatherLocation(location_id="loc-address", label="4054 HORTON RD")
    manager = _make_manager(monkeypatch, [location])

    payload = build_weather_form_payload(manager)

    assert payload["current"]["local"] == ""
    assert payload["conditions"] == ""
    assert payload["summary"] == ""
