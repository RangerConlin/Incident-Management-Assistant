import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.intel.weather.services import weather_manager as wm_module


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_briefing_pdf_nonempty_even_with_no_stations(monkeypatch):
    _app()
    monkeypatch.setattr(wm_module.client, "get_config", lambda incident_id: {"polling_minutes": 10, "thresholds": {}, "locations": []})
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})

    manager = wm_module.get_weather_manager("TEST-PDF-1")

    from modules.intel.weather.export.briefing_pdf import build_weather_briefing_pdf

    data = build_weather_briefing_pdf(incident_name="Test Incident", manager=manager)
    assert data.startswith(b"%PDF")
    assert len(data) > 100


def test_briefing_pdf_with_no_active_alerts(monkeypatch):
    _app()
    from modules.intel.weather.models.location import WeatherLocation

    location = WeatherLocation(location_id="loc-1", label="ICP", icao_codes=["KTST"])
    monkeypatch.setattr(
        wm_module.client,
        "get_config",
        lambda incident_id: {
            "polling_minutes": 10,
            "thresholds": {},
            "locations": [
                {
                    "location_id": location.location_id,
                    "label": location.label,
                    "latitude": None,
                    "longitude": None,
                    "icao_codes": location.icao_codes,
                    "is_default": False,
                    "source": "manual",
                    "source_ref_id": None,
                }
            ],
        },
    )
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})

    manager = wm_module.get_weather_manager("TEST-PDF-2")

    from modules.intel.weather.export.briefing_pdf import build_weather_briefing_pdf

    data = build_weather_briefing_pdf(incident_name=None, manager=manager)
    assert data.startswith(b"%PDF")
