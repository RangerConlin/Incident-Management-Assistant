import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient
from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_incident_db


def test_weather_router():
    incident_id = "TESTWEATHER1"
    db = get_incident_db(incident_id)
    db["weather_data"].delete_many({})

    app = create_app()
    with TestClient(app) as client:
        # GET: verify default config
        res = client.get(f"/api/incidents/{incident_id}/weather")
        assert res.status_code == 200
        data = res.json()
        assert data["latitude"] == 39.8283
        assert data["longitude"] == -98.5795

        # WebSocket: listen for broadcasts
        with client.websocket_connect(f"/api/incidents/{incident_id}/ws") as ws:
            # POST: update settings
            post_payload = {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "radius_nm": 15.0,
                "icao_codes": ["KJFK", "KLGA"],
                "polling_minutes": 5,
                "active_location_preset": "facility:fac-1",
                "location_presets": [
                    {
                        "id": "facility:fac-1",
                        "label": "ICP - County Fairgrounds",
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                    }
                ],
                "weather_payload": {"temp": "sunny"}
            }
            res_post = client.post(f"/api/incidents/{incident_id}/weather", json=post_payload)
            assert res_post.status_code == 200
            updated_data = res_post.json()
            assert updated_data["latitude"] == 40.7128
            assert updated_data["radius_nm"] == 15.0
            assert updated_data["active_location_preset"] == "facility:fac-1"
            assert updated_data["location_presets"][0]["id"] == "facility:fac-1"

            # WebSocket: verify the change event is broadcasted
            event = ws.receive_json()
            assert event["collection"] == "weather_data"
            # It's an insert since there was no doc before
            assert event["op"] == "created"
            assert event["doc"]["latitude"] == 40.7128

        # GET: verify final state
        res_get = client.get(f"/api/incidents/{incident_id}/weather")
        assert res_get.status_code == 200
        final_data = res_get.json()
        assert final_data["latitude"] == 40.7128
        assert final_data["active_location_preset"] == "facility:fac-1"
        assert final_data["weather_payload"] == {"temp": "sunny"}

    db["weather_data"].delete_many({})
