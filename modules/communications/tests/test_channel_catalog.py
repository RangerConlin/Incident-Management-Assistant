from __future__ import annotations

import pytest

from modules.communications import channel_catalog
from utils.api_client import api_client
from utils.catalog_cache import catalog_cache
from utils.incident_cache import incident_cache


@pytest.fixture(autouse=True)
def _clear_caches():
    catalog_cache.invalidate()
    incident_cache.clear()
    yield
    catalog_cache.invalidate()
    incident_cache.clear()


def test_get_master_channels_by_id_memoizes_and_indexes(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [
            {"id": 1, "name": "Command 1", "function": "Command"},
            {"id": 2, "name": "Tac 2", "function": "Tactical"},
        ]

    monkeypatch.setattr(api_client, "get", fake_get)

    by_id = channel_catalog.get_master_channels_by_id()
    by_id_again = channel_catalog.get_master_channels_by_id()

    assert by_id[1]["name"] == "Command 1"
    assert by_id[2]["function"] == "Tactical"
    assert calls == ["/api/comms/master-channels"]  # second call served from cache
    assert by_id_again == by_id


def test_invalidate_master_channels_forces_refetch(monkeypatch):
    calls: list[str] = []

    def fake_get(path, params=None):
        calls.append(path)
        return [{"id": 1, "name": f"Channel {len(calls)}"}]

    monkeypatch.setattr(api_client, "get", fake_get)

    first = channel_catalog.get_master_channels_by_id()
    channel_catalog.invalidate_master_channels()
    second = channel_catalog.get_master_channels_by_id()

    assert len(calls) == 2
    assert first[1]["name"] == "Channel 1"
    assert second[1]["name"] == "Channel 2"


def test_map_incident_channel_joins_master_fields():
    master_by_id = {5: {"id": 5, "name": "Command 1", "function": "Command", "rx_freq": 155.0}}
    doc = {
        "channel_id": "INC-CH-3",
        "master_id": "5",
        "priority": "High",
        "sort_index": 2,
    }

    row = channel_catalog.map_incident_channel(doc, master_by_id)

    assert row["id"] == 3
    assert row["channel"] == "Command 1"
    assert row["rx_freq"] == 155.0
    assert row["priority"] == "High"


def test_cached_channel_plan_reads_from_incident_cache(monkeypatch):
    def fake_get(path, params=None):
        return [{"id": 5, "name": "Command 1", "function": "Command", "system": "VHF"}]

    monkeypatch.setattr(api_client, "get", fake_get)

    incident_cache.load_snapshot(
        "INC-CACHE",
        {
            "incident_channels": [
                {"_id": "c-1", "channel_id": "INC-CH-1", "master_id": "5", "sort_index": 1},
            ]
        },
    )

    plan = channel_catalog.cached_channel_plan("INC-CACHE")

    assert plan is not None
    assert plan[0]["channel"] == "Command 1"
    assert plan[0]["system"] == "VHF"


def test_cached_channel_plan_returns_none_without_active_cache():
    assert channel_catalog.cached_channel_plan("INC-NOT-LOADED") is None
