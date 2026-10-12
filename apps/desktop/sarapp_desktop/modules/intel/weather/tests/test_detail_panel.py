import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.intel.weather.services import weather_manager as wm_module


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_detail_panel_constructs_with_five_tabs_and_empty_locations(monkeypatch):
    _app()
    monkeypatch.setattr(wm_module.client, "get_config", lambda incident_id: {"polling_minutes": 10, "thresholds": {}, "locations": []})
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})
    monkeypatch.setattr(wm_module.client, "list_weather_alerts", lambda incident_id: [])

    from modules.intel.weather.ui.detail_panel import WeatherDetailPanel

    panel = WeatherDetailPanel("TEST-DETAIL-1")
    assert panel._tabs.count() == 5
    tab_labels = [panel._tabs.tabText(i) for i in range(5)]
    assert "Aviation" in tab_labels
    assert "History" in tab_labels
    assert "Stations" in tab_labels

    panel.open_tab("stations")
    assert panel._tabs.currentIndex() == 4

    # Should not raise even with no stations configured
    panel.open_tab("alerts")
    assert panel._tabs.currentIndex() == 2


def test_refresh_button_disables_during_poll_and_reenables_after(monkeypatch):
    _app()
    monkeypatch.setattr(wm_module.client, "get_config", lambda incident_id: {"polling_minutes": 10, "thresholds": {}, "locations": []})
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})
    monkeypatch.setattr(wm_module.client, "list_weather_alerts", lambda incident_id: [])

    from modules.intel.weather.ui.detail_panel import WeatherDetailPanel

    panel = WeatherDetailPanel("TEST-DETAIL-2")
    assert panel._refresh_btn.isEnabled()

    panel._manager.pollStarted.emit()
    assert not panel._refresh_btn.isEnabled()
    assert "Refreshing" in panel._refresh_btn.text()

    panel._manager.pollFinished.emit()
    assert panel._refresh_btn.isEnabled()
    assert panel._refresh_btn.text() == "⟳ Refresh"


def test_refresh_button_click_triggers_a_poll_cycle(monkeypatch):
    _app()
    # A location with no ICAO code and no lat/lon has no async jobs, so
    # refresh_all() runs its pollStarted/pollFinished cycle synchronously —
    # enough to prove the button is wired to the manager without needing to
    # mock network providers.
    location = {
        "location_id": "loc-1",
        "label": "Bare Location",
        "latitude": None,
        "longitude": None,
        "icao_codes": [],
        "is_default": True,
        "source": "manual",
    }
    monkeypatch.setattr(
        wm_module.client, "get_config", lambda incident_id: {"polling_minutes": 10, "thresholds": {}, "locations": [location]}
    )
    monkeypatch.setattr(wm_module.client, "list_airport_facilities", lambda incident_id: [])
    monkeypatch.setattr(wm_module.client, "get_initial_response_aircraft_info", lambda incident_id: {})
    monkeypatch.setattr(wm_module.client, "list_weather_alerts", lambda incident_id: [])

    from modules.intel.weather.ui.detail_panel import WeatherDetailPanel

    panel = WeatherDetailPanel("TEST-DETAIL-3")

    events = []
    panel._manager.pollStarted.connect(lambda: events.append("started"))
    panel._manager.pollFinished.connect(lambda: events.append("finished"))
    panel._refresh_btn.click()
    assert events == ["started", "finished"]
