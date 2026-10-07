from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app
from sarapp_db.mongo.database_manager import get_central_master_db, get_master_db


def _route_paths(app) -> set[str]:
    return {route.path for route in app.routes}


def test_full_mode_mounts_incident_and_master_routers() -> None:
    app = create_app()
    paths = _route_paths(app)

    assert "/api/master/personnel" in paths
    assert "/api/incidents" in paths


def test_master_only_mode_omits_incident_routers() -> None:
    app = create_app(mode="master_only")
    paths = _route_paths(app)

    assert "/api/master/personnel" in paths
    assert "/api/incidents" not in paths
    assert not any(path.startswith("/api/incidents") for path in paths)


def test_unknown_mode_rejected() -> None:
    with pytest.raises(ValueError):
        create_app(mode="bogus")


def test_master_only_app_serves_personnel_endpoint() -> None:
    app = create_app(mode="master_only")
    with TestClient(app) as client:
        response = client.get("/api/master/personnel")
    assert response.status_code == 200


def test_master_db_name_env_var_redirects_get_master_db(monkeypatch) -> None:
    monkeypatch.delenv("SARAPP_MASTER_DB_NAME", raising=False)
    assert get_master_db().name == "sarapp_master"

    monkeypatch.setenv("SARAPP_MASTER_DB_NAME", "sarapp_central_master")
    assert get_master_db().name == "sarapp_central_master"
    assert get_master_db().name == get_central_master_db().name
