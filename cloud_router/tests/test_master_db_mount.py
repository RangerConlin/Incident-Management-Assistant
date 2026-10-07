"""Verifies the optional embedded central master database mount.

cloud_router stays a plain stateless proxy when SARAPP_CLOUD_ROUTER_MONGO_URI
is unset (covered implicitly by every other test in this suite, which run
without that variable). These tests cover the opt-in path.
"""

import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from router.app import create_router_app


def _route_paths(app) -> set[str]:
    paths: set[str] = set()
    for route in app.routes:
        paths.add(route.path)
        # Mounted sub-apps don't expose their inner routes on the parent
        # app's .routes directly in older Starlette versions; walk in if so.
        sub_app = getattr(route, "app", None)
        if sub_app is not None and hasattr(sub_app, "routes"):
            prefix = route.path
            for sub_route in sub_app.routes:
                paths.add(prefix + sub_route.path)
    return paths


def test_master_db_not_mounted_when_uri_unset(monkeypatch) -> None:
    monkeypatch.delenv("SARAPP_CLOUD_ROUTER_MONGO_URI", raising=False)

    app = create_router_app()
    paths = _route_paths(app)

    assert not any(path.startswith("/central-master") for path in paths)
    # Proxy/tunnel routes are still present.
    assert "/health" in paths
    assert "/tunnel/register" in paths


def test_master_db_mounted_when_uri_set(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_MONGO_URI", "mongodb://localhost:27017")

    app = create_router_app()
    paths = _route_paths(app)

    assert "/central-master/api/master/personnel" in paths
    assert "/health" in paths


def test_master_db_serves_central_master_personnel_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_MONGO_URI", "mongodb://localhost:27017")

    app = create_router_app()
    with TestClient(app) as client:
        response = client.get("/central-master/api/master/personnel")

    assert response.status_code == 200
