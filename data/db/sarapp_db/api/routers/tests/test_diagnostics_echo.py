import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os
os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app


def test_echo_post_returns_body_and_server_time():
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/diagnostics/echo", json={"hello": "world"})
        assert response.status_code == 200
        body = response.json()
        assert body["received"] == {"hello": "world"}
        assert "server_time_utc" in body


def test_echo_get_works_for_browser_round_trip():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/diagnostics/echo")
        assert response.status_code == 200
        body = response.json()
        assert body["received"] is None
        assert "server_time_utc" in body


def test_echo_post_with_empty_body_does_not_error():
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/diagnostics/echo")
        assert response.status_code == 200
        assert response.json()["received"] is None
