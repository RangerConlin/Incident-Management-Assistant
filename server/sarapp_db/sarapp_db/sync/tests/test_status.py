"""Coverage for sarapp_db.sync.status.get_sync_status — the snapshot the
LAN server console (and, later, the cloud dashboard) displays so an admin
can actually see whether central-catalog sync is configured and caught up.
"""
from __future__ import annotations

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

import pytest

from sarapp_db.mongo.mongo_client import get_client
from sarapp_db.sync import checkpoint, config, outbox
from sarapp_db.sync.status import get_sync_status

_SYSTEM_DB = "TEST_SYNC_STATUS_SYSTEM"


@pytest.fixture
def status_env(monkeypatch):
    monkeypatch.delenv("SARAPP_CENTRAL_MASTER_URL", raising=False)
    monkeypatch.setattr("sarapp_db.mongo.database_manager.DB_SYSTEM", _SYSTEM_DB, raising=False)
    get_client().drop_database(_SYSTEM_DB)
    yield
    get_client().drop_database(_SYSTEM_DB)


def test_disabled_when_no_central_master_url(status_env):
    status = get_sync_status()
    assert status == {
        "enabled": False,
        "central_master_url": "",
        "pending_count": 0,
        "last_pulled": {},
    }


def test_enabled_reports_url_pending_count_and_checkpoints(status_env, monkeypatch):
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "https://central.test")
    system_db = get_client()[_SYSTEM_DB]
    outbox.enqueue(system_db, collection="personnel", doc_id="p-1")
    outbox.enqueue(system_db, collection="equipment", doc_id="e-1")
    checkpoint.set_last_pulled_at(system_db, "personnel", "2026-01-01T00:00:00")

    status = get_sync_status()

    assert status["enabled"] is True
    assert status["central_master_url"] == "https://central.test"
    assert status["pending_count"] == 2
    assert status["last_pulled"]["personnel"] == "2026-01-01T00:00:00"
    assert status["last_pulled"]["equipment"] is None
    assert set(status["last_pulled"]) == set(config.SYNCABLE_MASTER_COLLECTIONS)
