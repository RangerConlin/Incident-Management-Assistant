import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.intel.weather.models.location import WeatherLocation
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
    assert recorded[0]["temperature_f"] is not None


def test_configure_polling_enforces_one_minute_floor(monkeypatch):
    _app()
    manager = _make_manager(monkeypatch, [])
    manager.configure_polling(0)
    assert manager.polling_minutes() == 1
