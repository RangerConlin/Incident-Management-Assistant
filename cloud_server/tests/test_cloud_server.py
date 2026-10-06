from __future__ import annotations

from fastapi.testclient import TestClient


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SARAPP_CONNECT_CODE", "TEST-1234")
    monkeypatch.setenv("CLOUD_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("CLOUD_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CLOUD_SESSION_SECRET", "test-session-secret")
    monkeypatch.delenv("SARAPP_CLOUD_ROUTER_URL", raising=False)
    monkeypatch.delenv("SARAPP_CLOUD_ROUTER_TOKEN", raising=False)
    from cloud_server.main import create_cloud_app

    return TestClient(create_cloud_app(), follow_redirects=False)


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

