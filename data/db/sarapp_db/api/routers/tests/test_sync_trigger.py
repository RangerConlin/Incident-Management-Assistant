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
    # Points at a URL nothing is listening on — push/pull failures inside
    # run_one_tick() are caught internally (see sync/loop.py), so this
    # still reports "synced": True; the point of this test is just that
    # the endpoint actually calls through to run_one_tick() rather than
    # short-circuiting, which the "not configured" test already covers.
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SARAPP_CLOUD_ROUTER_TOKEN", "test-token")

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync")

    assert response.status_code == 200
    assert response.json() == {"synced": True}


def test_sync_trigger_router_absent_in_master_only_mode() -> None:
    app = create_app(mode="master_only")
    paths = {route.path for route in app.routes}
    assert "/api/sync-trigger/resync" not in paths
