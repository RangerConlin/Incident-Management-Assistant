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
from sarapp_db.mongo.database_manager import get_master_db, get_system_db
from sarapp_db.mongo.collection_names import SystemCollections


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
    monkeypatch.setattr("sarapp_db.sync.central_client.pull_since", lambda *args, **kwargs: None)

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


def test_collection_resync_only_pulls_requested_collection(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://central-master.test")
    monkeypatch.setattr("sarapp_db.sync.loop.pull_and_apply", lambda collection: calls.append(collection) or True)

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync", params={"collection": "personnel"})

    assert response.status_code == 200
    assert response.json()["synced"] is True
    assert calls == ["personnel"]


def test_collection_resync_reports_requested_collection_failure(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "http://central-master.test")
    monkeypatch.setattr("sarapp_db.sync.loop.pull_and_apply", lambda collection: False)

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/sync-trigger/resync", params={"collection": "personnel"})

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] is False
    assert "personnel" in body["reason"]
    assert "vehicles" not in body["reason"]


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


def test_reset_local_catalog_clears_collection_checkpoint_and_outbox(monkeypatch) -> None:
    monkeypatch.delenv("SARAPP_MASTER_DB_NAME", raising=False)
    collection = "personnel"
    master_db = get_master_db()
    system_db = get_system_db()
    master_db[collection].delete_many({})
    system_db[SystemCollections.SYNC_PULL_CHECKPOINTS].delete_many({"_id": collection})
    system_db[SystemCollections.SYNC_STATE].delete_many({"collection": collection})
    master_db[collection].insert_many(
        [
            {"_id": "reset-person-1", "person_record": 1, "name": "Reset One"},
            {"_id": "reset-person-2", "person_record": 2, "name": "Reset Two"},
        ]
    )
    system_db[SystemCollections.SYNC_PULL_CHECKPOINTS].insert_one(
        {"_id": collection, "last_pulled_at": "2026-01-01T00:00:00+00:00"}
    )
    system_db[SystemCollections.SYNC_STATE].insert_one(
        {"_id": "queued-reset-person", "collection": collection, "doc_id": "reset-person-1"}
    )

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.post(f"/api/sync-trigger/local-catalog/{collection}/reset")

        assert response.status_code == 200
        body = response.json()
        assert body["reset"] is True
        assert body["deleted_count"] == 2
        assert body["cleared_outbox_count"] == 1
        assert master_db[collection].count_documents({}) == 0
        assert system_db[SystemCollections.SYNC_PULL_CHECKPOINTS].find_one({"_id": collection}) is None
        assert system_db[SystemCollections.SYNC_STATE].find_one({"collection": collection}) is None
    finally:
        master_db[collection].delete_many({"_id": {"$in": ["reset-person-1", "reset-person-2"]}})
        system_db[SystemCollections.SYNC_PULL_CHECKPOINTS].delete_many({"_id": collection})
        system_db[SystemCollections.SYNC_STATE].delete_many({"collection": collection})
