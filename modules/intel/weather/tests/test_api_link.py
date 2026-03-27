import os
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


def test_request_methods_run_without_network(monkeypatch, tmp_path: Path, qapp):
    api = WeatherApiManager.instance()

    # Force cache dir to a temp location by monkeypatching cache helpers
    from modules.intel.weather.services import cache as cache_mod

    tmp_cache = tmp_path / "weather_cache"
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
    called = {"advisories": None, "lightning": None}
    api = WeatherApiManager.instance()

    monkeypatch.setattr(api, "request_advisories", lambda latitude, longitude: called.__setitem__("advisories", (latitude, longitude)))
    monkeypatch.setattr(api, "request_lightning", lambda latitude, longitude, radius_nm: called.__setitem__("lightning", (latitude, longitude, radius_nm)))

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

