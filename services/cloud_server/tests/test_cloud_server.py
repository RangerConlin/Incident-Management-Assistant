from __future__ import annotations

from fastapi.testclient import TestClient


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SARAPP_CONNECT_CODE", "TEST-1234")
    monkeypatch.setenv("CLOUD_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("CLOUD_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CLOUD_SESSION_SECRET", "test-session-secret")
    monkeypatch.delenv("SARAPP_CLOUD_ROUTER_URL", raising=False)
    monkeypatch.delenv("SARAPP_CLOUD_ROUTER_TOKEN", raising=False)
    from services.cloud_server.main import create_cloud_app

    return TestClient(create_cloud_app(), follow_redirects=False)


def _login(client: TestClient) -> None:
    from services.cloud_server.config import load_settings
    from services.cloud_server.dashboard import _SESSION_COOKIE, _session_value

    settings = load_settings()
    client.cookies.set(_SESSION_COOKIE, _session_value(settings, settings.admin_username))


def test_connect_code_prefix_serves_normal_health(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/r/TEST-1234/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["server"]["connect_code"] == "TEST-1234"


def test_unprefixed_router_forwarded_health_is_allowed(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["server"]["connect_code"] == "TEST-1234"


def test_unprefixed_router_forwarded_api_is_allowed(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post("/api/diagnostics/echo", json={"hello": "world"})

    assert response.status_code == 200
    assert response.json()["received"]["hello"] == "world"


def test_wrong_connect_code_is_not_routed(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/r/WRONG-0000/health")

    assert response.status_code == 404


def test_dashboard_requires_login(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/r/TEST-1234/dashboard")

    assert response.status_code == 303
    assert response.headers["location"] == "/r/TEST-1234/dashboard/login"


def test_unprefixed_router_forwarded_dashboard_requires_login(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/dashboard")

    assert response.status_code == 303
    assert response.headers["location"] == "/r/TEST-1234/dashboard/login"


def test_dashboard_shows_central_catalog_sync_status(monkeypatch) -> None:
    monkeypatch.setattr("services.cloud_server.dashboard.ping", lambda: True)
    monkeypatch.setattr("services.cloud_server.dashboard._active_connections", lambda: [])
    monkeypatch.setattr(
        "services.cloud_server.dashboard._sync_status",
        lambda: {
            "enabled": True,
            "central_master_url": "https://central.example/central-master",
            "pending_count": 2,
            "last_pulled": {"personnel": "2026-10-12T12:00:00+00:00", "vehicles": None},
        },
    )
    client = _client(monkeypatch)
    _login(client)

    response = client.get("/r/TEST-1234/dashboard")

    assert response.status_code == 200
    assert "Central Catalog Sync" in response.text
    assert "Enabled — 2 pending" in response.text
    assert "https://central.example/central-master" in response.text
    assert "personnel" in response.text
    assert "vehicles" in response.text
    assert "never" in response.text


def test_dashboard_status_includes_central_catalog_sync(monkeypatch) -> None:
    sync_status = {
        "enabled": True,
        "central_master_url": "https://central.example/central-master",
        "pending_count": 0,
        "last_pulled": {"personnel": "2026-10-12T12:00:00+00:00"},
    }
    monkeypatch.setattr("services.cloud_server.dashboard.ping", lambda: True)
    monkeypatch.setattr("services.cloud_server.dashboard._active_connections", lambda: [])
    monkeypatch.setattr("services.cloud_server.dashboard._sync_status", lambda: sync_status)
    client = _client(monkeypatch)
    _login(client)

    response = client.get("/r/TEST-1234/api/cloud/dashboard/status")

    assert response.status_code == 200
    assert response.json()["central_catalog_sync"] == sync_status

