from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from modules.safety.weather.manager import WeatherSafetyManager
from modules.safety import services as safety_services
from modules.intel.utils import db_access as intel_db
from modules.intel.models import EnvSnapshot
from sqlmodel import select


class FakeClient:
    def __init__(self, payloads: Dict[str, Dict[str, Any]]):
        self.payloads = payloads

    def get_json(self, url: str, params=None):
        # naive match by prefix
        for key, value in self.payloads.items():
            if url.startswith(key):
                return json.loads(json.dumps(value))
        raise RuntimeError(f"no payload for {url}")


def _nws_points(lat: float, lon: float) -> Dict[str, Any]:
    return {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/DTX/1,1/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/DTX/1,1/forecast/hourly",
            "observationStations": "https://api.weather.gov/stations",
            "cwa": "DTX",
        }
    }


def _nws_current() -> Dict[str, Any]:
    return {"properties": {"temperature": {"value": 20}, "relativeHumidity": {"value": 50}}}


def _nws_daily() -> Dict[str, Any]:
    return {"properties": {"periods": [{"name": "Today", "temperature": 70, "temperatureUnit": "F", "shortForecast": "Sunny"}]}}


def _nws_hourly() -> Dict[str, Any]:
    return {"properties": {"periods": []}}


def _nws_alerts(severity: str = "Severe") -> Dict[str, Any]:
    return {
        "features": [
            {
                "id": "ALERT1",
                "properties": {
                    "severity": severity,
                    "event": "Severe Thunderstorm Warning",
                    "headline": "Severe Thunderstorm Warning for Test County",
                    "areaDesc": "Test County",
                    "effective": "2025-09-29T00:00:00+00:00",
                    "description": "Large hail and damaging winds possible.",
                },
            }
        ]
    }


def _nws_hwo() -> Dict[str, Any]:
    return {"productText": "Hazardous Weather Outlook text."}


def test_poll_once_creates_snapshot_and_report(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    # set active incident
    import utils.incident_context as ic

    ic.set_active_incident("UNITTEST-WS-1")

    # prepare fake client payloads
    client = FakeClient(
        payloads={
            "https://api.weather.gov/points/": _nws_points(0, 0),
            "https://api.weather.gov/gridpoints/DTX/1,1/forecast/hourly": _nws_hourly(),
            "https://api.weather.gov/gridpoints/DTX/1,1/forecast": _nws_daily(),
            "https://api.weather.gov/stations": {"features": [{"id": "https://api.weather.gov/stations/KXYZ"}]},
            "https://api.weather.gov/stations/KXYZ/observations/latest": _nws_current(),
            "https://api.weather.gov/alerts/active": _nws_alerts(),
            "https://api.weather.gov/products/types/HWO": {},
            "https://api.weather.gov/products": {"@graph": []},
        }
    )

    mgr = WeatherSafetyManager(client=client)  # type: ignore[arg-type]
    # Provide an explicit location override for repeatability
    mgr.set_location_override(42.1, -83.2)

    data = mgr.poll_once()
    assert data.get("nws") is not None

    # EnvSnapshot created
    intel_db.ensure_incident_schema()
    with intel_db.incident_session() as session:
        snaps = session.exec(select(EnvSnapshot)).all()
        assert len(snaps) >= 1

    # Safety report created via auto-log
    reports = safety_services.list_safety_reports("UNITTEST-WS-1")
    assert any("[AUTO]" in (r.notes or "") for r in reports)

