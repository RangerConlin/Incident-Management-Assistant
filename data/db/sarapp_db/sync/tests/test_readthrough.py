from __future__ import annotations

from sarapp_db.sync.readthrough import refresh_collection_before_read


def test_refresh_collection_before_read_pulls_when_central_sync_enabled(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "https://central.test")
    monkeypatch.setattr("sarapp_db.mongo.database_manager.get_master_db", lambda: object())
    monkeypatch.setattr("sarapp_db.mongo.database_manager.is_central_master_db", lambda _db: False)
    monkeypatch.setattr("sarapp_db.sync.loop.pull_and_apply", lambda collection: calls.append(collection))

    refresh_collection_before_read("personnel")

    assert calls == ["personnel"]


def test_refresh_collection_before_read_skips_when_sync_disabled(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.delenv("SARAPP_CENTRAL_MASTER_URL", raising=False)
    monkeypatch.setattr("sarapp_db.sync.loop.pull_and_apply", lambda collection: calls.append(collection))

    refresh_collection_before_read("personnel")

    assert calls == []


def test_refresh_collection_before_read_is_best_effort(monkeypatch) -> None:
    monkeypatch.setenv("SARAPP_CENTRAL_MASTER_URL", "https://central.test")
    monkeypatch.setattr("sarapp_db.mongo.database_manager.get_master_db", lambda: object())
    monkeypatch.setattr("sarapp_db.mongo.database_manager.is_central_master_db", lambda _db: False)

    def raise_on_pull(_collection: str) -> None:
        raise RuntimeError("central unavailable")

    monkeypatch.setattr("sarapp_db.sync.loop.pull_and_apply", raise_on_pull)

    refresh_collection_before_read("personnel")
