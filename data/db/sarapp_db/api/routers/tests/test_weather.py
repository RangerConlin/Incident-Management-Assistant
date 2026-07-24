import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient
from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


def test_weather_config_defaults_and_thresholds_update():
    incident_id = "TESTWEATHER1"
    db = get_incident_db(incident_id)
    db["weather_config"].delete_many({})

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{incident_id}/weather/config")
        assert res.status_code == 200
        data = res.json()
        assert data["locations"] == []
        assert data["thresholds"]["ground"]["wind_gust_marginal_mph"] == 20.0
        assert data["thresholds"]["aviation"]["crosswind_nogo_kt"] == 25.0

        res_put = client.put(
            f"/api/incidents/{incident_id}/weather/config",
            json={"polling_minutes": 15, "thresholds": {"ground": {"wind_gust_marginal_mph": 25.0}}},
        )
        assert res_put.status_code == 200
        updated = res_put.json()
        assert updated["polling_minutes"] == 15
        assert updated["thresholds"]["ground"]["wind_gust_marginal_mph"] == 25.0
        # unspecified ground fields fall back to the model's own defaults, not silently dropped
        assert updated["thresholds"]["ground"]["visibility_nogo_mi"] == 1.0

    db["weather_config"].delete_many({})


def test_weather_locations_crud_and_auto_population_protection():
    incident_id = "TESTWEATHER2"
    db = get_incident_db(incident_id)
    db["weather_config"].delete_many({})

    app = create_app()
    with TestClient(app) as client:
        res_add = client.post(
            f"/api/incidents/{incident_id}/weather/locations",
            json={"label": "ICP", "latitude": 39.1, "longitude": -84.5, "icao_codes": ["KLUK"], "is_default": True},
        )
        assert res_add.status_code == 200
        config = res_add.json()
        assert len(config["locations"]) == 1
        location_id = config["locations"][0]["location_id"]
        assert config["locations"][0]["source"] == "manual"
        assert config["locations"][0]["is_default"] is True

        res_auto = client.post(
            f"/api/incidents/{incident_id}/weather/locations",
            json={
                "label": "Helibase 1",
                "source": "facility",
                "source_ref_id": "facility:abc",
            },
        )
        assert res_auto.status_code == 200
        auto_location_id = next(
            loc["location_id"] for loc in res_auto.json()["locations"] if loc["source"] == "facility"
        )

        # Auto-populated stations cannot be deleted through this endpoint
        res_del_auto = client.delete(f"/api/incidents/{incident_id}/weather/locations/{auto_location_id}")
        assert res_del_auto.status_code == 409

        # Manual stations can be deleted
        res_del = client.delete(f"/api/incidents/{incident_id}/weather/locations/{location_id}")
        assert res_del.status_code == 200
        assert not any(loc["location_id"] == location_id for loc in res_del.json()["locations"])

    db["weather_config"].delete_many({})


def test_weather_history_windowed_query():
    incident_id = "TESTWEATHER3"
    db = get_incident_db(incident_id)
    db["weather_history"].delete_many({})

    app = create_app()
    with TestClient(app) as client:
        for i in range(3):
            res = client.post(
                f"/api/incidents/{incident_id}/weather/history",
                json={
                    "location_id": "loc-1",
                    "recorded_at": f"2026-07-2{i}T00:00:00+00:00",
                    "temperature_f": 70.0 + i,
                },
            )
            assert res.status_code == 200

        res_get = client.get(
            f"/api/incidents/{incident_id}/weather/history", params={"location_id": "loc-1"}
        )
        assert res_get.status_code == 200
        samples = res_get.json()["samples"]
        assert len(samples) == 3
        assert samples[0]["temperature_f"] == 70.0

        res_windowed = client.get(
            f"/api/incidents/{incident_id}/weather/history",
            params={"location_id": "loc-1", "since": "2026-07-21T00:00:00+00:00"},
        )
        assert len(res_windowed.json()["samples"]) == 2

    db["weather_history"].delete_many({})


def test_weather_location_codes_roundtrip():
    incident_id = "TESTWEATHER4"
    db = get_incident_db(incident_id)
    db["weather_data"].delete_many({})

    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/api/incidents/{incident_id}/weather/location-codes")
        assert res.status_code == 200
        assert res.json()["codes"] == []

        payload = {
            "codes": [
                {
                    "label": "ICP",
                    "latitude": 39.1031,
                    "longitude": -84.512,
                    "office": "ILN",
                    "grid_id": "ILN",
                    "grid_x": 40,
                    "grid_y": 42,
                    "forecast_url": "https://api.weather.gov/gridpoints/ILN/40,42/forecast",
                    "stations": ["KLUK", "KCVG"],
                }
            ]
        }
        res_post = client.post(
            f"/api/incidents/{incident_id}/weather/location-codes", json=payload
        )
        assert res_post.status_code == 200
        assert res_post.json()["codes"][0]["office"] == "ILN"

        payload["codes"][0]["stations"] = ["KLUK"]
        res_post2 = client.post(
            f"/api/incidents/{incident_id}/weather/location-codes", json=payload
        )
        assert res_post2.status_code == 200

        res_get = client.get(f"/api/incidents/{incident_id}/weather/location-codes")
        codes = res_get.json()["codes"]
        assert len(codes) == 1
        assert codes[0]["stations"] == ["KLUK"]
        assert db["weather_data"].count_documents({"key": "location_codes"}) == 1

    db["weather_data"].delete_many({})
