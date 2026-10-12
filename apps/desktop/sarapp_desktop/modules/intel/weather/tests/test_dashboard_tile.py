import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.intel.weather.models.location import WeatherLocation
from modules.intel.weather.services import weather_manager as wm_module
from modules.intel.weather.ui import dashboard_tile as tile_module


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


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


def test_tile_with_no_active_incident_shows_no_incident_not_fake_data(monkeypatch):
    _app()
    monkeypatch.setattr(tile_module, "get_active_incident_id", lambda: None)
    tile = tile_module.WeatherDashboardTile()
    assert tile._temp_label.text() == "—"
    assert "No active incident" in tile._cond_label.text()


def test_tile_with_no_stations_configured_shows_placeholder_not_fake_reading(monkeypatch):
    _app()
    monkeypatch.setattr(wm_module.client, "get_config", lambda incident_id: {"polling_minutes": 10, "thresholds": {}, "locations": []})
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})
    monkeypatch.setattr(tile_module, "get_active_incident_id", lambda: "TEST-TILE-1")

    tile = tile_module.WeatherDashboardTile()
    assert tile._temp_label.text() == "—"
    assert "No station configured" in tile._cond_label.text()
    assert tile._severity_badge.isVisible() is False


def test_tile_renders_current_temperature_and_severity_badge(monkeypatch):
    _app()
    location = WeatherLocation(location_id="loc-1", label="ICP", icao_codes=["KTST"], is_default=True)
    monkeypatch.setattr(
        wm_module.client,
        "get_config",
        lambda incident_id: {"polling_minutes": 10, "thresholds": {}, "locations": [_location_dict(location)]},
    )
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})
    monkeypatch.setattr(tile_module, "get_active_incident_id", lambda: "TEST-TILE-2")

    manager = wm_module.get_weather_manager("TEST-TILE-2")

    from modules.intel.weather.models.readings import MetarReading
    from modules.intel.weather.models.advisory import Advisory

    reading = MetarReading(station="KTST", decoded={"temp": 20, "dewp": 10, "wspd": 5})
    snap = manager._snapshots.setdefault("loc-1", wm_module.WeatherSnapshot(location_id="loc-1"))
    snap.metar = reading
    snap.advisories = [Advisory(event="Severe Thunderstorm Warning", severity="Severe", start=None, end=None, headline="h", description="d")]

    tile = tile_module.WeatherDashboardTile()
    tile.show()
    tile.refresh()

    assert "68" in tile._temp_label.text() or "°F" in tile._temp_label.text()
    assert tile._severity_badge.isVisible() is True
    assert tile._severity_badge.text() == "Severe"
