"""POST /api/sync-trigger/resync lets a desktop client force an immediate
resync instead of waiting for CentralSyncLoop's next periodic tick.
"""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from fastapi.testclient import TestClient

from sarapp_db.api.app import create_app


def test_resync_reports_not_configured_when_sync_disabled(monkeypatch) -> None:
    monkeypatch.delenv("SARAPP_CENTRAL_MASTER_URL", raising=False)
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync")

    assert response.status_code == 200
    assert response.json() == {"synced": False, "reason": "Central master sync is not configured on this server."}


def test_resync_runs_a_tick_when_sync_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_TOKEN", "test-token")

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync")

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is False
    assert "could not complete a sync tick" in body["reason"]
    assert "personnel" in body["details"]["pull_failed_collections"]


def test_resync_reports_failure_instead_of_500_when_tick_raises(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://central-master.test")

    def boom() -> dict:
        raise RuntimeError("simulated sync crash")

    monkeypatch.setattr("sarapp_db.sync.loop.run_one_tick", boom)

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync")

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is False
    assert "simulated sync crash" in body["reason"]


def test_resync_reports_collection_error_details(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://central-master.test")
    monkeypatch.setattr(
        "sarapp_db.sync.loop.run_one_tick",
        lambda: {
            "enabled": True,
            "pull_failed_collections": ["vehicles"],
            "outbox_failed_count": 0,
            "outbox_sent_count": 0,
            "errors": [{"phase": "pull_and_apply", "collection": "vehicles", "error": "bad vehicle doc"}],
        },
    )

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync")

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is False
    assert "vehicles" in body["reason"]
    assert "bad vehicle doc" in body["reason"]


def test_resync_reports_failure_instead_of_500_for_legacy_tick_return(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://central-master.test")
    monkeypatch.setattr("sarapp_db.sync.loop.run_one_tick", lambda: None)

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync")

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is False
    assert "did not return a status summary" in body["reason"]


def test_sync_trigger_router_absent_in_master_only_mode() -> None:
    app = create_app(mode="master_only")
    paths = {route.path for route in app.routes}
    assert "/api/sync-trigger/resync" not in paths
